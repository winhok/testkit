#!/usr/bin/env python3
"""Statically discover HTTP routes and emit an OpenAPI 3.1 skeleton."""
from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCANNER_VERSION = "static-scan-v1"
SOURCE_SUFFIXES = {".java", ".py", ".go", ".js", ".ts", ".mjs", ".mts"}
SKIP_DIRS = {
    ".git",
    ".idea",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    ".vscode",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "target",
    "vendor",
}
STANDARD_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}


@dataclass(slots=True)
class Endpoint:
    path: str
    method: str
    file: str
    line: int
    framework: str


@dataclass(slots=True)
class CodeScanResult:
    document: dict[str, Any]
    source: str
    source_sha256: str
    warnings: list[str]
    unsupported_features: list[str]


class CodeScanError(ValueError):
    """Raised when a source tree cannot be scanned safely."""


_SPRING_MAPPING = re.compile(
    r"@(Get|Post|Put|Delete|Patch|Request)Mapping\s*\(\s*"
    r'(?:value\s*=\s*)?["\']([^"\']*)["\']',
    re.IGNORECASE,
)
_SPRING_PREFIX = re.compile(
    r'@RequestMapping\s*\(\s*(?:value\s*=\s*)?["\']([^"\']*)["\']',
    re.IGNORECASE,
)
_FASTAPI = re.compile(
    r'@([A-Za-z_][A-Za-z0-9_]*)\.(get|post|put|delete|patch|head|options)'
    r'\s*\(\s*["\']([^"\']+)["\']'
)
_FASTAPI_PREFIX = re.compile(
    r'([A-Za-z_][A-Za-z0-9_]*)\s*=\s*APIRouter\s*'
    r'\([^)]*prefix\s*=\s*["\']([^"\']+)["\']'
)
_FLASK = re.compile(
    r'@(?:app|blueprint|bp)\.(route|get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']'
)
_DJANGO_URL = re.compile(r"""(?:path|re_path)\s*\(\s*['"]([^'"]+)['"]""")
_GIN = re.compile(
    r'\b([A-Za-z_][A-Za-z0-9_]*)\.\s*'
    r'(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s*\(\s*["\']([^"\']+)["\']'
)
_GIN_PREFIX = re.compile(
    r'([A-Za-z_][A-Za-z0-9_]*)\s*:?=\s*[A-Za-z_][A-Za-z0-9_]*'
    r'\.Group\s*\(\s*["\']([^"\']+)["\']'
)
_NET_HTTP = re.compile(r'(?:HandleFunc|Handle)\s*\(\s*["\']([^"\']+)["\']')
_EXPRESS = re.compile(
    r'\b([A-Za-z_][A-Za-z0-9_]*)\.(get|post|put|delete|patch|head|options|all)'
    r'\s*\(\s*["\']([^"\']+)["\']'
)
_EXPRESS_PREFIX = re.compile(
    r'[A-Za-z_][A-Za-z0-9_]*\.\s*use\s*\(\s*["\']([^"\']+)["\']\s*,\s*'
    r'([A-Za-z_][A-Za-z0-9_]*)'
)
_NESTJS = re.compile(
    r'@(Get|Post|Put|Delete|Patch|Head|Options)\s*'
    r'\(\s*["\']?([^"\')\s]*)["\']?\s*\)',
    re.IGNORECASE,
)
_NESTJS_PREFIX = re.compile(r'@Controller\s*\(\s*["\']([^"\']*)["\']', re.IGNORECASE)
_KOA = re.compile(
    r'router\.(get|post|put|delete|patch|head|options|all)\s*'
    r'\(\s*["\']([^"\']+)["\']'
)


def _join_paths(*parts: str) -> str:
    joined = "/".join(part.strip("/") for part in parts if part and part.strip("/"))
    return "/" + joined if joined else "/"


def _openapi_path(path: str) -> str:
    normalized = path if path.startswith("/") else f"/{path}"
    normalized = re.sub(r":([A-Za-z_][A-Za-z0-9_]*)", r"{\1}", normalized)
    normalized = re.sub(
        r"<(?:(?:str|int|slug|uuid|path):)?([A-Za-z_][A-Za-z0-9_]*)>",
        r"{\1}",
        normalized,
    )
    return normalized or "/"


def _prefixes(content: str, pattern: re.Pattern[str]) -> list[str]:
    return list(dict.fromkeys(match.group(1) for match in pattern.finditer(content)))


def _variable_prefixes(
    content: str,
    pattern: re.Pattern[str],
    *,
    reverse_groups: bool = False,
) -> dict[str, str]:
    prefixes: dict[str, str] = {}
    ambiguous: set[str] = set()
    for match in pattern.finditer(content):
        variable, prefix = (
            (match.group(2), match.group(1))
            if reverse_groups
            else (match.group(1), match.group(2))
        )
        if variable in prefixes and prefixes[variable] != prefix:
            ambiguous.add(variable)
        else:
            prefixes[variable] = prefix
    for variable in ambiguous:
        prefixes.pop(variable, None)
    return prefixes


