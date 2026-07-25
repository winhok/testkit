#!/usr/bin/env python3
"""Safe Arazzo workflow execution for deterministic API automation."""
from __future__ import annotations

import http.cookiejar
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import yaml


SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
ARAZZO_VERSION = re.compile(r"^1\.(?:0|1)\.\d+$")
EXPRESSION = re.compile(
    r"^\$(?:inputs|outputs|steps|response)"
    r"(?:[.#].*)?$|^\$(?:statusCode|url|method)$"
)
EMBEDDED_EXPRESSION = re.compile(r"\{(\$[^{}]+)\}")
MAX_DOCUMENT_BYTES = 20 * 1024 * 1024
MAX_WORKFLOW_DEPTH = 10
HEADER_NAME = re.compile(r"^[A-Za-z0-9!#$%&'*+.^_`|~-]+$")
SIMPLE_COMPARISON = re.compile(r"(.+?)\s*(==|!=|>=|<=|>|<)\s*(.+)")
RESULT_METADATA_FIELDS = {
    "runner",
    "status",
    "error_type",
    "workflow_id",
    "dataset_index",
    "phase",
    "step_id",
    "operation_id",
    "method",
    "path",
    "status_code",
    "duration_ms",
    "output_names",
}


class WorkflowError(ValueError):
    """Base workflow error."""


class WorkflowConfigurationError(WorkflowError):
    """Raised before network access when workflow configuration is invalid."""


class WorkflowTransportError(WorkflowError):
    """Raised when a request could not produce an HTTP response."""


@dataclass(slots=True)
class HttpResponse:
    status_code: int
    headers: dict[str, str]
    body: Any
    text: str


class HttpTransport(Protocol):
    def reset(self) -> None: ...

    def request(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        query: dict[str, object],
        body: object,
        timeout: float,
    ) -> HttpResponse: ...


class UrllibTransport:
    """Cookie-preserving stdlib HTTP transport."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Start a fresh top-level workflow session while preserving step cookies."""
        cookie_jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(cookie_jar),
            _SameOriginRedirectHandler(),
        )

    def request(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        query: dict[str, object],
        body: object,
        timeout: float,
    ) -> HttpResponse:
        if query:
            encoded = urllib.parse.urlencode(query, doseq=True)
            url = f"{url}{'&' if '?' in url else '?'}{encoded}"
        data: bytes | None = None
        request_headers = dict(headers)
        if not any(name.lower() == "user-agent" for name in request_headers):
            request_headers["User-Agent"] = "testkit-api-test-automation/1.0"
        if body is not None:
            content_type = request_headers.get("Content-Type", "application/json")
            request_headers["Content-Type"] = content_type
            media_type = content_type.split(";", 1)[0].strip().lower()
            if media_type == "application/json" or media_type.endswith("+json"):
                data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            elif isinstance(body, str):
                data = body.encode("utf-8")
            elif isinstance(body, bytes):
                data = body
            else:
                data = urllib.parse.urlencode(body, doseq=True).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers=request_headers,
            method=method,
        )
        try:
            with self._opener.open(request, timeout=timeout) as response:
                raw = response.read()
                return _http_response(response.status, dict(response.headers), raw)
        except urllib.error.HTTPError as exc:
            return _http_response(exc.code, dict(exc.headers), exc.read())
        except (TimeoutError, urllib.error.URLError, OSError, ValueError) as exc:
            raise WorkflowTransportError(f"HTTP transport failed: {exc}") from exc


class _SameOriginRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Block redirects that could forward workflow credentials to another origin."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if _origin(req.full_url) != _origin(newurl):
            raise urllib.error.URLError("Cross-origin redirect blocked")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _origin(url: str) -> tuple[str, str, int | None]:
    parsed = urllib.parse.urlsplit(url)
    port = parsed.port
    if port is None:
        port = 443 if parsed.scheme.lower() == "https" else 80
    return parsed.scheme.lower(), (parsed.hostname or "").lower(), port


def _add_query_value(
    query: dict[str, object],
    name: str,
    value: object,
) -> None:
    """Preserve repeated query keys for urlencode(..., doseq=True)."""
    if name not in query:
        query[name] = value
        return
    existing = query[name]
    existing_values = (
        list(existing)
        if isinstance(existing, (list, tuple))
        else [existing]
    )
    new_values = (
        list(value)
        if isinstance(value, (list, tuple))
        else [value]
    )
    query[name] = [*existing_values, *new_values]


def _http_response(status: int, headers: dict[str, str], raw: bytes) -> HttpResponse:
    text = raw.decode("utf-8", errors="replace")
    content_type = next(
        (value for key, value in headers.items() if key.lower() == "content-type"),
        "",
    )
    body: Any = None
    if raw and ("json" in content_type.lower() or text.lstrip().startswith(("{", "["))):
        try:
            body = json.loads(text)
        except json.JSONDecodeError:
            body = None
    return HttpResponse(
        status_code=status,
        headers={key.lower(): value for key, value in headers.items()},
        body=body,
        text=text,
    )


@dataclass(slots=True)
class Operation:
    operation_id: str
    method: str
    path: str
    raw: dict[str, Any]


@dataclass(slots=True)
class RuntimeContext:
    inputs: dict[str, Any]
    step_outputs: dict[str, dict[str, Any]] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    response: HttpResponse | None = None
    url: str = ""
    method: str = ""
    secret_values: list[str] = field(default_factory=list)


