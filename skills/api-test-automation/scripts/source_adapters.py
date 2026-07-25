#!/usr/bin/env python3
"""Load P0 API document formats and normalize them to an API description."""
from __future__ import annotations

import hashlib
import json
import re
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

import yaml


class SourceError(ValueError):
    """Raised when an API source cannot be loaded or recognized."""


@dataclass(slots=True)
class ImportedSource:
    kind: str
    version: str
    source: str
    fidelity: str
    document: dict[str, Any]
    source_sha256: str
    warnings: list[str] = field(default_factory=list)
    unsupported_features: list[str] = field(default_factory=list)

    def manifest(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("document")
        data["operation_count"] = count_operations(self.document)
        data["schema_version"] = 1
        return data


@dataclass(slots=True)
class LoadedPayload:
    value: Any
    raw: bytes
    source: str
    content_type: str = ""


HTTP_METHODS = {
    "get",
    "put",
    "post",
    "delete",
    "options",
    "head",
    "patch",
    "trace",
}
OPENAPI_VERSION_PATTERN = re.compile(
    r"^3\.(?:0|1|2)\.\d+(?:[-+][0-9A-Za-z.-]+)?$"
)
POSTMAN_21_SCHEMA = "https://schema.getpostman.com/json/collection/v2.1.0/"
MAX_SOURCE_BYTES = 20 * 1024 * 1024
YAPI_PAGE_LIMIT = 10000


def _decode_payload(
    raw: bytes,
    source: str,
    content_type: str = "",
    *,
    timeout: float = 20,
    allow_html_discovery: bool = True,
) -> Any:
    text = raw.decode("utf-8-sig")
    if "html" in content_type.lower() or text.lstrip().lower().startswith("<!doctype html"):
        if not allow_html_discovery:
            raise SourceError("The discovered API description URL returned HTML")
        spec_url = _discover_spec_url(text, source)
        if not spec_url:
            raise SourceError(
                "The URL returned HTML, but no OpenAPI/Swagger document URL was found"
            )
        return _request_json(
            spec_url,
            timeout=timeout,
            allow_html_discovery=False,
        )
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            return yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise SourceError(f"Unable to parse JSON or YAML from {source}: {exc}") from exc


def _discover_spec_url(html: str, page_url: str) -> str | None:
    patterns = [
        r"""url\s*:\s*["']([^"']+(?:openapi|swagger|api-docs)[^"']*)["']""",
        r"""["']url["']\s*:\s*["']([^"']+)["']""",
        r"""["']([^"']+/(?:v[23]/api-docs|openapi\.json|swagger\.json))["']""",
    ]
    for pattern in patterns:
        match = re.search(pattern, html, flags=re.IGNORECASE)
        if match:
            return urllib.parse.urljoin(page_url, match.group(1))
    return None


def _request_json(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 20,
    allow_html_discovery: bool = True,
) -> LoadedPayload:
    parsed_url = urllib.parse.urlsplit(url)
    if (
        parsed_url.scheme not in {"http", "https"}
        or not parsed_url.hostname
        or parsed_url.username
        or parsed_url.password
    ):
        raise SourceError("Source URL must be an absolute credential-free HTTP(S) URL")
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json, application/yaml, text/yaml", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(MAX_SOURCE_BYTES + 1)
            if len(raw) > MAX_SOURCE_BYTES:
                raise SourceError(
                    f"Source exceeds the {MAX_SOURCE_BYTES // (1024 * 1024)} MiB limit"
                )
            content_type = response.headers.get("Content-Type", "")
            final_url = response.geturl()
    except SourceError:
        raise
    except Exception as exc:
        raise SourceError(f"Unable to load {_safe_url(url)}: {exc}") from exc
    decoded = _decode_payload(
        raw,
        final_url,
        content_type,
        timeout=timeout,
        allow_html_discovery=allow_html_discovery,
    )
    if isinstance(decoded, LoadedPayload):
        return decoded
    return LoadedPayload(decoded, raw, final_url, content_type)


def load_payload(source: str | Path) -> LoadedPayload:
    source_text = str(source)
    if source_text.startswith(("http://", "https://")):
        return _request_json(source_text)
    path = Path(source_text).expanduser().resolve()
    if not path.is_file():
        raise SourceError(f"Source file not found: {path}")
    if path.stat().st_size > MAX_SOURCE_BYTES:
        raise SourceError(
            f"Source exceeds the {MAX_SOURCE_BYTES // (1024 * 1024)} MiB limit: {path}"
        )
    raw = path.read_bytes()
    value = _decode_payload(raw, str(path))
    if isinstance(value, LoadedPayload):
        return value
    return LoadedPayload(value, raw, str(path))


def detect_kind(value: Any) -> tuple[str, str]:
    if isinstance(value, dict):
        swagger = str(value.get("swagger", ""))
        if swagger == "2.0":
            return "openapi", "2.0"
        openapi = str(value.get("openapi", ""))
        if OPENAPI_VERSION_PATTERN.fullmatch(openapi):
            return "openapi", openapi
        info = value.get("info")
        schema = info.get("schema", "") if isinstance(info, dict) else ""
        if (
            isinstance(schema, str)
            and "schema.getpostman.com/json/collection/v2.1" in schema
        ):
            return "postman", "2.1"
        if _looks_like_yapi(value):
            return "yapi", "native-json"
    if isinstance(value, list) and any(_looks_like_yapi(item) for item in value):
        return "yapi", "native-json"
    raise SourceError(
        "Unsupported API source. Expected OpenAPI/Swagger, YApi JSON, or Postman Collection 2.1"
    )


def import_source(source: str | Path) -> ImportedSource:
    loaded = load_payload(source)
    kind, version = detect_kind(loaded.value)
    digest = hashlib.sha256(loaded.raw).hexdigest()
    safe_source = (
        _safe_url(loaded.source)
        if loaded.source.startswith(("http://", "https://"))
        else loaded.source
    )
    if kind == "openapi":
        document = _validate_openapi(loaded.value)
        return ImportedSource(
            kind=kind,
            version=version,
            source=safe_source,
            fidelity="lossless",
            document=document,
            source_sha256=digest,
            warnings=_openapi_warnings(document),
        )
    if kind == "postman":
        document, warnings, unsupported = postman_to_openapi(loaded.value)
        return ImportedSource(
            kind=kind,
            version=version,
            source=safe_source,
            fidelity="high-with-losses",
            document=document,
            source_sha256=digest,
            warnings=warnings,
            unsupported_features=unsupported,
        )
    document, warnings, unsupported = yapi_to_openapi(loaded.value)
    return ImportedSource(
        kind=kind,
        version=version,
        source=safe_source,
        fidelity="high",
        document=document,
        source_sha256=digest,
        warnings=warnings,
        unsupported_features=unsupported,
    )


def import_code_source(
    root: str | Path,
    *,
    url_prefix: str | None = None,
    max_files: int = 5000,
    max_bytes: int = 50 * 1024 * 1024,
) -> ImportedSource:
    """Import a static source scan through the same normalized-source seam."""
    from code_source_adapter import CodeScanError, SCANNER_VERSION, scan_code_source

    try:
        scanned = scan_code_source(
            root,
            url_prefix=url_prefix,
            max_files=max_files,
            max_bytes=max_bytes,
        )
    except CodeScanError as exc:
        raise SourceError(str(exc)) from exc
    return ImportedSource(
        kind="source-code",
        version=SCANNER_VERSION,
        source=scanned.source,
        fidelity="skeleton",
        document=scanned.document,
        source_sha256=scanned.source_sha256,
        warnings=scanned.warnings,
        unsupported_features=scanned.unsupported_features,
    )


def import_yapi_project(
    base_url: str,
    project_id: int,
    token: str,
    *,
    timeout: float = 20,
) -> ImportedSource:
    if not token:
        raise SourceError("YApi token is required")
    base = base_url.rstrip("/")
    parsed_base = urllib.parse.urlsplit(base)
    if (
        parsed_base.scheme not in {"http", "https"}
        or not parsed_base.hostname
        or parsed_base.username
        or parsed_base.password
        or parsed_base.query
        or parsed_base.fragment
    ):
        raise SourceError("YApi base URL must be an absolute credential-free HTTP(S) URL")
    interfaces = []
    seen_interface_ids: set[Any] = set()
    page = 1
    total: int | None = None
    while True:
        query = urllib.parse.urlencode(
            {"project_id": project_id, "token": token, "page": page, "limit": YAPI_PAGE_LIMIT}
        )
        listed = _request_json(f"{base}/api/interface/list?{query}", timeout=timeout)
        data = _unwrap_yapi_response(listed.value, "interface/list")
        summaries = data.get("list", []) if isinstance(data, dict) else []
        if not isinstance(summaries, list):
            raise SourceError("YApi interface/list response does not contain data.list")
        if total is None and isinstance(data, dict):
            raw_total = data.get("total")
            if isinstance(raw_total, int) and raw_total >= 0:
                total = raw_total
        new_items = 0
        for summary in summaries:
            interface_id = summary.get("_id") if isinstance(summary, dict) else None
            if interface_id is None or interface_id in seen_interface_ids:
                continue
            seen_interface_ids.add(interface_id)
            new_items += 1
            detail_query = urllib.parse.urlencode({"id": interface_id, "token": token})
            detail = _request_json(
                f"{base}/api/interface/get?{detail_query}", timeout=timeout
            )
            interfaces.append(_unwrap_yapi_response(detail.value, "interface/get"))
        if not summaries:
            break
        if total is not None and len(seen_interface_ids) >= total:
            break
        if new_items == 0:
            raise SourceError("YApi pagination repeated a page without new interfaces")
        if total is None and len(summaries) < YAPI_PAGE_LIMIT:
            break
        page += 1
    raw = json.dumps(interfaces, ensure_ascii=False, sort_keys=True).encode()
    document, warnings, unsupported = yapi_to_openapi({"list": interfaces})
    return ImportedSource(
        kind="yapi",
        version="open-api",
        source=f"{base}/project/{project_id}",
        fidelity="high",
        document=document,
        source_sha256=hashlib.sha256(raw).hexdigest(),
        warnings=warnings,
        unsupported_features=unsupported,
    )


def _unwrap_yapi_response(value: Any, endpoint: str) -> Any:
    if not isinstance(value, dict):
        raise SourceError(f"YApi {endpoint} returned a non-object response")
    if value.get("errcode") not in (None, 0):
        raise SourceError(
            f"YApi {endpoint} failed: {value.get('errmsg') or value.get('errcode')}"
        )
    return value.get("data", value)


def _validate_openapi(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SourceError("OpenAPI document must be an object")
    swagger = str(value.get("swagger", ""))
    if swagger == "2.0":
        if not isinstance(value.get("paths"), dict):
            raise SourceError("Swagger 2.0 documents must contain a paths object")
        return value

    openapi = str(value.get("openapi", ""))
    if OPENAPI_VERSION_PATTERN.fullmatch(openapi):
        present_sections = [
            name for name in ("paths", "components", "webhooks") if name in value
        ]
        if not present_sections:
            raise SourceError(
                "OpenAPI 3.x documents must contain at least one of paths, components, or webhooks"
            )
        for section in present_sections:
            if not isinstance(value.get(section), dict):
                raise SourceError(f"OpenAPI 3.x field '{section}' must be an object")
        return value

    if not isinstance(value.get("paths"), dict):
        raise SourceError("OpenAPI document must contain a paths object")
    return value


def _openapi_warnings(document: dict[str, Any]) -> list[str]:
    warnings = []
    operation_ids: set[str] = set()
    duplicates: set[str] = set()
    for _, _, operation in iter_operations(document):
        operation_id = operation.get("operationId")
        if not operation_id:
            continue
        if operation_id in operation_ids:
            duplicates.add(operation_id)
        operation_ids.add(operation_id)
    if duplicates:
        warnings.append(
            "Duplicate operationId values: " + ", ".join(sorted(duplicates))
        )
    refs = [
        value
        for value in _iter_ref_values(document)
        if isinstance(value, str) and not value.startswith("#")
    ]
    if refs:
        warnings.append("The document contains references; external references are preserved")
    return warnings


def _iter_ref_values(value: Any) -> Iterable[Any]:
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "$ref":
                yield item
            else:
                yield from _iter_ref_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_ref_values(item)


def iter_operations(
    document: dict[str, Any],
) -> Iterable[tuple[str, str, dict[str, Any]]]:
    is_openapi_32 = str(document.get("openapi", "")).startswith("3.2.")
    fixed_methods = HTTP_METHODS | ({"query"} if is_openapi_32 else set())
    for container_name, container in (
        ("paths", document.get("paths") or {}),
        ("webhooks", document.get("webhooks") or {}),
    ):
        for path, path_item in container.items():
            if not isinstance(path_item, dict):
                continue
            inventory_path = (
                path if container_name == "paths" else f"webhooks:{path}"
            )
            for method, operation in path_item.items():
                if method.lower() in fixed_methods and isinstance(operation, dict):
                    yield method.upper(), inventory_path, operation
            additional = path_item.get("additionalOperations")
            if is_openapi_32 and isinstance(additional, dict):
                for method, operation in additional.items():
                    if isinstance(operation, dict):
                        yield method.upper(), inventory_path, operation


def count_operations(document: dict[str, Any]) -> int:
    return sum(1 for _ in iter_operations(document))


def operation_inventory(document: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "method": method,
            "path": path,
            "operation_id": operation.get("operationId"),
            "summary": operation.get("summary", ""),
            "tags": operation.get("tags", []),
        }
        for method, path, operation in iter_operations(document)
    ]


def _looks_like_yapi(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    if {"path", "method", "title"} <= value.keys():
        return True
    if isinstance(value.get("list"), list):
        return any(_looks_like_yapi(item) for item in value["list"])
    if isinstance(value.get("data"), (dict, list)):
        nested = value["data"]
        return _looks_like_yapi(nested) if isinstance(nested, dict) else any(
            _looks_like_yapi(item) for item in nested
        )
    return False


def _walk_yapi(value: Any, category: str = "") -> Iterable[tuple[dict[str, Any], str]]:
    if isinstance(value, list):
        for item in value:
            yield from _walk_yapi(item, category)
        return
    if not isinstance(value, dict):
        return
    if {"path", "method"} <= value.keys():
        yield value, category
        return
    next_category = str(value.get("name") or value.get("cat_name") or category)
    for key in ("list", "data", "interfaces"):
        if key in value:
            yield from _walk_yapi(value[key], next_category)


def _parse_json_value(raw: Any) -> Any:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _safe_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    sensitive_query_keys = {
        "access_token",
        "api-key",
        "api_key",
        "apikey",
        "auth",
        "authorization",
        "key",
        "password",
        "private_token",
        "secret",
        "sig",
        "signature",
        "token",
    }
    safe_query = [
        (key, "[REDACTED]" if key.lower() in sensitive_query_keys else value)
        for key, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    ]
    hostname = parsed.hostname or ""
    try:
        port = parsed.port
    except ValueError:
        port = None
    if port:
        hostname = f"{hostname}:{port}"
    return urllib.parse.urlunsplit(
        (parsed.scheme, hostname, parsed.path, urllib.parse.urlencode(safe_query), "")
    )


def _coerce_declared_example(value: Any, schema_type: str) -> Any:
    if not isinstance(value, str):
        return value
    try:
        if schema_type == "boolean" and value.lower() in {"true", "false"}:
            return value.lower() == "true"
        if schema_type == "integer":
            return int(value)
        if schema_type == "number":
            return float(value)
        if schema_type in {"array", "object"}:
            parsed = json.loads(value)
            expected = list if schema_type == "array" else dict
            return parsed if isinstance(parsed, expected) else value
    except (TypeError, ValueError, json.JSONDecodeError):
        return value
    return value


def _source_flag(value: Any) -> bool:
    return value is True or str(value).lower() in {"1", "true", "yes"}


def _oas_parameter(
    item: dict[str, Any],
    location: str,
    *,
    default_required: bool = False,
) -> dict[str, Any]:
    name = str(item.get("name") or item.get("key") or item.get("_id") or "parameter")
    declared_type = str(item.get("type") or "string").lower()
    type_aliases = {
        "bool": "boolean",
        "float": "number",
        "int": "integer",
    }
    schema_type = type_aliases.get(declared_type, declared_type)
    if schema_type not in {"array", "boolean", "integer", "number", "object", "string"}:
        schema_type = "string"
    parameter: dict[str, Any] = {
        "name": name,
        "in": location,
        "required": location == "path"
        or str(item.get("required", "")).lower() in {"1", "true", "yes"},
        "schema": {"type": schema_type},
    }
    if default_required:
        parameter["required"] = True
    description = item.get("desc") or item.get("description")
    if description:
        parameter["description"] = str(description)
    example = item.get("example") or item.get("value")
    if example not in (None, ""):
        parameter["example"] = _coerce_declared_example(example, schema_type)
    return parameter


def _unique_operation_id(method: str, path: str, used: set[str]) -> str:
    stem = re.sub(r"[^a-zA-Z0-9]+", "_", f"{method}_{path}").strip("_").lower()
    stem = stem or "operation"
    candidate = stem
    index = 2
    while candidate in used:
        candidate = f"{stem}_{index}"
        index += 1
    used.add(candidate)
    return candidate


def yapi_to_openapi(
    value: Any,
) -> tuple[dict[str, Any], list[str], list[str]]:
    endpoints = list(_walk_yapi(value))
    if not endpoints:
        raise SourceError("No YApi interfaces were found")
    title = "Imported YApi project"
    if isinstance(value, dict):
        project = value.get("project") or {}
        if isinstance(project, dict):
            title = str(project.get("name") or project.get("project_name") or title)
    document: dict[str, Any] = {
        "openapi": "3.1.0",
        "info": {"title": title, "version": "imported"},
        "paths": {},
    }
    used_ids: set[str] = set()
    warnings = [
        "YApi does not provide response status codes consistently; missing codes default to 200"
    ]
    unsupported: set[str] = set()
    for interface, category in endpoints:
        method = str(interface.get("method") or "GET").lower()
        path = str(interface.get("path") or interface.get("query_path", {}).get("path") or "/")
        if method not in HTTP_METHODS:
            warnings.append(f"Skipped unsupported method {method.upper()} {path}")
            continue
        operation: dict[str, Any] = {
            "operationId": _unique_operation_id(method, path, used_ids),
            "summary": str(interface.get("title") or f"{method.upper()} {path}"),
            "responses": {},
            "x-source-yapi-id": interface.get("_id"),
        }
        description = interface.get("markdown") or interface.get("desc")
        if description:
            operation["description"] = str(description)
        raw_tags = interface.get("tag") or []
        tags = (
            [str(tag) for tag in raw_tags]
            if isinstance(raw_tags, list)
            else [str(raw_tags)]
        )
        if category and category not in tags:
            tags.append(category)
        if tags:
            operation["tags"] = tags
        parameters = []
        parameters.extend(
            _oas_parameter(item, "path", default_required=True)
            for item in (interface.get("req_params") or [])
        )
        parameters.extend(
            _oas_parameter(item, "query")
            for item in (interface.get("req_query") or [])
        )
        parameters.extend(
            _oas_parameter(item, "header")
            for item in (interface.get("req_headers") or [])
            if str(item.get("name", "")).lower() not in {"content-type", "accept"}
        )
        if parameters:
            operation["parameters"] = parameters
        body_type = str(interface.get("req_body_type") or "").lower()
        body_value = _parse_json_value(interface.get("req_body_other"))
        if body_type == "json" and body_value is not None:
            if _source_flag(interface.get("req_body_is_json_schema")) and isinstance(
                body_value, dict
            ):
                body_schema = body_value
            else:
                body_schema = {"example": body_value}
            operation["requestBody"] = {
                "content": {"application/json": {"schema": body_schema}}
            }
        elif body_type in {"form", "file"}:
            properties = {}
            required = []
            for item in interface.get("req_body_form") or []:
                name = str(item.get("name") or "field")
                properties[name] = {
                    "type": "string",
                    **({"description": str(item["desc"])} if item.get("desc") else {}),
                }
                if str(item.get("type", "")).lower() == "file":
                    properties[name].update({"type": "string", "format": "binary"})
                if str(item.get("required", "")).lower() in {"1", "true", "yes"}:
                    required.append(name)
            schema: dict[str, Any] = {"type": "object", "properties": properties}
            if required:
                schema["required"] = required
            media = (
                "multipart/form-data"
                if any(p.get("format") == "binary" for p in properties.values())
                else "application/x-www-form-urlencoded"
            )
            operation["requestBody"] = {"content": {media: {"schema": schema}}}
        elif interface.get("req_body_other"):
            operation["requestBody"] = {
                "content": {
                    "text/plain": {
                        "schema": {
                            "type": "string",
                            "example": str(interface["req_body_other"]),
                        }
                    }
                }
            }
        response_value = _parse_json_value(interface.get("res_body"))
        response: dict[str, Any] = {"description": "Imported YApi response"}
        if response_value is not None:
            if _source_flag(interface.get("res_body_is_json_schema")) and isinstance(
                response_value, dict
            ):
                response_schema = response_value
            else:
                response_schema = {"example": response_value}
            response["content"] = {"application/json": {"schema": response_schema}}
        operation["responses"]["200"] = response
        for script_field in ("pre_script", "after_script", "test_script"):
            if interface.get(script_field):
                unsupported.add(f"YApi {script_field}")
        path_item = document["paths"].setdefault(path, {})
        if method in path_item:
            warnings.append(
                f"Duplicate YApi interface {method.upper()} {path}; later definition was skipped"
            )
            continue
        path_item[method] = operation
    return document, warnings, sorted(unsupported)


def _walk_postman_items(items: list[Any], folders: tuple[str, ...] = ()):
    for item in items:
        if not isinstance(item, dict):
            continue
        if isinstance(item.get("item"), list):
            name = str(item.get("name") or "folder")
            yield from _walk_postman_items(item["item"], (*folders, name))
        elif isinstance(item.get("request"), (dict, str)):
            yield item, folders


def _postman_collection_features(value: Any) -> set[str]:
    unsupported: set[str] = set()
    if not isinstance(value, dict):
        return unsupported
    if value.get("event"):
        unsupported.add("Postman pre-request/test scripts")
    if value.get("variable"):
        unsupported.add("Postman variable scopes")
    if value.get("auth"):
        unsupported.add("Postman collection/folder auth configuration")
    for item in value.get("item") or []:
        unsupported.update(_postman_collection_features(item))
    return unsupported


def _postman_variables(collection: dict[str, Any]) -> dict[str, str]:
    variables: dict[str, str] = {}
    for item in collection.get("variable") or []:
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        value = item.get("value")
        if isinstance(key, str) and isinstance(value, str):
            variables[key] = value
    return variables


def _postman_server_url(raw: str, variables: dict[str, str]) -> str | None:
    expanded = raw
    for key, value in variables.items():
        expanded = expanded.replace(f"{{{{{key}}}}}", value)
    parsed = urllib.parse.urlsplit(expanded)
    if (
        parsed.scheme in {"http", "https"}
        and parsed.hostname
        and not parsed.username
        and not parsed.password
    ):
        hostname = parsed.hostname
        try:
            port = parsed.port
        except ValueError:
            return None
        if port:
            hostname = f"{hostname}:{port}"
        return urllib.parse.urlunsplit((parsed.scheme, hostname, "", "", ""))
    return None


def _postman_url(
    request: dict[str, Any], variables: dict[str, str]
) -> tuple[str, list[dict[str, Any]], str | None]:
    raw_url = request.get("url")
    if isinstance(raw_url, str):
        raw = raw_url
        server_url = _postman_server_url(raw, variables)
        parsed_query = urllib.parse.urlsplit(raw).query
        query_items = [
            {"key": key, "value": value}
            for key, value in urllib.parse.parse_qsl(parsed_query, keep_blank_values=True)
        ]
    elif isinstance(raw_url, dict):
        raw = str(raw_url.get("raw") or "")
        server_url = _postman_server_url(raw, variables)
        parsed_query = urllib.parse.urlsplit(
            raw.replace("{{baseUrl}}", "http://placeholder.invalid")
        ).query
        path_parts = raw_url.get("path") or []
        if isinstance(path_parts, list) and path_parts:
            raw = "/" + "/".join(str(part) for part in path_parts)
        query_items = raw_url.get("query") or [
            {"key": key, "value": value}
            for key, value in urllib.parse.parse_qsl(parsed_query, keep_blank_values=True)
        ]
    else:
        raw, query_items, server_url = "/", [], None
    parsed = urllib.parse.urlsplit(raw.replace("{{baseUrl}}", "http://placeholder.invalid"))
    path = parsed.path or raw.split("?", 1)[0] or "/"
    path = re.sub(r":([A-Za-z_][\w-]*)", r"{\1}", path)
    path = re.sub(r"\{\{([^}]+)\}\}", r"{\1}", path)
    if not path.startswith("/"):
        path = "/" + path
    return path, query_items, server_url


def postman_to_openapi(
    collection: dict[str, Any],
) -> tuple[dict[str, Any], list[str], list[str]]:
    info = collection.get("info") or {}
    title = str(info.get("name") or "Imported Postman collection")
    document: dict[str, Any] = {
        "openapi": "3.1.0",
        "info": {
            "title": title,
            "version": str(info.get("version") or "imported"),
        },
        "paths": {},
    }
    warnings = [
        "Postman scripts and variable scopes are not executed during import"
    ]
    unsupported = _postman_collection_features(collection)
    variables = _postman_variables(collection)
    server_urls: set[str] = set()
    used_ids: set[str] = set()
    for item, folders in _walk_postman_items(collection.get("item") or []):
        request = item["request"]
        if isinstance(request, str):
            request = {"method": "GET", "url": request}
        method = str(request.get("method") or "GET").lower()
        if method not in HTTP_METHODS:
            continue
        path, query_items, server_url = _postman_url(request, variables)
        if server_url:
            server_urls.add(server_url)
        operation: dict[str, Any] = {
            "operationId": _unique_operation_id(method, path, used_ids),
            "summary": str(item.get("name") or f"{method.upper()} {path}"),
            "responses": {},
        }
        if folders:
            operation["tags"] = list(folders)
        description = request.get("description")
        if isinstance(description, dict):
            description = description.get("content")
        if description:
            operation["description"] = str(description)
        parameters: list[dict[str, Any]] = []
        for variable in (
            request.get("url", {}).get("variable", [])
            if isinstance(request.get("url"), dict)
            else []
        ):
            parameters.append(_oas_parameter(variable, "path", default_required=True))
        for query in query_items:
            if query.get("disabled"):
                continue
            parameters.append(_oas_parameter(query, "query"))
        headers = request.get("header") or []
        for header in headers:
            if header.get("disabled"):
                continue
            name = str(header.get("key") or header.get("name") or "")
            if name.lower() == "authorization":
                unsupported.add("Postman Authorization headers")
                continue
            if name.lower() == "accept":
                unsupported.add("Postman Accept headers")
                continue
            if name.lower() == "content-type":
                continue
            parameters.append(
                _oas_parameter(
                    {"name": name, "value": header.get("value"), "desc": header.get("description")},
                    "header",
                )
            )
        if parameters:
            operation["parameters"] = parameters
        body = request.get("body") or {}
        mode = body.get("mode")
        if mode == "raw":
            raw = body.get("raw", "")
            parsed = _parse_json_value(raw)
            media = "application/json" if parsed is not None else "text/plain"
            schema: dict[str, Any] = (
                {"example": parsed}
                if parsed is not None
                else {"type": "string", "example": raw}
            )
            operation["requestBody"] = {"content": {media: {"schema": schema}}}
        elif mode in {"urlencoded", "formdata"}:
            properties = {}
            required = []
            for field_item in body.get(mode) or []:
                if field_item.get("disabled"):
                    continue
                name = str(field_item.get("key") or "field")
                schema = {"type": "string"}
                if field_item.get("type") == "file":
                    schema["format"] = "binary"
                if field_item.get("value") not in (None, ""):
                    schema["example"] = field_item["value"]
                properties[name] = schema
                required.append(name)
            media = (
                "multipart/form-data"
                if mode == "formdata"
                else "application/x-www-form-urlencoded"
            )
            operation["requestBody"] = {
                "content": {
                    media: {
                        "schema": {
                            "type": "object",
                            "properties": properties,
                            "required": required,
                        }
                    }
                }
            }
        elif mode:
            unsupported.add(f"Postman request body mode: {mode}")
        responses = item.get("response") or []
        for response in responses:
            code = str(response.get("code") or "default")
            converted: dict[str, Any] = {
                "description": str(response.get("name") or "Imported example")
            }
            body_text = response.get("body")
            if isinstance(body_text, str) and body_text:
                parsed = _parse_json_value(body_text)
                if parsed is not None:
                    converted["content"] = {
                        "application/json": {"example": parsed}
                    }
                else:
                    converted["content"] = {"text/plain": {"example": body_text}}
            operation["responses"][code] = converted
        if not operation["responses"]:
            operation["responses"]["default"] = {
                "description": "Response not defined in the Postman collection"
            }
        if item.get("event") or request.get("event"):
            unsupported.add("Postman pre-request/test scripts")
        if request.get("auth"):
            unsupported.add("Postman request-level auth configuration")
        path_item = document["paths"].setdefault(path, {})
        if method in path_item:
            warnings.append(
                f"Duplicate Postman request {method.upper()} {path}; later request was skipped"
            )
            continue
        path_item[method] = operation
    if not document["paths"]:
        raise SourceError("No requests were found in the Postman collection")
    if server_urls:
        document["servers"] = [{"url": url} for url in sorted(server_urls)]
    return document, warnings, sorted(unsupported)


def dump_api_description(document: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".json":
        path.write_text(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    else:
        path.write_text(
            yaml.safe_dump(document, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