def _spring_class_prefixes(lines: list[str]) -> tuple[list[str], set[int]]:
    prefixes: list[str] = []
    annotation_lines: set[int] = set()
    for index, line in enumerate(lines):
        match = _SPRING_PREFIX.search(line)
        if not match:
            continue
        declaration_window = "\n".join(lines[index : index + 4])
        if re.search(r"\b(?:class|interface)\s+[A-Za-z_]", declaration_window):
            prefixes.append(match.group(1))
            annotation_lines.add(index + 1)
    return list(dict.fromkeys(prefixes)), annotation_lines


def _scan_file(relative_path: Path, content: str) -> tuple[list[Endpoint], list[str]]:
    suffix = relative_path.suffix.lower()
    lines = content.splitlines()
    warnings: list[str] = []
    patterns: list[tuple[re.Pattern[str], str, bool, str]] = []

    if suffix == ".java":
        patterns = [(_SPRING_MAPPING, "spring", True, "spring")]
    elif suffix == ".py":
        patterns = [(_FASTAPI, "fastapi", True, "fastapi")]
        if ".route(" in content or re.search(r"\b(?:Flask|Blueprint)\b", content):
            patterns.append((_FLASK, "flask", True, ""))
        patterns.append((_DJANGO_URL, "django", False, ""))
    elif suffix == ".go":
        patterns = [
            (_GIN, "gin", True, "gin"),
            (_NET_HTTP, "net/http", False, ""),
        ]
    elif suffix in {".js", ".ts", ".mjs", ".mts"}:
        patterns = [
            (_EXPRESS, "express", True, "express"),
            (_NESTJS, "nestjs", True, "nestjs"),
            (_KOA, "koa", True, ""),
        ]

    variable_prefixes = {
        "fastapi": _variable_prefixes(content, _FASTAPI_PREFIX),
        "gin": _variable_prefixes(content, _GIN_PREFIX),
        "express": _variable_prefixes(
            content, _EXPRESS_PREFIX, reverse_groups=True
        ),
    }
    prefix_patterns = {"nestjs": _NESTJS_PREFIX}
    prefix_cache: dict[str, str] = {}
    spring_prefixes, spring_annotation_lines = _spring_class_prefixes(lines)
    prefix_cache["spring"] = spring_prefixes[0] if len(spring_prefixes) == 1 else ""
    if len(spring_prefixes) > 1:
        warnings.append(
            f"{relative_path.as_posix()}: multiple spring class route prefixes; "
            "prefix composition was omitted"
        )
    for key, pattern in prefix_patterns.items():
        matches = _prefixes(content, pattern)
        prefix_cache[key] = matches[0] if len(matches) == 1 else ""
        if len(matches) > 1:
            warnings.append(
                f"{relative_path.as_posix()}: multiple {key} route prefixes; "
                "prefix composition was omitted"
            )

    endpoints: list[Endpoint] = []
    seen: set[tuple[str, str, int, str]] = set()
    for line_number, line in enumerate(lines, 1):
        for pattern, framework, has_method, prefix_key in patterns:
            for match in pattern.finditer(line):
                if framework == "spring" and line_number in spring_annotation_lines:
                    continue
                if has_method:
                    if framework in variable_prefixes:
                        receiver = match.group(1)
                        method = match.group(2).upper()
                        route = match.group(3)
                    else:
                        receiver = ""
                        method = match.group(1).upper()
                        route = match.group(2)
                    if framework == "spring" and method == "REQUEST":
                        method = "ANY"
                    elif framework == "flask" and method == "ROUTE":
                        method = "ANY"
                else:
                    method = "ANY"
                    route = match.group(1)
                    receiver = ""
                prefix = (
                    variable_prefixes[framework].get(receiver, "")
                    if framework in variable_prefixes
                    else prefix_cache.get(prefix_key, "")
                )
                full_path = _openapi_path(_join_paths(prefix, route) if prefix else route)
                key = (full_path, method, line_number, framework)
                if key in seen:
                    continue
                seen.add(key)
                endpoints.append(
                    Endpoint(
                        path=full_path,
                        method=method,
                        file=relative_path.as_posix(),
                        line=line_number,
                        framework=framework,
                    )
                )
    return endpoints, warnings


def _iter_source_files(root: Path, max_files: int) -> list[Path]:
    files: list[Path] = []
    for directory, dirnames, filenames in os.walk(root, followlinks=False):
        directory_path = Path(directory)
        dirnames[:] = sorted(
            name
            for name in dirnames
            if name not in SKIP_DIRS and not (directory_path / name).is_symlink()
        )
        for filename in sorted(filenames):
            path = directory_path / filename
            if path.is_symlink() or path.suffix.lower() not in SOURCE_SUFFIXES:
                continue
            files.append(path)
            if len(files) > max_files:
                raise CodeScanError(
                    f"Code root contains more than {max_files} supported source files; "
                    "raise --code-max-files explicitly to scan it"
                )
    return files


