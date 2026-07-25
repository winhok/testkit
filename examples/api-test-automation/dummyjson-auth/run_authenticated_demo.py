#!/usr/bin/env python3
"""Run the generic workflow + Schemathesis automation against DummyJSON."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


BASE_URL = "https://dummyjson.com"
EXAMPLE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = EXAMPLE_ROOT.parents[2]
RUNNER = REPO_ROOT / "skills" / "api-test-automation" / "scripts" / "run_automation.py"
SCHEMA = EXAMPLE_ROOT / "openapi.yaml"
WORKFLOW = EXAMPLE_ROOT / "workflow.yaml"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username-env", default="DUMMYJSON_USERNAME")
    parser.add_argument("--password-env", default="DUMMYJSON_PASSWORD")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/dummyjson-automation-result.json"),
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    if not os.environ.get(args.username_env) or not os.environ.get(args.password_env):
        print(
            f"ERROR: Set {args.username_env} and {args.password_env} before running",
            file=sys.stderr,
        )
        return 2

    stem = args.output.with_suffix("")
    command = [
        sys.executable,
        str(RUNNER),
        str(WORKFLOW),
        "--schema",
        str(SCHEMA),
        "--url",
        BASE_URL,
        "--preflight-workflow",
        "authenticatedUser",
        "--input-env",
        f"username={args.username_env}",
        "--input-env",
        f"password={args.password_env}",
        "--schema-header-from-output",
        "Authorization=token",
        "--header-template",
        "Authorization=Bearer {value}",
        "--allow-preflight-mutating-target",
        "--workflow-output",
        f"{stem}-workflow.json",
        "--schema-output",
        f"{stem}-schema.json",
        "--output",
        str(args.output),
    ]
    if args.force:
        command.append("--force")
    return subprocess.run(command, cwd=REPO_ROOT, env=os.environ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
