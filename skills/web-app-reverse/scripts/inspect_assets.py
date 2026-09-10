#!/usr/bin/env python3
"""Inventory local exported Web assets; candidates are not runtime facts."""
import argparse
import hashlib
import json
import re
from bisect import bisect_right
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit


class DOMInventory(HTMLParser):
    def __init__(self, site_origin=None):
        super().__init__()
        self.site_origin = site_origin
        self.controls = []
        self.resources = []
        self.forms = []
        self.base_href = None
        self.coverage_references = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "base" and self.base_href is None and attrs.get("href"):
            self.base_href = attrs["href"]
        if tag in {"input", "button", "select", "textarea", "form"}:
            # Do not export values, user text, hidden tokens or arbitrary attributes.
            self.controls.append({"tag": tag, "type": attrs.get("type"), "required": "required" in attrs, "line": self.getpos()[0]})
        if tag == "form":
            action = attrs.get("action")
            self.forms.append({
                "method": attrs.get("method", "get").upper(),
                "path": safe_path(action) if action else None,
                "origin_label": origin_label(action, self.site_origin) if action else ("target-origin" if self.site_origin else "same-origin"),
                "line": self.getpos()[0],
            })
        key = "src" if tag in {"script", "iframe"} else "href" if tag == "link" else None
        if key and attrs.get(key):
            resource = {"tag": tag, "path": safe_path(attrs[key]), "origin_label": origin_label(attrs[key], self.site_origin), "line": self.getpos()[0]}
            if tag == "link":
                resource["rel"] = attrs.get("rel")
            self.resources.append(resource)
            self.coverage_references.append({"url": attrs[key], "kind": tag})


def safe_path(value):
    parsed = urlsplit(value)
    if parsed.scheme in {"data", "blob"}:
        return f"[{parsed.scheme.upper()}-RESOURCE]"
    # Domain, query, fragment and userinfo may contain identifiers or credentials.
    path = parsed.path
    return re.sub(r"[0-9a-f]{24,}|[0-9]{6,}", "[REDACTED-ID]", path, flags=re.I)


def normalize_site_origin(value):
    if value is None:
        return None
    parsed = urlsplit(value)
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password
            or parsed.path not in {"", "/"} or parsed.query or parsed.fragment):
        raise ValueError("site-origin must be an http(s) origin without path, credentials, query or fragment")
    port = parsed.port
    if (parsed.scheme == "https" and port == 443) or (parsed.scheme == "http" and port == 80):
        port = None
    return f"{parsed.scheme}://{parsed.hostname.lower()}{f':{port}' if port else ''}"


def absolute_origin(value, default_scheme=None):
    parsed = urlsplit(value)
    if not parsed.netloc:
        return None
    scheme = parsed.scheme.lower() or default_scheme
    if scheme not in {"http", "https"}:
        return None
    port = parsed.port
    if (scheme == "https" and port == 443) or (scheme == "http" and port == 80):
        port = None
    return f"{scheme}://{(parsed.hostname or '').lower()}{f':{port}' if port else ''}"


def origin_label(value, site_origin=None):
    parsed = urlsplit(value)
    if parsed.scheme in {"data", "blob"}:
        return parsed.scheme
    if not parsed.netloc:
        return "target-origin" if site_origin else "same-origin"
    normalized = absolute_origin(value, urlsplit(site_origin).scheme if site_origin else None)
    if site_origin and normalized == site_origin:
        return "target-origin"
    # Hash only normalized origin; strip userinfo, query and fragment first.
    port = parsed.port
    scheme = parsed.scheme.lower()
    if (scheme == 'https' and port == 443) or (scheme == 'http' and port == 80):
        port = None
    origin = f"{scheme}://{(parsed.hostname or '').lower()}:{port or ''}"
    return 'origin-' + hashlib.sha256(origin.encode()).hexdigest()[:16]


REQUEST_PATTERNS = (
    (re.compile(r"(?P<call>fetch|axios\.(?:get|post|put|patch|delete|head|options))\s*\(\s*['\"](?P<url>[^'\"]+)['\"]"), "http"),
    (re.compile(r"\.open\s*\(\s*['\"](?P<method>GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)['\"]\s*,\s*['\"](?P<url>[^'\"]+)['\"]", re.I), "xhr"),
    (re.compile(r"(?:navigator\s*\.\s*)?sendBeacon\s*\(\s*['\"](?P<url>[^'\"]+)['\"]"), "beacon"),
    (re.compile(r"new\s+WebSocket\s*\(\s*['\"](?P<url>[^'\"]+)['\"]"), "websocket"),
    (re.compile(r"new\s+EventSource\s*\(\s*['\"](?P<url>[^'\"]+)['\"]"), "sse"),
)