def _operation_id(method: str, path: str, used: set[str]) -> str:
    base = re.sub(r"[^A-Za-z0-9]+", "_", f"{method}_{path}").strip("_") or method.lower()
    candidate = base.lower()
    suffix = 2
    while candidate in used:
        candidate = f"{base.lower()}_{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def _path_parameters(path: str) -> list[dict[str, Any]]:
    return [
        {
            "name": name,
            "in": "path",
            "required": True,
            "schema": {"type": "string"},
            "description": "Discovered from a source route; type was not inferred.",
        }
        for name in re.findall(r"\{([^{}]+)\}", path)
    ]


def scan_code_source(
    root: str | Path,
    *,
    url_prefix: str | None = None,
    max_files: int = 5000,
    max_bytes: int = 50 * 1024 * 1024,
) -> CodeScanResult:
    """Scan a local source tree without importing or executing application code."""
    requested_root = Path(root).expanduser()
    if requested_root.is_symlink():
        raise CodeScanError(f"Code root cannot be a symlink: {requested_root}")
    source_root = requested_root.resolve()
    if not source_root.is_dir():
        raise CodeScanError(f"Code root is not a directory: {source_root}")
    if max_files < 1 or max_bytes < 1:
        raise CodeScanError("Code scan limits must be positive")

    files = _iter_source_files(source_root, max_files)

    digest = hashlib.sha256()
    total_bytes = 0
    endpoints: list[Endpoint] = []
    warnings: list[str] = []
    for path in files:
        try:
            size = path.stat().st_size
            if total_bytes + size > max_bytes:
                raise CodeScanError(
                    f"Code scan exceeds the {max_bytes} byte limit; "
                    "raise --code-max-bytes explicitly"
                )
            raw = path.read_bytes()
        except OSError as exc:
            warnings.append(
                f"{path.relative_to(source_root).as_posix()}: unable to read source file: {exc}"
            )
            continue
        total_bytes += len(raw)
        if total_bytes > max_bytes:
            raise CodeScanError(
                f"Code scan exceeds the {max_bytes} byte limit; raise --code-max-bytes explicitly"
            )
        relative = path.relative_to(source_root)
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(raw)
        digest.update(b"\0")
        content = raw.decode("utf-8", errors="replace")
        discovered, file_warnings = _scan_file(relative, content)
        endpoints.extend(discovered)
        warnings.extend(file_warnings)

    prefixes = [
        _openapi_path(value.strip().rstrip("*"))
        for value in (url_prefix or "").split(",")
        if value.strip()
    ]
    if prefixes:
        endpoints = [
            endpoint
            for endpoint in endpoints
            if any(
                prefix == "/"
                or endpoint.path == prefix
                or endpoint.path.startswith(prefix.rstrip("/") + "/")
                for prefix in prefixes
            )
        ]

    document: dict[str, Any] = {
        "openapi": "3.1.0",
        "info": {
            "title": f"Discovered API surface: {source_root.name}",
            "version": SCANNER_VERSION,
            "description": (
                "Static source scan skeleton. Request and response contracts require review."
            ),
        },
        "paths": {},
    }
    unsupported = {
        "Dynamic or computed route paths",
        "Request and response schemas inferred from DTOs or application code",
        "Middleware- or decorator-driven authentication and authorization",
        "Cross-file router mounts and runtime route composition",
    }
    used_ids: set[str] = set()
    for endpoint in sorted(
        endpoints, key=lambda item: (item.path, item.method, item.file, item.line)
    ):
        method = endpoint.method.lower()
        if method not in STANDARD_METHODS:
            unsupported.add(
                f"{endpoint.framework} ANY-method route at "
                f"{endpoint.file}:{endpoint.line} ({endpoint.path})"
            )
            continue
        path_item = document["paths"].setdefault(endpoint.path, {})
        if method in path_item:
            warnings.append(
                f"Duplicate discovered route {endpoint.method} {endpoint.path} at "
                f"{endpoint.file}:{endpoint.line}; later route was skipped"
            )
            continue
        operation: dict[str, Any] = {
            "operationId": _operation_id(method, endpoint.path, used_ids),
            "summary": f"Discovered {endpoint.method} {endpoint.path}",
            "responses": {
                "default": {
                    "description": "Response contract was not inferred from source code."
                }
            },
            "x-source-file": endpoint.file,
            "x-source-line": endpoint.line,
            "x-source-framework": endpoint.framework,
            "x-discovery-confidence": "heuristic",
        }
        parameters = _path_parameters(endpoint.path)
        if parameters:
            operation["parameters"] = parameters
        path_item[method] = operation

    warnings.insert(
        0,
        "Static source scanning is heuristic; review every discovered route before execution.",
    )
    if not files:
        warnings.append("No supported source files were found under the code root.")
    elif not document["paths"]:
        warnings.append("No statically recognizable HTTP operations were found.")
    return CodeScanResult(
        document=document,
        source=str(source_root),
        source_sha256=digest.hexdigest(),
        warnings=list(dict.fromkeys(warnings)),
        unsupported_features=sorted(unsupported),
    )
