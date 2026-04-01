#!/usr/bin/env python3
"""Lightweight HTTP endpoint scanner for common backend frameworks.

Walks source files and extracts route definitions via regex patterns.
Produces Markdown or JSON output.

Supported frameworks:
  - Java Spring MVC / Spring Boot  (@GetMapping, @PostMapping, @RequestMapping, etc.)
    Merges class-level @RequestMapping prefix with method-level route.
  - Python FastAPI / Flask / Django  (@app.get, @router.post, url_patterns, etc.)
    Merges FastAPI APIRouter prefix.
  - Go Gin / net/http  (r.GET, http.HandleFunc, etc.)
    Merges Gin r.Group() prefix.
  - Node.js Express / Koa / NestJS  (router.get, @Get, etc.)
    Merges NestJS @Controller() prefix and Express app.use() mount prefix.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Endpoint model
# ---------------------------------------------------------------------------

@dataclass
class Endpoint:
    path: str
    method: str
    handler: str = ""
    file: str = ""
    line: int = 0
    summary: str = ""
    framework: str = ""


# ---------------------------------------------------------------------------
# Framework-specific patterns
# ---------------------------------------------------------------------------

_SPRING_MAPPING = re.compile(
    r'@(Get|Post|Put|Delete|Patch|Request)Mapping\s*\(\s*(?:value\s*=\s*)?["\']([^"\']+)["\']',
    re.IGNORECASE,
)
_SPRING_CLASS_PREFIX = re.compile(
    r'@RequestMapping\s*\(\s*(?:value\s*=\s*)?["\']([^"\']+)["\']',
    re.IGNORECASE,
)
_SPRING_METHOD = {"get": "GET", "post": "POST", "put": "PUT", "delete": "DELETE", "patch": "PATCH", "request": "ANY"}

_FASTAPI = re.compile(
    r'@(?:app|router)\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']',
)
_FASTAPI_PREFIX = re.compile(
    r'APIRouter\s*\([^)]*prefix\s*=\s*["\']([^"\']+)["\']',
)

_FLASK = re.compile(
    r'@(?:app|blueprint|bp)\.(route|get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']',
)

_DJANGO_URL = re.compile(
    r"""(?:path|re_path)\s*\(\s*['\"]([^'\"]+)['\"]""",
)

_GIN = re.compile(
    r'\.\s*(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s*\(\s*["\']([^"\']+)["\']',
)
_GIN_GROUP = re.compile(
    r'\.Group\s*\(\s*["\']([^"\']+)["\']',
)

_NET_HTTP = re.compile(
    r'(?:HandleFunc|Handle)\s*\(\s*["\']([^"\']+)["\']',
)

_EXPRESS = re.compile(
    r'(?:app|router)\.(get|post|put|delete|patch|all)\s*\(\s*["\']([^"\']+)["\']',
)
_EXPRESS_USE = re.compile(
    r'(?:app)\.\s*use\s*\(\s*["\']([^"\']+)["\']',
)

_NESTJS = re.compile(
    r'@(Get|Post|Put|Delete|Patch)\s*\(\s*["\']?([^"\')\s]*)["\']?\s*\)',
    re.IGNORECASE,
)
_NESTJS_CONTROLLER = re.compile(
    r'@Controller\s*\(\s*["\']([^"\']*)["\']',
    re.IGNORECASE,
)

_KOA = re.compile(
    r'router\.(get|post|put|delete|patch|all)\s*\(\s*["\']([^"\']+)["\']',
)


def _join_paths(*parts: str) -> str:
    """Join URL path segments, normalising slashes."""
    joined = "/".join(p.strip("/") for p in parts if p and p.strip("/"))
    return "/" + joined if joined else "/"


def _find_class_prefix(lines: list[str], framework: str) -> tuple[str, int]:
    """Scan for a class/controller-level route prefix.

    Returns (prefix, line_number).  line_number is 1-based; 0 means not found.
    """
    if framework == "spring":
        pat = _SPRING_CLASS_PREFIX
    elif framework == "nestjs":
        pat = _NESTJS_CONTROLLER
    elif framework == "fastapi":
        pat = _FASTAPI_PREFIX
    elif framework == "gin":
        pat = _GIN_GROUP
    elif framework == "express":
        pat = _EXPRESS_USE
    else:
        return "", 0
    for idx, line in enumerate(lines):
        m = pat.search(line)
        if m:
            return m.group(1), idx + 1
    return "", 0


def _scan_file(path: Path, content: str) -> list[Endpoint]:
    endpoints: list[Endpoint] = []
    suffix = path.suffix.lower()

    patterns: list[tuple[re.Pattern, str, bool]] = []

    if suffix == ".java":
        patterns.append((_SPRING_MAPPING, "spring", True))
    elif suffix == ".py":
        patterns.append((_FASTAPI, "fastapi", True))
        patterns.append((_FLASK, "flask", True))
        patterns.append((_DJANGO_URL, "django", False))
    elif suffix == ".go":
        patterns.append((_GIN, "gin", True))
        patterns.append((_NET_HTTP, "net/http", False))
    elif suffix in {".js", ".ts", ".mjs", ".mts"}:
        patterns.append((_EXPRESS, "express", True))
        patterns.append((_NESTJS, "nestjs", True))
        patterns.append((_KOA, "koa", True))

    if not patterns:
        return endpoints

    lines = content.splitlines()

    prefix_cache: dict[str, tuple[str, int]] = {}
    for _, fw, _ in patterns:
        if fw not in prefix_cache:
            prefix_cache[fw] = _find_class_prefix(lines, fw)

    for lineno, line in enumerate(lines, 1):
        for pat, framework, has_method in patterns:
            class_prefix, prefix_lineno = prefix_cache.get(framework, ("", 0))
            if prefix_lineno == lineno:
                continue

            for m in pat.finditer(line):
                if has_method:
                    raw_method = m.group(1).upper()
                    route = m.group(2)
                    method = _SPRING_METHOD.get(raw_method.lower(), raw_method) if framework == "spring" else raw_method
                else:
                    route = m.group(1)
                    method = "ANY"

                full_path = _join_paths(class_prefix, route) if class_prefix else route

                endpoints.append(Endpoint(
                    path=full_path, method=method, file=str(path), line=lineno, framework=framework,
                ))
    return endpoints


# ---------------------------------------------------------------------------
# Directory walker
# ---------------------------------------------------------------------------

_SOURCE_SUFFIXES = {".java", ".py", ".go", ".js", ".ts", ".mjs", ".mts"}
_SKIP_DIRS = {"node_modules", ".git", "__pycache__", "vendor", "build", "dist", "target", ".idea", ".vscode"}


def scan_directory(root: Path, url_prefix: str | None = None) -> list[Endpoint]:
    results: list[Endpoint] = []
    for path in sorted(root.rglob("*")):
        if path.is_dir():
            continue
        if any(skip in path.parts for skip in _SKIP_DIRS):
            continue
        if path.suffix.lower() not in _SOURCE_SUFFIXES:
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        results.extend(_scan_file(path.relative_to(root.parent) if root.parent != root else path, content))

    if url_prefix:
        prefixes = [p.strip().rstrip("*") for p in url_prefix.split(",")]
        results = [e for e in results if any(e.path.startswith(p) for p in prefixes)]

    return results


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------

def to_markdown(endpoints: list[Endpoint], scan_root: str) -> str:
    lines = [f"# API Surface Scan\n", f"扫描范围: `{scan_root}`\n", f"共发现 **{len(endpoints)}** 个 HTTP 端点。\n"]
    by_framework: dict[str, list[Endpoint]] = {}
    for ep in endpoints:
        by_framework.setdefault(ep.framework or "unknown", []).append(ep)

    for fw, eps in sorted(by_framework.items()):
        lines.append(f"\n## {fw} ({len(eps)} endpoints)\n")
        lines.append("| Method | Path | File | Line |")
        lines.append("|--------|------|------|------|")
        for ep in eps:
            lines.append(f"| {ep.method} | `{ep.path}` | `{ep.file}` | {ep.line} |")
    return "\n".join(lines) + "\n"


def to_json(endpoints: list[Endpoint]) -> str:
    return json.dumps([asdict(e) for e in endpoints], ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Scan backend source code for HTTP endpoints")
    parser.add_argument("root", help="Directory to scan")
    parser.add_argument("--output", "-o", help="Output file path (default: stdout)")
    parser.add_argument("--format", "-f", choices=["md", "json"], default="md", help="Output format")
    parser.add_argument("--prefix", "-p", help="Filter by URL prefix (comma-separated)")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"Not a directory: {root}", file=sys.stderr)
        return 1

    endpoints = scan_directory(root, url_prefix=args.prefix)

    if args.format == "json":
        content = to_json(endpoints)
    else:
        content = to_markdown(endpoints, str(root))

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
        print(f"Wrote {len(endpoints)} endpoints to {out}")
    else:
        print(content)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