SIGNALS = (
    "XMLHttpRequest", "sendBeacon", "WebSocket", "EventSource", "localStorage",
    "sessionStorage", "indexedDB", "serviceWorker", "CacheStorage", "BroadcastChannel",
    "postMessage", "pushState", "replaceState", "@media", "prefers-reduced-motion",
)

RESOURCE_PATTERNS = (
    (re.compile(r"(?:import|export)\s+(?:[^'\";]+?\s+from\s+)?['\"](?P<url>[^'\"]+)['\"]"), "static-import"),
    (re.compile(r"import\s*\(\s*['\"](?P<url>[^'\"]+)['\"]\s*\)"), "dynamic-import"),
    (re.compile(r"@import\s+(?:url\(\s*)?['\"]?(?P<url>[^'\"\s;)]+)"), "css-import"),
    (re.compile(r"new\s+(?:Shared)?Worker\s*\(\s*['\"](?P<url>[^'\"]+)['\"]"), "worker"),
    (re.compile(r"serviceWorker\s*\.\s*register\s*\(\s*['\"](?P<url>[^'\"]+)['\"]"), "service-worker"),
    (re.compile(r"[#@]\s*sourceMappingURL\s*=\s*(?P<url>[^\s*]+)"), "source-map"),
)

ROUTE_PATTERNS = (
    re.compile(r"\bpath\s*[:=]\s*['\"](?P<route>/[^'\"]*)['\"]"),
    re.compile(r"\b(?:navigate|router\.(?:push|replace))\s*\(\s*['\"](?P<route>/[^'\"]*)['\"]"),
)

STORAGE_PATTERN = re.compile(
    r"(?P<store>localStorage|sessionStorage)\s*\.\s*(?P<operation>getItem|setItem|removeItem)"
    r"\s*\(\s*['\"](?P<key>[^'\"]+)['\"]"
)
INDEXED_DB_PATTERN = re.compile(r"indexedDB\s*\.\s*open\s*\(\s*['\"](?P<key>[^'\"]+)['\"]")
GRAPHQL_PATTERN = re.compile(r"\b(?P<operation>query|mutation|subscription)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)")


def request_candidates(content, newline_offsets, site_origin=None):
    candidates = []
    for pattern, transport in REQUEST_PATTERNS:
        for match in pattern.finditer(content):
            call = match.groupdict().get("call")
            explicit_method = match.groupdict().get("method")
            if explicit_method:
                method = explicit_method.upper()
            elif call and call.startswith("axios."):
                method = call.split(".")[-1].upper()
            elif transport == "beacon":
                method = "POST"
            else:
                method = None
            candidates.append((match.start(), {
                "path": safe_path(match.group("url")),
                "origin_label": origin_label(match.group("url"), site_origin),
                "method": method,
                "line": bisect_right(newline_offsets, match.start()) + 1,
                "kind": "request-candidate",
                "transport": transport,
            }))
    return [candidate for _, candidate in sorted(candidates, key=lambda item: item[0])]


