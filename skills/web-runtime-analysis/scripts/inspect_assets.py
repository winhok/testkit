#!/usr/bin/env python3
"""Inventory explicitly exported Web assets; candidates are not runtime facts."""
import argparse
import hashlib
import json
import re
from bisect import bisect_right
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit


class DOMInventory(HTMLParser):
    def __init__(self):
        super().__init__()
        self.controls = []
        self.resources = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"input", "button", "select", "textarea", "form"}:
            # Do not export values, user text, hidden tokens or arbitrary attributes.
            self.controls.append({"tag": tag, "type": attrs.get("type"), "required": "required" in attrs, "line": self.getpos()[0]})
        key = "src" if tag == "script" else "href" if tag == "link" else None
        if key and attrs.get(key):
            self.resources.append({"tag": tag, "path": safe_path(attrs[key]), "origin_label": origin_label(attrs[key]), "line": self.getpos()[0]})


def safe_path(value):
    parsed = urlsplit(value)
    # Domain, query, fragment and userinfo may contain identifiers or credentials.
    path = parsed.path
    return re.sub(r"[0-9a-f]{24,}|[0-9]{6,}", "[REDACTED-ID]", path, flags=re.I)


def origin_label(value):
    parsed = urlsplit(value)
    if not parsed.netloc:
        return "same-origin"
    # Hash only normalized origin; strip userinfo, query and fragment first.
    port = parsed.port
    scheme = parsed.scheme.lower()
    if (scheme == 'https' and port == 443) or (scheme == 'http' and port == 80):
        port = None
    origin = f"{scheme}://{(parsed.hostname or '').lower()}:{port or ''}"
    return 'origin-' + hashlib.sha256(origin.encode()).hexdigest()[:16]


def inspect(root, paths, max_bytes=2_000_000):
    if type(max_bytes) is not int or max_bytes <= 0:
        raise ValueError("max-bytes must be positive")
    root = Path(root).resolve()
    reports = []
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
            dom = DOMInventory()
            dom.feed(content)
            report.update(controls=dom.controls, resource_references=dom.resources)
        elif path.suffix.lower() == ".map":
            source_map = json.loads(content)
            if not isinstance(source_map, dict) or not isinstance(source_map.get('sources', []), list):
                raise ValueError('invalid source map')
            report.update(source_count=len(source_map.get("sources", [])), embedded_sources=bool(source_map.get("sourcesContent")))
        else:
            candidates = []
            newline_offsets = [m.start() for m in re.finditer('\n', content)]
            for match in re.finditer(r"(?P<call>fetch|axios\.(?:get|post|put|patch|delete|head|options))\s*\(\s*['\"](?P<url>[^'\"]+)['\"]", content):
                method = match.group('call').split('.')[-1].upper() if match.group('call').startswith('axios.') else None
                candidates.append({"path": safe_path(match.group('url')), "origin_label": origin_label(match.group('url')), "method": method, "line": bisect_right(newline_offsets, match.start()) + 1, "kind": "request-candidate"})
            report["request_candidates"] = candidates
            report["signals"] = [signal for signal in ("WebSocket", "EventSource", "localStorage", "sessionStorage", "indexedDB", "serviceWorker", "@media", "prefers-reduced-motion") if signal in content]
        reports.append(report)
    return {"schema_version": 1, "kind": "web-asset-inspection", "assets": reports,
            "limitations": ["Explicit local exports only; heuristic patterns miss computed/minified calls, unloaded chunks and runtime branches.", "Inspect output before sharing; paths may still contain project identifiers."]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--asset", action="append", required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--max-bytes", type=int, default=2_000_000)
    args = p.parse_args()
    try:
        if args.max_bytes < 1:
            raise ValueError("max-bytes must be positive")
        result = inspect(args.root, args.asset, args.max_bytes)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