def _load_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise WorkflowConfigurationError(f"Document not found: {path}")
    if path.stat().st_size > MAX_DOCUMENT_BYTES:
        raise WorkflowConfigurationError(
            f"Document exceeds the {MAX_DOCUMENT_BYTES} byte limit: {path}"
        )
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise WorkflowConfigurationError(f"Unable to read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise WorkflowConfigurationError(f"Document must be an object: {path}")
    return value


def _json_pointer(value: Any, pointer: str) -> Any:
    if pointer in {"", "#"}:
        return value
    if pointer.startswith("#"):
        pointer = pointer[1:]
    if not pointer.startswith("/"):
        raise WorkflowConfigurationError(f"Invalid JSON Pointer: {pointer}")
    current = value
    for raw_part in pointer[1:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            raise WorkflowError(f"JSON Pointer did not resolve: {pointer}")
    return current


def _validate_json_pointer_syntax(pointer: str, *, location: str) -> None:
    normalized = pointer[1:] if pointer.startswith("#") else pointer
    if normalized and not normalized.startswith("/"):
        raise WorkflowConfigurationError(
            f"{location} has an invalid JSON Pointer: {pointer}"
        )
    if re.search(r"~(?![01])", normalized):
        raise WorkflowConfigurationError(
            f"{location} has an invalid JSON Pointer escape: {pointer}"
        )


def _jsonpath_tokens(selector: str) -> list[tuple[str, str]]:
    if selector == "$":
        return []
    if not selector.startswith("$."):
        raise WorkflowConfigurationError(
            f"Only deterministic dot/index JSONPath is supported: {selector}"
        )
    tail = selector[2:]
    tokens = re.findall(r"([A-Za-z_][A-Za-z0-9_-]*)|\[(\d+)\]", tail)
    reconstructed_parts: list[str] = []
    for index, (name, position) in enumerate(tokens):
        if name:
            reconstructed_parts.append(
                ("" if index == 0 else ".") + name
            )
        else:
            reconstructed_parts.append(f"[{position}]")
    reconstructed = "".join(reconstructed_parts)
    if reconstructed != tail:
        raise WorkflowConfigurationError(
            f"Only deterministic dot/index JSONPath is supported: {selector}"
        )
    return tokens


def _jsonpath(value: Any, selector: str) -> Any:
    tokens = _jsonpath_tokens(selector)
    if not tokens:
        return value
    current = value
    for name, position in tokens:
        if name:
            if not isinstance(current, dict) or name not in current:
                raise WorkflowError(f"JSONPath did not resolve: {selector}")
            current = current[name]
        else:
            index = int(position)
            if not isinstance(current, list) or index >= len(current):
                raise WorkflowError(f"JSONPath did not resolve: {selector}")
            current = current[index]
    return current


def _nested(value: Any, dotted: str) -> Any:
    if isinstance(value, dict) and dotted in value:
        return value[dotted]
    current = value
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            raise WorkflowError(f"Runtime expression did not resolve: {dotted}")
        current = current[part]
    return current


def _split_pointer(expression: str) -> tuple[str, str]:
    if "#" not in expression:
        return expression, ""
    base, pointer = expression.split("#", 1)
    return base, pointer


def _resolve_expression(expression: str, context: RuntimeContext) -> Any:
    base, pointer = _split_pointer(expression)
    if base == "$statusCode":
        if context.response is None:
            raise WorkflowError("$statusCode is unavailable before a response")
        value: Any = context.response.status_code
    elif base == "$url":
        value = context.url
    elif base == "$method":
        value = context.method
    elif base.startswith("$inputs."):
        value = _nested(context.inputs, base[len("$inputs.") :])
    elif base.startswith("$outputs."):
        value = _nested(context.outputs, base[len("$outputs.") :])
    elif base.startswith("$steps."):
        match = re.fullmatch(
            r"\$steps\.([A-Za-z0-9_-]+)\.outputs\.([A-Za-z0-9_.-]+)",
            base,
        )
        if not match:
            raise WorkflowConfigurationError(f"Unsupported step expression: {expression}")
        step_id, output_name = match.groups()
        if step_id not in context.step_outputs:
            raise WorkflowError(f"Step output is unavailable: {step_id}")
        value = _nested(context.step_outputs[step_id], output_name)
    elif base == "$response.body":
        if context.response is None:
            raise WorkflowError("$response.body is unavailable before a response")
        value = context.response.body
    elif base.startswith("$response.header."):
        if context.response is None:
            raise WorkflowError("$response.header is unavailable before a response")
        name = base[len("$response.header.") :].lower()
        if name not in context.response.headers:
            raise WorkflowError(f"Response header is unavailable: {name}")
        value = context.response.headers[name]
    else:
        raise WorkflowConfigurationError(f"Unsupported runtime expression: {expression}")
    return _json_pointer(value, pointer) if pointer else value


def _render(value: Any, context: RuntimeContext) -> Any:
    if isinstance(value, str):
        if EXPRESSION.fullmatch(value):
            return _resolve_expression(value, context)

        def replace(match: re.Match[str]) -> str:
            return str(_resolve_expression(match.group(1), context))

        return EMBEDDED_EXPRESSION.sub(replace, value)
    if isinstance(value, list):
        return [_render(item, context) for item in value]
    if isinstance(value, dict):
        return {key: _render(item, context) for key, item in value.items()}
    return value


def _validate_renderable(value: Any, *, location: str) -> None:
    if isinstance(value, str):
        if value.startswith("$") and not EXPRESSION.fullmatch(value):
            raise WorkflowConfigurationError(
                f"{location} contains an unsupported runtime expression: {value}"
            )
        for match in re.finditer(r"\{(\$[^{}]+)\}", value):
            if not EXPRESSION.fullmatch(match.group(1)):
                raise WorkflowConfigurationError(
                    f"{location} contains an unsupported runtime expression: "
                    f"{match.group(1)}"
                )
        return
    if isinstance(value, list):
        for item in value:
            _validate_renderable(item, location=location)
    elif isinstance(value, dict):
        for item in value.values():
            _validate_renderable(item, location=location)


def _selector(spec: dict[str, Any], context: RuntimeContext) -> Any:
    selector_type = spec.get("type")
    selector = spec.get("selector")
    source = spec.get("context")
    if not isinstance(source, str) or not isinstance(selector, str):
        raise WorkflowConfigurationError("Selector requires string context and selector")
    value = _resolve_expression(source, context)
    if selector_type == "jsonpointer":
        return _json_pointer(value, selector)
    if selector_type == "jsonpath":
        return _jsonpath(value, selector)
    raise WorkflowConfigurationError(f"Unsupported selector type: {selector_type}")


def _output_value(spec: Any, context: RuntimeContext) -> Any:
    if isinstance(spec, str):
        return _resolve_expression(spec, context)
    if isinstance(spec, dict):
        return _selector(spec, context)
    raise WorkflowConfigurationError("Step output must be an expression or selector")


def _literal(value: str, context: RuntimeContext) -> Any:
    value = value.strip()
    if EXPRESSION.fullmatch(value):
        return _resolve_expression(value, context)
    try:
        parsed = json.loads(value)
        return _render(parsed, context)
    except json.JSONDecodeError:
        return _render(value, context)


def _compare(actual: Any, operator: str, expected: Any) -> bool:
    if operator == "==":
        return actual == expected
    if operator == "!=":
        return actual != expected
    if operator in {">", ">=", "<", "<="}:
        if isinstance(actual, bool) or isinstance(expected, bool):
            return False
        if not isinstance(actual, (int, float)) or not isinstance(expected, (int, float)):
            return False
        return {
            ">": actual > expected,
            ">=": actual >= expected,
            "<": actual < expected,
            "<=": actual <= expected,
        }[operator]
    raise WorkflowConfigurationError(f"Unsupported criterion operator: {operator}")


def _criterion_passes(criterion: dict[str, Any], context: RuntimeContext) -> bool:
    criterion_type = criterion.get("type", "simple")
    condition = criterion.get("condition")
    if not isinstance(condition, str):
        raise WorkflowConfigurationError("Criterion condition must be a string")
    if criterion_type == "simple":
        match = SIMPLE_COMPARISON.fullmatch(condition)
        if match:
            try:
                actual = _literal(match.group(1), context)
                expected = _literal(match.group(3), context)
            except WorkflowError:
                return False
            return _compare(actual, match.group(2), expected)
        try:
            return bool(_literal(condition, context))
        except WorkflowError:
            return False
    if criterion_type == "regex":
        source = criterion.get("context")
        if not isinstance(source, str):
            raise WorkflowConfigurationError("Regex criterion requires context")
        try:
            value = _resolve_expression(source, context)
        except WorkflowError:
            return False
        return re.search(condition, str(value)) is not None
    if criterion_type == "jsonpath":
        source = criterion.get("context", "$response.body")
        if not isinstance(source, str):
            raise WorkflowConfigurationError("JSONPath criterion requires context")
        try:
            return bool(_jsonpath(_resolve_expression(source, context), condition))
        except WorkflowError:
            return False
    if criterion_type == "x-testkit-contains":
        source = criterion.get("context")
        if not isinstance(source, str):
            raise WorkflowConfigurationError("Contains criterion requires context")
        try:
            actual = _resolve_expression(source, context)
            expected = _literal(condition, context)
        except WorkflowError:
            return False
        if isinstance(actual, (list, tuple, set, dict)):
            return expected in actual
        return str(expected) in str(actual)
    if criterion_type == "x-testkit-exists":
        try:
            return _resolve_expression(condition, context) is not None
        except WorkflowError:
            return False
    raise WorkflowConfigurationError(f"Unsupported criterion type: {criterion_type}")


def _redact(value: Any, secrets: list[str]) -> Any:
    secret_values = sorted(
        {item for item in secrets if isinstance(item, str) and item},
        key=len,
        reverse=True,
    )
    if isinstance(value, str):
        for secret in secret_values:
            if value == secret:
                return "[REDACTED]"
            value = re.sub(
                rf"(?<![A-Za-z0-9]){re.escape(secret)}(?![A-Za-z0-9])",
                "[REDACTED]",
                value,
            )
        return value
    if isinstance(value, list):
        return [_redact(item, secret_values) for item in value]
    if isinstance(value, tuple):
        return [_redact(item, secret_values) for item in value]
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            name = str(key)
            if name in RESULT_METADATA_FIELDS and (
                isinstance(item, (str, int, float, bool, type(None)))
                or name == "output_names"
            ):
                redacted[name] = item
            else:
                redacted[name] = _redact(item, secret_values)
        return redacted
    return value


class WorkflowRunner:
    """Execute Arazzo workflows against one OpenAPI source."""

    def __init__(
        self,
        workflow_path: str | Path,
        *,
        base_url: str,
        transport: HttpTransport | None = None,
        schema_path: str | Path | None = None,
    ) -> None:
        self.workflow_path = Path(workflow_path).expanduser().resolve()
        self.document = _load_mapping(self.workflow_path)
        self._validate_document()
        self.workflows = {
            workflow["workflowId"]: workflow
            for workflow in self.document["workflows"]
        }
        self.base_url = self._validate_base_url(base_url)
        source_path = (
            Path(schema_path).expanduser().resolve()
            if schema_path
            else self._source_path()
        )
        self.schema_path = source_path
        self.schema = _load_mapping(source_path)
        self.operations = self._operation_index(self.schema)
        self.transport = transport or UrllibTransport()
        if not callable(getattr(self.transport, "reset", None)):
            raise WorkflowConfigurationError(
                "HTTP transport must implement reset() for isolated workflow sessions"
            )

    def _validate_document(self) -> None:
        version = str(self.document.get("arazzo", ""))
        if not ARAZZO_VERSION.fullmatch(version):
            raise WorkflowConfigurationError(
                "Expected an Arazzo 1.0.x or 1.1.x document"
            )
        sources = self.document.get("sourceDescriptions")
        workflows = self.document.get("workflows")
        if not isinstance(sources, list) or not sources:
            raise WorkflowConfigurationError("sourceDescriptions must be a non-empty list")
        if not isinstance(workflows, list) or not workflows:
            raise WorkflowConfigurationError("workflows must be a non-empty list")
        workflow_ids: set[str] = set()
        for index, workflow in enumerate(workflows):
            if not isinstance(workflow, dict):
                raise WorkflowConfigurationError(f"workflows[{index}] must be an object")
            workflow_id = workflow.get("workflowId")
            if not isinstance(workflow_id, str) or not workflow_id:
                raise WorkflowConfigurationError(
                    f"workflows[{index}].workflowId is required"
                )
            if workflow_id in workflow_ids:
                raise WorkflowConfigurationError(
                    f"Duplicate workflowId: {workflow_id}"
                )
            workflow_ids.add(workflow_id)
            for phase_name in ("x-testkit-setup", "x-testkit-cleanup"):
                phase = workflow.get(phase_name, [])
                if not isinstance(phase, list):
                    raise WorkflowConfigurationError(
                        f"Workflow {workflow_id} {phase_name} must be a list"
                    )
            steps = workflow.get("steps")
            if not isinstance(steps, list):
                raise WorkflowConfigurationError(
                    f"Workflow {workflow_id} steps must be a list"
                )
            if not isinstance(workflow.get("inputs", {}), dict):
                raise WorkflowConfigurationError(
                    f"Workflow {workflow_id} inputs must be an object"
                )
            if not isinstance(workflow.get("outputs", {}), dict):
                raise WorkflowConfigurationError(
                    f"Workflow {workflow_id} outputs must be an object"
                )
            for output_name, output_spec in workflow.get("outputs", {}).items():
                if not isinstance(output_name, str) or not output_name:
                    raise WorkflowConfigurationError(
                        f"Workflow {workflow_id} output names must be non-empty strings"
                    )
                self._validate_output_spec(
                    output_spec,
                    location=f"Workflow {workflow_id} output {output_name}",
                )
            if not isinstance(
                workflow.get("x-testkit-continue-on-failure", False), bool
            ):
                raise WorkflowConfigurationError(
                    f"Workflow {workflow_id} continue-on-failure must be boolean"
                )
            tags = workflow.get("x-testkit-tags", [])
            if not isinstance(tags, list) or not all(
                isinstance(tag, str) for tag in tags
            ):
                raise WorkflowConfigurationError(
                    f"Workflow {workflow_id} tags must be strings"
                )
            self._validate_steps(
                [*workflow.get("x-testkit-setup", []), *steps, *workflow.get("x-testkit-cleanup", [])],
                workflow_id,
            )

    def _validate_steps(self, steps: list[Any], workflow_id: str) -> None:
        seen: set[str] = set()
        for index, step in enumerate(steps):
            if not isinstance(step, dict):
                raise WorkflowConfigurationError(
                    f"{workflow_id} step {index} must be an object"
                )
            step_id = step.get("stepId")
            if not isinstance(step_id, str) or not re.fullmatch(
                r"[A-Za-z0-9_-]+", step_id
            ):
                raise WorkflowConfigurationError(
                    f"{workflow_id} step {index} has invalid stepId"
                )
            if step_id in seen:
                raise WorkflowConfigurationError(
                    f"Duplicate stepId in {workflow_id}: {step_id}"
                )
            seen.add(step_id)
            targets = [
                name
                for name in ("operationId", "operationPath", "workflowId")
                if step.get(name) is not None
            ]
            has_delay = step.get("x-testkit-delay-ms") is not None
            if "x-testkit-mutating" in step:
                raise WorkflowConfigurationError(
                    f"Step {step_id} cannot override method-based mutation safety"
                )
            if len(targets) != 1 and not (len(targets) == 0 and has_delay):
                raise WorkflowConfigurationError(
                    f"Step {step_id} requires one operationId, operationPath, "
                    "workflowId, or a standalone x-testkit-delay-ms"
                )
            if "operationPath" in targets:
                raise WorkflowConfigurationError(
                    f"operationPath is not supported yet; use operationId in {step_id}"
                )
            if targets:
                target = step[targets[0]]
                if not isinstance(target, str) or not target:
                    raise WorkflowConfigurationError(
                        f"Step {step_id} target must be a non-empty string"
                    )
            delay_ms = step.get("x-testkit-delay-ms")
            if has_delay and (
                not isinstance(delay_ms, (int, float))
                or isinstance(delay_ms, bool)
                or delay_ms < 0
                or delay_ms > 300000
            ):
                raise WorkflowConfigurationError(
                    f"Step {step_id} delay must be between 0 and 300000 milliseconds"
                )
            dependencies = step.get("dependsOn", [])
            if not isinstance(dependencies, list) or not all(
                isinstance(item, str) for item in dependencies
            ):
                raise WorkflowConfigurationError(
                    f"Step {step_id} dependsOn must be a list of step ids"
                )
            for dependency in dependencies:
                if dependency not in seen:
                    raise WorkflowConfigurationError(
                        f"Step {step_id} depends on an unavailable prior step: {dependency}"
                    )
            parameters = step.get("parameters", [])
            if not isinstance(parameters, list) or not all(
                isinstance(item, dict) for item in parameters
            ):
                raise WorkflowConfigurationError(
                    f"Step {step_id} parameters must be a list of objects"
                )
            for parameter in parameters:
                if not isinstance(parameter.get("name"), str) or not isinstance(
                    parameter.get("in"), str
                ):
                    raise WorkflowConfigurationError(
                        f"Step {step_id} parameter requires string name and in"
                    )
                _validate_renderable(
                    parameter.get("value"),
                    location=f"Step {step_id} parameter {parameter['name']}",
                )
            if step.get("requestBody") is not None and not isinstance(
                step["requestBody"], dict
            ):
                raise WorkflowConfigurationError(
                    f"Step {step_id} requestBody must be an object"
                )
            if isinstance(step.get("requestBody"), dict):
                _validate_renderable(
                    step["requestBody"].get("payload"),
                    location=f"Step {step_id} requestBody",
                )
            criteria = step.get("successCriteria", [])
            if not isinstance(criteria, list) or not all(
                isinstance(item, dict) for item in criteria
            ):
                raise WorkflowConfigurationError(
                    f"Step {step_id} successCriteria must be a list of objects"
                )
            for criterion in criteria:
                criterion_type = criterion.get("type", "simple")
                if criterion_type not in {
                    "simple",
                    "regex",
                    "jsonpath",
                    "x-testkit-contains",
                    "x-testkit-exists",
                }:
                    raise WorkflowConfigurationError(
                        f"Step {step_id} has unsupported criterion type: {criterion_type}"
                    )
                if not isinstance(criterion.get("condition"), str):
                    raise WorkflowConfigurationError(
                        f"Step {step_id} criterion condition must be a string"
                    )
                context_expression = criterion.get("context")
                if context_expression is not None and (
                    not isinstance(context_expression, str)
                    or not EXPRESSION.fullmatch(context_expression)
                ):
                    raise WorkflowConfigurationError(
                        f"Step {step_id} criterion context is invalid"
                    )
                condition = criterion["condition"]
                if criterion_type == "simple":
                    comparison = SIMPLE_COMPARISON.fullmatch(condition)
                    if comparison:
                        if not EXPRESSION.fullmatch(comparison.group(1).strip()):
                            raise WorkflowConfigurationError(
                                f"Step {step_id} comparison must start with a "
                                "supported runtime expression"
                            )
                    elif not EXPRESSION.fullmatch(condition.strip()):
                        raise WorkflowConfigurationError(
                            f"Step {step_id} simple criterion is invalid: {condition}"
                        )
                elif criterion_type in {"regex", "x-testkit-contains"}:
                    if context_expression is None:
                        raise WorkflowConfigurationError(
                            f"Step {step_id} {criterion_type} criterion requires context"
                        )
                    if criterion_type == "regex":
                        try:
                            re.compile(condition)
                        except re.error as exc:
                            raise WorkflowConfigurationError(
                                f"Step {step_id} regex criterion is invalid: {exc}"
                            ) from exc
                elif criterion_type == "jsonpath":
                    _jsonpath_tokens(condition)
                elif criterion_type == "x-testkit-exists" and not EXPRESSION.fullmatch(
                    condition
                ):
                    raise WorkflowConfigurationError(
                        f"Step {step_id} exists criterion requires a runtime expression"
                    )
            outputs = step.get("outputs", {})
            if not isinstance(outputs, dict):
                raise WorkflowConfigurationError(
                    f"Step {step_id} outputs must be an object"
                )
            for output_name, output_spec in outputs.items():
                if not isinstance(output_name, str) or not output_name:
                    raise WorkflowConfigurationError(
                        f"Step {step_id} output names must be non-empty strings"
                    )
                self._validate_output_spec(
                    output_spec,
                    location=f"Step {step_id} output {output_name}",
                )
            aliases = step.get("x-testkit-aliases", [])
            if not isinstance(aliases, list) or not all(
                isinstance(alias, str) and alias for alias in aliases
            ):
                raise WorkflowConfigurationError(
                    f"Step {step_id} aliases must be non-empty strings"
                )
            timeout = step.get("timeout", 30000)
            if (
                not isinstance(timeout, (int, float))
                or isinstance(timeout, bool)
                or timeout <= 0
                or timeout > 300000
            ):
                raise WorkflowConfigurationError(
                    f"Step {step_id} timeout must be between 1 and 300000 milliseconds"
                )

    @staticmethod
    def _validate_output_spec(spec: Any, *, location: str) -> None:
        if isinstance(spec, str):
            if not EXPRESSION.fullmatch(spec):
                raise WorkflowConfigurationError(
                    f"{location} must be a supported runtime expression"
                )
            if "#" in spec:
                _validate_json_pointer_syntax(
                    spec.split("#", 1)[1],
                    location=location,
                )
            return
        if not isinstance(spec, dict):
            raise WorkflowConfigurationError(
                f"{location} must be an expression or selector"
            )
        selector_type = spec.get("type")
        if selector_type not in {"jsonpointer", "jsonpath"}:
            raise WorkflowConfigurationError(
                f"{location} has unsupported selector type: {selector_type}"
            )
        if not isinstance(spec.get("context"), str) or not EXPRESSION.fullmatch(
            spec["context"]
        ):
            raise WorkflowConfigurationError(
                f"{location} selector context is invalid"
            )
        if "#" in spec["context"]:
            _validate_json_pointer_syntax(
                spec["context"].split("#", 1)[1],
                location=f"{location} context",
            )
        if not isinstance(spec.get("selector"), str):
            raise WorkflowConfigurationError(
                f"{location} selector must be a string"
            )
        selector = spec["selector"]
        if selector_type == "jsonpointer":
            _validate_json_pointer_syntax(selector, location=location)
        else:
            _jsonpath_tokens(selector)

    def _source_path(self) -> Path:
        openapi_sources = [
            source
            for source in self.document["sourceDescriptions"]
            if isinstance(source, dict) and source.get("type") == "openapi"
        ]
        if len(openapi_sources) != 1:
            raise WorkflowConfigurationError(
                "Exactly one local OpenAPI sourceDescription is required"
            )
        raw_url = openapi_sources[0].get("url")
        if not isinstance(raw_url, str) or not raw_url:
            raise WorkflowConfigurationError("OpenAPI sourceDescription.url is required")
        parsed = urllib.parse.urlsplit(raw_url)
        if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
            raise WorkflowConfigurationError(
                "sourceDescription.url must be a local path without query or fragment"
            )
        workflow_root = self.workflow_path.parent.resolve()
        source_path = (workflow_root / parsed.path).resolve()
        try:
            source_path.relative_to(workflow_root)
        except ValueError as exc:
            raise WorkflowConfigurationError(
                "OpenAPI sourceDescription.url must stay inside the workflow directory"
            ) from exc
        return source_path

    @staticmethod
    def _validate_base_url(value: str) -> str:
        parsed = urllib.parse.urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise WorkflowConfigurationError(
                "Base URL must be a credential-free absolute HTTP(S) URL"
            )
        return value.rstrip("/")

    @staticmethod
    def _operation_index(schema: dict[str, Any]) -> dict[str, Operation]:
        paths = schema.get("paths")
        if not isinstance(paths, dict):
            raise WorkflowConfigurationError("OpenAPI schema requires paths")
        operations: dict[str, Operation] = {}
        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue
            if not isinstance(path, str) or not path.startswith("/"):
                raise WorkflowConfigurationError(
                    f"OpenAPI path must start with '/': {path!r}"
                )
            for method, operation in path_item.items():
                if method.lower() not in {
                    "get",
                    "put",
                    "post",
                    "delete",
                    "options",
                    "head",
                    "patch",
                    "trace",
                } or not isinstance(operation, dict):
                    continue
                operation_id = operation.get("operationId")
                if not isinstance(operation_id, str) or not operation_id:
                    continue
                if operation_id in operations:
                    raise WorkflowConfigurationError(
                        f"Duplicate OpenAPI operationId: {operation_id}"
                    )
                operations[operation_id] = Operation(
                    operation_id=operation_id,
                    method=method.upper(),
                    path=str(path),
                    raw=operation,
                )
        return operations

    def _workflow_inputs(
        self,
        workflow: dict[str, Any],
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        schema = workflow.get("inputs") or {}
        if not isinstance(schema, dict):
            raise WorkflowConfigurationError(
                f"Workflow {workflow['workflowId']} inputs must be an object schema"
            )
        properties = schema.get("properties") or {}
        if not isinstance(properties, dict):
            raise WorkflowConfigurationError(
                f"Workflow {workflow['workflowId']} input properties must be an object"
            )
        merged = {
            name: spec["default"]
            for name, spec in properties.items()
            if isinstance(spec, dict) and "default" in spec
        }
        merged.update(inputs)
        required = schema.get("required") or []
        if not isinstance(required, list) or not all(
            isinstance(name, str) for name in required
        ):
            raise WorkflowConfigurationError(
                f"Workflow {workflow['workflowId']} required inputs must be strings"
            )
        missing = [
            name
            for name in required
            if name not in merged or merged[name] in (None, "")
        ]
        if missing:
            raise WorkflowConfigurationError(
                f"Missing required workflow inputs: {', '.join(missing)}"
            )
        return merged

    def _selected(
        self, workflow_ids: list[str], tags: list[str]
    ) -> list[dict[str, Any]]:
        selected = list(self.workflows.values())
        if workflow_ids:
            unknown = [item for item in workflow_ids if item not in self.workflows]
            if unknown:
                raise WorkflowConfigurationError(
                    f"Unknown workflowId: {', '.join(unknown)}"
                )
            selected = [self.workflows[item] for item in workflow_ids]
        if tags:
            requested = set(tags)
            selected = [
                item
                for item in selected
                if requested.issubset(set(item.get("x-testkit-tags", [])))
            ]
        if not selected:
            raise WorkflowConfigurationError("No workflows matched the selection")
        return selected

    def declared_output_names(self, workflow_id: str) -> set[str]:
        workflow = self.workflows.get(workflow_id)
        if workflow is None:
            raise WorkflowConfigurationError(f"Unknown workflowId: {workflow_id}")
        outputs = workflow.get("outputs") or {}
        if not isinstance(outputs, dict):
            raise WorkflowConfigurationError(
                f"Workflow {workflow_id} outputs must be an object"
            )
        return {str(name) for name in outputs}

    def _workflow_is_mutating(
        self,
        workflow: dict[str, Any],
        *,
        stack: tuple[str, ...] = (),
    ) -> bool:
        workflow_id = workflow["workflowId"]
        if workflow_id in stack:
            raise WorkflowConfigurationError(
                f"Recursive workflow reference: {' -> '.join((*stack, workflow_id))}"
            )
        steps = [
            *workflow.get("x-testkit-setup", []),
            *workflow.get("steps", []),
            *workflow.get("x-testkit-cleanup", []),
        ]
        for step in steps:
            if step.get("workflowId"):
                child_id = step["workflowId"]
                child = self.workflows.get(child_id)
                if child is None:
                    raise WorkflowConfigurationError(
                        f"Unknown referenced workflowId: {child_id}"
                    )
                if self._workflow_is_mutating(child, stack=(*stack, workflow_id)):
                    return True
                continue
            if step.get("x-testkit-delay-ms") is not None and not step.get(
                "operationId"
            ):
                continue
            operation_id = step.get("operationId")
            operation = self.operations.get(operation_id)
            if operation is None:
                raise WorkflowConfigurationError(
                    f"Unknown OpenAPI operationId: {operation_id}"
                )
            if operation.method not in SAFE_METHODS:
                return True
        return False

    def _validate_nested_input_bindings(
        self,
        workflow: dict[str, Any],
        available_inputs: dict[str, Any],
        *,
        stack: tuple[str, ...] = (),
    ) -> None:
        workflow_id = workflow["workflowId"]
        if workflow_id in stack:
            raise WorkflowConfigurationError(
                f"Recursive workflow reference: {' -> '.join((*stack, workflow_id))}"
            )
        for step in (
            *workflow.get("x-testkit-setup", []),
            *workflow.get("steps", []),
            *workflow.get("x-testkit-cleanup", []),
        ):
            child_id = step.get("workflowId")
            if not child_id:
                continue
            child = self.workflows.get(child_id)
            if child is None:
                raise WorkflowConfigurationError(
                    f"Unknown referenced workflowId: {child_id}"
                )
            parameter_names = {
                str(parameter["name"])
                for parameter in step.get("parameters", [])
            }
            candidate_inputs = {
                **available_inputs,
                **{name: "__runtime_value__" for name in parameter_names},
            }
            resolved = self._workflow_inputs(child, candidate_inputs)
            self._validate_nested_input_bindings(
                child,
                resolved,
                stack=(*stack, workflow_id),
            )

    def _request_parts(
        self,
        step: dict[str, Any],
        operation: Operation,
        context: RuntimeContext,
    ) -> tuple[str, dict[str, str], dict[str, object], object]:
        path = operation.path
        headers: dict[str, str] = {}
        query: dict[str, object] = {}
        cookies: dict[str, str] = {}
        for parameter in step.get("parameters", []):
            if not isinstance(parameter, dict):
                raise WorkflowConfigurationError("Step parameters must be objects")
            name = parameter.get("name")
            location = parameter.get("in")
            if not isinstance(name, str) or not isinstance(location, str):
                raise WorkflowConfigurationError("Parameter requires name and in")
            value = _render(parameter.get("value"), context)
            if location == "path":
                marker = "{" + name + "}"
                if marker not in path:
                    raise WorkflowConfigurationError(
                        f"Path parameter {name} is absent from {operation.path}"
                    )
                path = path.replace(
                    marker,
                    urllib.parse.quote(str(value), safe=""),
                )
            elif location == "query":
                _add_query_value(query, name, value)
            elif location == "querystring":
                if not isinstance(value, str):
                    raise WorkflowConfigurationError(
                        "querystring parameter must resolve to a string"
                    )
                for key, item in urllib.parse.parse_qsl(
                    value, keep_blank_values=True
                ):
                    _add_query_value(query, key, item)
            elif location == "header":
                if not HEADER_NAME.fullmatch(name):
                    raise WorkflowConfigurationError(
                        f"Invalid HTTP header name: {name}"
                    )
                if "\r" in str(value) or "\n" in str(value):
                    raise WorkflowConfigurationError(
                        f"HTTP header {name} contains a newline"
                    )
                headers[name] = str(value)
            elif location == "cookie":
                if any(character in str(value) for character in "\r\n;"):
                    raise WorkflowConfigurationError(
                        f"Cookie {name} contains an unsafe character"
                    )
                cookies[name] = str(value)
            else:
                raise WorkflowConfigurationError(
                    f"Unsupported parameter location: {location}"
                )
        if re.search(r"\{[^{}]+\}", path):
            raise WorkflowConfigurationError(
                f"Unresolved path parameters for {operation.operation_id}: {path}"
            )
        if cookies:
            headers["Cookie"] = "; ".join(
                f"{name}={value}" for name, value in cookies.items()
            )
        request_body = step.get("requestBody")
        body = None
        if request_body is not None:
            if not isinstance(request_body, dict):
                raise WorkflowConfigurationError("requestBody must be an object")
            body = _render(request_body.get("payload"), context)
            content_type = request_body.get("contentType")
            if content_type:
                headers["Content-Type"] = str(content_type)
        return f"{self.base_url}{path}", headers, query, body

    def _execute_step(
        self,
        step: dict[str, Any],
        *,
        phase: str,
        context: RuntimeContext,
        depth: int,
    ) -> dict[str, Any]:
        step_id = step["stepId"]
        if depth > MAX_WORKFLOW_DEPTH:
            raise WorkflowConfigurationError("Workflow call depth exceeded")
        delay_ms = float(step.get("x-testkit-delay-ms", 0))
        delay_started = time.monotonic()
        if delay_ms:
            time.sleep(delay_ms / 1000)
        if step.get("x-testkit-delay-ms") is not None and not any(
            step.get(name) is not None
            for name in ("operationId", "operationPath", "workflowId")
        ):
            return {
                "phase": phase,
                "step_id": step_id,
                "status": "passed",
                "duration_ms": round((time.monotonic() - delay_started) * 1000, 3),
            }
        if step.get("workflowId"):
            child_id = step["workflowId"]
            child = self.workflows.get(child_id)
            if child is None:
                raise WorkflowConfigurationError(
                    f"Unknown referenced workflowId: {child_id}"
                )
            child_inputs = {
                str(item["name"]): _render(item.get("value"), context)
                for item in step.get("parameters", [])
                if isinstance(item, dict) and item.get("name")
            }
            inherited_inputs = {**context.inputs, **child_inputs}
            child_result, child_outputs = self._execute_workflow(
                child,
                inputs=inherited_inputs,
                secrets=context.secret_values,
                depth=depth + 1,
            )
            context.step_outputs[step_id] = child_outputs
            context.outputs.update(child_outputs)
            return {
                "phase": phase,
                "step_id": step_id,
                "workflow_id": child_id,
                "status": child_result["status"],
                "duration_ms": round(
                    (time.monotonic() - delay_started) * 1000,
                    3,
                ),
                "output_names": sorted(child_outputs),
                "children": child_result["steps"],
                **(
                    {"error_type": child_result["error_type"]}
                    if child_result.get("error_type")
                    else {}
                ),
                **(
                    {"error": child_result["error"]}
                    if child_result.get("error")
                    else {}
                ),
            }

        operation_id = step["operationId"]
        operation = self.operations.get(operation_id)
        if operation is None:
            raise WorkflowConfigurationError(
                f"Unknown OpenAPI operationId: {operation_id}"
            )
        try:
            url, headers, query, body = self._request_parts(step, operation, context)
        except WorkflowConfigurationError:
            raise
        except WorkflowError as exc:
            return {
                "phase": phase,
                "step_id": step_id,
                "operation_id": operation_id,
                "method": operation.method,
                "path": operation.path,
                "status": "failed",
                "error": str(exc),
            }
        context.url = url
        context.method = operation.method
        timeout_ms = step.get("timeout", 30000)
        if (
            not isinstance(timeout_ms, (int, float))
            or isinstance(timeout_ms, bool)
            or timeout_ms <= 0
            or timeout_ms > 300000
        ):
            raise WorkflowConfigurationError(
                f"Step {step_id} timeout must be between 1 and 300000 milliseconds"
            )
        started = time.monotonic()
        try:
            response = self.transport.request(
                method=operation.method,
                url=url,
                headers=headers,
                query=query,
                body=body,
                timeout=float(timeout_ms) / 1000,
            )
        except WorkflowTransportError as exc:
            return {
                "phase": phase,
                "step_id": step_id,
                "operation_id": operation_id,
                "method": operation.method,
                "path": operation.path,
                "status": "error",
                "error_type": "transport",
                "error": str(exc),
                "duration_ms": round(
                    (time.monotonic() - started) * 1000,
                    3,
                ),
            }
        elapsed_ms = round((time.monotonic() - started) * 1000, 3)
        context.response = response
        output_values: dict[str, Any] = {}
        failed_criteria: list[str] = []
        runtime_error: str | None = None
        try:
            for name, output_spec in (step.get("outputs") or {}).items():
                output_values[str(name)] = _output_value(output_spec, context)
            context.step_outputs[step_id] = output_values
            for alias in step.get("x-testkit-aliases", []):
                if not isinstance(alias, str) or not alias:
                    raise WorkflowConfigurationError(
                        f"Step {step_id} aliases must be non-empty strings"
                    )
                context.step_outputs[alias] = output_values
            context.outputs.update(output_values)
            context.secret_values.extend(
                value for value in output_values.values() if isinstance(value, str)
            )
            failed_criteria = [
                str(criterion.get("condition"))
                for criterion in step.get("successCriteria", [])
                if not _criterion_passes(criterion, context)
            ]
        except WorkflowConfigurationError:
            raise
        except WorkflowError as exc:
            runtime_error = str(exc)
        result: dict[str, Any] = {
            "phase": phase,
            "step_id": step_id,
            "operation_id": operation_id,
            "method": operation.method,
            "path": operation.path,
            "status": "failed" if failed_criteria or runtime_error else "passed",
            "status_code": response.status_code,
            "duration_ms": elapsed_ms,
            "output_names": sorted(output_values),
        }
        if runtime_error:
            result["error"] = runtime_error
        elif failed_criteria:
            result["error"] = (
                "Success criteria failed: " + ", ".join(failed_criteria)
            )
        return result

    def _execute_workflow(
        self,
        workflow: dict[str, Any],
        *,
        inputs: dict[str, Any],
        secrets: list[str],
        depth: int = 0,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        resolved_inputs = self._workflow_inputs(workflow, inputs)
        context = RuntimeContext(
            inputs=resolved_inputs,
            secret_values=secrets,
        )
        results: list[dict[str, Any]] = []
        failure: str | None = None
        transport_error: WorkflowTransportError | None = None
        try:
            for phase, steps in (
                ("setup", workflow.get("x-testkit-setup", [])),
                ("steps", workflow.get("steps", [])),
            ):
                for step in steps:
                    result = self._execute_step(
                        step,
                        phase=phase,
                        context=context,
                        depth=depth,
                    )
                    results.append(result)
                    if result["status"] == "error":
                        failure = str(result.get("error") or "Step execution error")
                        transport_error = WorkflowTransportError(failure)
                        break
                    continue_after_failure = (
                        phase == "steps"
                        and workflow.get("x-testkit-continue-on-failure", False)
                    )
                    if (
                        result["status"] != "passed"
                        and not continue_after_failure
                    ):
                        failure = str(result.get("error") or "Step failed")
                        break
                    if result["status"] != "passed" and failure is None:
                        failure = str(result.get("error") or "Step failed")
                if failure and phase == "setup":
                    break
        except WorkflowTransportError as exc:
            failure = str(exc)
            transport_error = exc
        finally:
            for step in workflow.get("x-testkit-cleanup", []):
                try:
                    result = self._execute_step(
                        step,
                        phase="cleanup",
                        context=context,
                        depth=depth,
                    )
                except WorkflowTransportError as exc:
                    transport_error = transport_error or exc
                    result = {
                        "phase": "cleanup",
                        "step_id": step.get("stepId", "unknown"),
                        "status": "failed",
                        "error": str(exc),
                    }
                except WorkflowError as exc:
                    result = {
                        "phase": "cleanup",
                        "step_id": step.get("stepId", "unknown"),
                        "status": "failed",
                        "error": str(exc),
                    }
                results.append(result)
                if (
                    result["status"] == "error"
                    and result.get("error_type") == "transport"
                    and transport_error is None
                ):
                    transport_error = WorkflowTransportError(
                        str(result.get("error") or "Cleanup transport error")
                    )
                if result["status"] != "passed" and failure is None:
                    failure = str(result.get("error") or "Cleanup failed")

        if transport_error is not None:
            return (
                {
                    "workflow_id": workflow["workflowId"],
                    "status": "error",
                    "error_type": "transport",
                    "error": str(transport_error),
                    "steps": results,
                },
                {},
            )
        workflow_outputs: dict[str, Any] = {}
        try:
            for name, expression in (workflow.get("outputs") or {}).items():
                workflow_outputs[str(name)] = _output_value(expression, context)
        except WorkflowConfigurationError:
            raise
        except WorkflowError as exc:
            failure = failure or f"Workflow output evaluation failed: {exc}"
        result = {
            "workflow_id": workflow["workflowId"],
            "status": "failed" if failure else "passed",
            "steps": results,
            **({"error": failure} if failure else {}),
        }
        return result, workflow_outputs

    def run(
        self,
        *,
        workflow_ids: list[str] | None = None,
        tags: list[str] | None = None,
        inputs: dict[str, Any] | None = None,
        datasets: list[dict[str, Any]] | None = None,
        secret_values: list[str] | None = None,
        allow_mutating_target: bool = False,
        output_sink: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        selected = self._selected(workflow_ids or [], tags or [])
        base_inputs = dict(inputs or {})
        data_rows = datasets if datasets is not None else [{}]
        if not data_rows:
            raise WorkflowConfigurationError("Datasets must not be empty")
        if output_sink is not None and (
            len(selected) != 1 or len(data_rows) != 1
        ):
            raise WorkflowConfigurationError(
                "Output capture requires exactly one workflow and one dataset"
            )
        for workflow in selected:
            for row in data_rows:
                if not isinstance(row, dict):
                    raise WorkflowConfigurationError(
                        "Each dataset row must be an object"
                    )
                resolved_inputs = self._workflow_inputs(
                    workflow,
                    {**base_inputs, **row},
                )
                self._validate_nested_input_bindings(
                    workflow,
                    resolved_inputs,
                )
            if (
                self._workflow_is_mutating(workflow)
                and not allow_mutating_target
            ):
                raise WorkflowConfigurationError(
                    "Workflow contains mutating operations; confirm an isolated "
                    "non-production target with --allow-mutating-target"
                )
        runs: list[dict[str, Any]] = []
        secrets = list(secret_values or [])
        for dataset_index, row in enumerate(data_rows):
            for workflow in selected:
                self.transport.reset()
                result, workflow_outputs = self._execute_workflow(
                    workflow,
                    inputs={**base_inputs, **row},
                    secrets=secrets,
                )
                if datasets:
                    result["dataset_index"] = dataset_index
                runs.append(result)
                if output_sink is not None:
                    output_sink.update(workflow_outputs)
        passed = sum(run["status"] == "passed" for run in runs)
        errors = sum(run["status"] == "error" for run in runs)
        failed = len(runs) - passed - errors
        payload = {
            "schema_version": 1,
            "runner": "testkit-arazzo",
            "status": (
                "error"
                if errors
                else "passed"
                if passed == len(runs)
                else "failed"
            ),
            "summary": {
                "total": len(runs),
                "passed": passed,
                "failed": failed,
                "errors": errors,
            },
            "runs": runs,
        }
        return _redact(payload, secrets)