def located_candidates(content, newline_offsets, site_origin=None):
    resources = []
    coverage_references = []
    for pattern, kind in RESOURCE_PATTERNS:
        for match in pattern.finditer(content):
            resources.append((match.start(), {
                "kind": kind,
                "path": safe_path(match.group("url")),
                "origin_label": origin_label(match.group("url"), site_origin),
                "line": bisect_right(newline_offsets, match.start()) + 1,
            }))
            coverage_references.append({"url": match.group("url"), "kind": kind})

    routes = []
    for pattern in ROUTE_PATTERNS:
        for match in pattern.finditer(content):
            route = safe_path(match.group("route"))
            if route and not route.startswith(("/api/", "/graphql")):
                routes.append((match.start(), {
                    "path": route,
                    "line": bisect_right(newline_offsets, match.start()) + 1,
                    "classification": "static-candidate",
                }))

    storage = []
    for match in STORAGE_PATTERN.finditer(content):
        storage.append((match.start(), {
            "store": match.group("store"),
            "operation": match.group("operation"),
            "key": match.group("key"),
            "line": bisect_right(newline_offsets, match.start()) + 1,
        }))
    for match in INDEXED_DB_PATTERN.finditer(content):
        storage.append((match.start(), {
            "store": "indexedDB",
            "operation": "open",
            "key": match.group("key"),
            "line": bisect_right(newline_offsets, match.start()) + 1,
        }))

    graphql = [{
        "operation": match.group("operation"),
        "name": match.group("name"),
        "line": bisect_right(newline_offsets, match.start()) + 1,
    } for match in GRAPHQL_PATTERN.finditer(content)]

    return {
        "resource_candidates": [item for _, item in sorted(resources, key=lambda row: row[0])],
        "route_candidates": [item for _, item in sorted(routes, key=lambda row: row[0])],
        "storage_candidates": [item for _, item in sorted(storage, key=lambda row: row[0])],
        "graphql_candidates": graphql,
    }, coverage_references


def discover_assets(root, max_assets=200):
    if type(max_assets) is not int or max_assets <= 0:
        raise ValueError("max-assets must be positive")
    root = Path(root).resolve()
    paths = []
    for path in sorted(root.rglob("*")):
        resolved = path.resolve()
        if not resolved.is_relative_to(root) or not resolved.is_file():
            continue
        if path.suffix.lower() in {".html", ".htm", ".js", ".mjs", ".css", ".map"}:
            paths.append(path.relative_to(root).as_posix())
            if len(paths) > max_assets:
                raise ValueError(f"discovered more than {max_assets} supported assets")
    return paths


def reference_coverage(root, references, site_origin=None):
    root = Path(root).resolve()
    local_edges = 0
    available_edges = 0
    unique_resources = set()
    available_resources = set()
    missing = []
    unresolved = []
    default_scheme = urlsplit(site_origin).scheme if site_origin else None
    for reference in references:
        raw_url = reference["url"]
        parsed = urlsplit(raw_url)
        if parsed.scheme in {"data", "blob"}:
            continue
        if parsed.netloc:
            candidate_origin = absolute_origin(raw_url, default_scheme)
            if site_origin is None:
                unresolved.append({"from": reference["from"], "path": safe_path(raw_url), "kind": reference["kind"], "reason": "site-origin-unset"})
                continue
            if candidate_origin != site_origin:
                unresolved.append({"from": reference["from"], "path": safe_path(raw_url), "kind": reference["kind"], "reason": "external-origin"})
                continue
            resolved_path = parsed.path
        elif reference.get("base_href"):
            document_path = "/" + reference["from"].lstrip("/")
            resolved_url = urljoin(urljoin(document_path, reference["base_href"]), raw_url)
            resolved_origin = absolute_origin(resolved_url, default_scheme)
            if resolved_origin and (site_origin is None or resolved_origin != site_origin):
                reason = "site-origin-unset" if site_origin is None else "external-origin"
                unresolved.append({"from": reference["from"], "path": safe_path(resolved_url), "kind": reference["kind"], "reason": reason})
                continue
            resolved_path = urlsplit(resolved_url).path
        elif raw_url.startswith("/"):
            resolved_path = parsed.path
        elif raw_url.startswith(("./", "../")) or reference["kind"] in {"script", "iframe", "link", "css-import", "source-map", "worker", "service-worker", "dynamic-import"}:
            resolved_path = (Path(reference["from"]).parent / parsed.path).as_posix()
        else:
            unresolved.append({"from": reference["from"], "path": safe_path(raw_url), "kind": reference["kind"], "reason": "bare-specifier"})
            continue

        target = (root / resolved_path.lstrip("/")).resolve()
        if not target.is_relative_to(root):
            unresolved.append({"from": reference["from"], "path": safe_path(raw_url), "kind": reference["kind"], "reason": "outside-export-root"})
            continue
        relative_target = target.relative_to(root).as_posix()
        local_edges += 1
        unique_resources.add(relative_target)
        if target.is_file():
            available_edges += 1
            available_resources.add(relative_target)
        else:
            missing.append({"from": reference["from"], "path": safe_path(raw_url), "kind": reference["kind"]})
    return {
        "local_reference_edges": local_edges,
        "available_reference_edges": available_edges,
        "unique_local_resources": len(unique_resources),
        "available_unique_resources": len(available_resources),
        "missing": missing,
        "unresolved": unresolved,
    }


