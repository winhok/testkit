#!/usr/bin/env python3
"""Explore test artifacts: Allure reports AND structured JSON results. Self-contained."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

_JSON_PROBE_PATHS = [
    "reports/results.json",
    "reports/summary.json",
]


def _probe_json_results(base: Path) -> list[Path]:
    found = []
    for rel in _JSON_PROBE_PATHS:
        p = base / rel
        if p.exists():
            found.append(p)
    reports_dir = base / "reports"
    if reports_dir.is_dir():
        for p in sorted(reports_dir.glob("*.json")):
            if p not in found:
                found.append(p)
    return found


def _print_json_summary(path: Path) -> None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"  Unable to parse {path}: {exc}")
        return
    summary = data.get("summary")
    if isinstance(summary, dict):
        total = summary.get("total", "?")
        passed = summary.get("passed", "?")
        failed = summary.get("failed", "?")
        print(f"  Summary: {passed}/{total} passed, {failed} failed")
    else:
        keys = list(data.keys())[:5]
        print(f"  Top-level keys: {keys}")


def main():
    parser = argparse.ArgumentParser(description="Explore test artifacts: Allure reports and JSON results")
    parser.add_argument("--results", "-r", default="allure-results", help="Allure results directory")
    parser.add_argument("--report", default="allure-report", help="Output report directory")
    parser.add_argument("--port", "-p", type=int, default=9090, help="Port for serving")
    parser.add_argument("--generate-only", "--no-open", action="store_true", help="Generate report without opening browser")
    parser.add_argument("--json-only", action="store_true", help="Only probe and display JSON results, skip Allure")
    parser.add_argument("--base-dir", default=".", help="Base directory to probe for result artifacts")
    args = parser.parse_args()

    base = Path(args.base_dir).resolve()

    json_results = _probe_json_results(base)
    if json_results:
        print("Structured JSON results found:")
        for jp in json_results:
            print(f"  -> {jp}")
            _print_json_summary(jp)
    else:
        print(f"No structured JSON results found under {base}/reports/")

    if args.json_only:
        if not json_results:
            sys.exit(1)
        return

    print()
    results = Path(args.results).resolve()
    report = Path(args.report).resolve()

    has_allure_results = results.exists() and any(results.iterdir()) if results.exists() else False

    if not has_allure_results:
        print(f"No Allure results found in {results}.")
        print("请先运行接口测试（apitestspec-scenario-runner）生成 allure-results。")
        if not json_results:
            sys.exit(1)
        return

    allure_cmd = "allure"
    try:
        subprocess.run([allure_cmd, "--version"], capture_output=True, check=True)
    except FileNotFoundError:
        print("allure command not found. Install: brew install allure / npm install -g allure-commandline")
        sys.exit(1)

    subprocess.run([allure_cmd, "generate", str(results), "-o", str(report), "--clean"], check=True)
    print(f"Report generated at {report}")

    if not args.generate_only:
        print(f"Serving report on http://localhost:{args.port} ...")
        subprocess.run([allure_cmd, "open", str(report), "-p", str(args.port)])


if __name__ == "__main__":
    main()
