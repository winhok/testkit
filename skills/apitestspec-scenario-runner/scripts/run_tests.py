#!/usr/bin/env python3
"""Run API test specs via CLI. Self-contained entry point."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from engine import CaseExecutionResult, HttpClient, execute_case, write_results
from loaders import (
    discover_case_files,
    discover_flows,
    load_case_file,
    load_project_spec,
)


def _load_env(project_dir: Path) -> dict[str, str]:
    env = dict(os.environ)
    dotenv = project_dir / "config" / ".env"
    if dotenv.exists():
        for line in dotenv.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, _, val = line.partition("=")
            env[key.strip()] = val.strip()
    return env


def main():
    parser = argparse.ArgumentParser(description="Run API test specs")
    parser.add_argument("--project", "-p", required=True, help="Path to project.yaml")
    parser.add_argument("--case", "-c", help="Run single case file")
    parser.add_argument("--tag", "-t", action="append", help="Filter by tag")
    parser.add_argument("--output", "-o", default="results.json", help="Results output file")
    args = parser.parse_args()

    project_path = Path(args.project).resolve()
    if not project_path.exists():
        print(f"Project file not found: {project_path}", file=sys.stderr)
        sys.exit(1)

    project = load_project_spec(project_path)
    env = _load_env(project_path.parent)

    base_url = env.get("BASE_URL", project.base_url)
    client = HttpClient(base_url)
    flows = discover_flows(project_path, project)

    if args.case:
        case_files = [Path(args.case).resolve()]
    else:
        case_files = discover_case_files(project_path, project)

    if not case_files:
        print("No case files found.", file=sys.stderr)
        sys.exit(1)

    results: list[CaseExecutionResult] = []
    for cf in case_files:
        doc = load_case_file(cf)
        flows.update(doc.flows)
        for case in doc.cases:
            if args.tag and not any(t in case.tags for t in args.tag):
                continue
            print(f"Running: [{case.id}] {case.name}")
            result = execute_case(project, case, client=client, env=env, flows=flows)
            results.append(result)
            status = "PASS" if result.status == "passed" else "FAIL"
            print(f"  -> {status}")
            if result.reason:
                print(f"     {result.reason}")

    out = Path(args.output)
    write_results(results, out)
    total = len(results)
    passed = sum(r.status == "passed" for r in results)
    failed = total - passed
    print(f"\nDone: {passed}/{total} passed, {failed} failed. Results -> {out}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