def inspect(root, paths, max_bytes=2_000_000, site_origin=None):
    if type(max_bytes) is not int or max_bytes <= 0:
        raise ValueError("max-bytes must be positive")
    root = Path(root).resolve()
    site_origin = normalize_site_origin(site_origin)
    reports = []
    coverage_references = []
    for name in paths:
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("assets must be relative to --root")
        path = (root / relative).resolve()
        if not path.is_relative_to(root):
            raise ValueError("asset symlink escapes root")
        if path.suffix.lower() not in {".html", ".htm", ".js", ".mjs", ".css", ".map"}:
            raise ValueError("unsupported asset type")
        if path.stat().st_size > max_bytes:
            reports.append({"path": relative.as_posix(), "status": "not-inspected", "reason": "size limit"})
            continue
        if not path.is_file():
            raise ValueError("asset must be a regular file")
        with path.open('rb') as stream:
            raw = stream.read(max_bytes + 1)
        if len(raw) > max_bytes:
            reports.append({"path": relative.as_posix(), "status": "not-inspected", "reason": "size limit"})
            continue
        content = raw.decode("utf-8")
        report = {"path": relative.as_posix(), "sha256": hashlib.sha256(raw).hexdigest(), "classification": "static-candidate", "status": "inspected"}
        if path.suffix.lower() in {".html", ".htm"}:
            dom = DOMInventory(site_origin)
            dom.feed(content)
            report.update(controls=dom.controls, forms=dom.forms, resource_references=dom.resources)
            if dom.base_href:
                report["base"] = {"path": safe_path(dom.base_href), "origin_label": origin_label(dom.base_href, site_origin)}
            coverage_references.extend({"from": relative.as_posix(), "base_href": dom.base_href, **item} for item in dom.coverage_references)
        elif path.suffix.lower() == ".map":
            source_map = json.loads(content)
            if not isinstance(source_map, dict) or not isinstance(source_map.get('sources', []), list):
                raise ValueError('invalid source map')
            generated_file = source_map.get("file")
            report.update(source_count=len(source_map.get("sources", [])), embedded_sources=bool(source_map.get("sourcesContent")),
                          generated_file=safe_path(generated_file) if isinstance(generated_file, str) else None)
        else:
            newline_offsets = [m.start() for m in re.finditer('\n', content)]
            report["request_candidates"] = request_candidates(content, newline_offsets, site_origin)
            located, located_references = located_candidates(content, newline_offsets, site_origin)
            report.update(located)
            coverage_references.extend({"from": relative.as_posix(), **item} for item in located_references)
            report["signals"] = [signal for signal in SIGNALS if signal in content]
            report["signal_locations"] = [
                {"signal": signal, "line": bisect_right(newline_offsets, content.find(signal)) + 1}
                for signal in report["signals"]
            ]
        reports.append(report)
    return {"schema_version": 2, "kind": "web-asset-inspection",
            "inventory": {"requested": len(paths), "inspected": sum(row["status"] == "inspected" for row in reports),
                          "not_inspected": sum(row["status"] != "inspected" for row in reports)},
            "reference_coverage": reference_coverage(root, coverage_references, site_origin),
            "assets": reports,
            "limitations": ["Local exports only; heuristic patterns miss computed/minified calls, absent chunks and runtime branches.", "Inspect output before sharing; paths and storage keys may still contain project identifiers."]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--asset", action="append")
    p.add_argument("--discover-local", action="store_true", help="recursively include supported files already present under --root")
    p.add_argument("--max-assets", type=int, default=200)
    p.add_argument("--site-origin", help="target http(s) origin used to classify absolute references")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--max-bytes", type=int, default=2_000_000)
    args = p.parse_args()
    try:
        if args.max_bytes < 1:
            raise ValueError("max-bytes must be positive")
        paths = list(args.asset or [])
        if args.discover_local:
            paths.extend(discover_assets(args.root, args.max_assets))
        paths = list(dict.fromkeys(paths))
        if not paths:
            raise ValueError("provide --asset or --discover-local")
        result = inspect(args.root, paths, args.max_bytes, args.site_origin)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
