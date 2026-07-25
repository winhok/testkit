#!/usr/bin/env python3
"""Run and validate the opt-in DummyJSON authentication integration eval."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
DEMO = (
    REPO_ROOT
    / "examples"
    / "api-test-automation"
    / "dummyjson-auth"
    / "run_authenticated_demo.py"
)


def main() -> int:
    username = os.environ.get("DUMMYJSON_USERNAME")
    password = os.environ.get("DUMMYJSON_PASSWORD")
    if not username or not password:
        print(
            "ERROR: Set DUMMYJSON_USERNAME and DUMMYJSON_PASSWORD to the public "
            "DummyJSON demo credentials",
            file=sys.stderr,
        )
        return 2

    with tempfile.TemporaryDirectory() as temp_dir:
        output = Path(temp_dir) / "run-result.json"
        completed = None
        for attempt in range(1, 4):
            completed = subprocess.run(
                [
                    sys.executable,
                    str(DEMO),
                    "--output",
                    str(output),
                    "--force",
                ],
                cwd=REPO_ROOT,
                env=os.environ,
                text=True,
                capture_output=True,
            )
            workflow_path = Path(f"{output.with_suffix('')}-workflow.json")
            workflow_status = None
            if workflow_path.is_file():
                try:
                    workflow_status = json.loads(
                        workflow_path.read_text(encoding="utf-8")
                    ).get("status")
                except (OSError, json.JSONDecodeError):
                    pass
            if completed.returncode in {0, 1} and workflow_status == "passed":
                break
            if attempt < 3:
                time.sleep(0.5)
        assert completed is not None
        if completed.returncode not in {0, 1}:
            print(completed.stdout, end="")
            print(completed.stderr, end="", file=sys.stderr)
            if workflow_path.is_file():
                print(workflow_path.read_text(encoding="utf-8"), file=sys.stderr)
            print(
                f"ERROR: Live eval ended with execution status {completed.returncode}",
                file=sys.stderr,
            )
            return 2
        if not output.is_file():
            print("ERROR: Live eval did not write run-result.json", file=sys.stderr)
            return 2

        result_text = output.read_text(encoding="utf-8")
        result = json.loads(result_text)
        stem = output.with_suffix("")
        workflow_path = Path(f"{stem}-workflow.json")
        schema_path = Path(f"{stem}-schema.json")
        if not workflow_path.is_file() or not schema_path.is_file():
            print("ERROR: Workflow or schema result is missing", file=sys.stderr)
            return 2
        workflow_text = workflow_path.read_text(encoding="utf-8")
        schema_text = schema_path.read_text(encoding="utf-8")
        workflow = json.loads(workflow_text)
        step_ids = [
            step.get("step_id")
            for run in workflow.get("runs", [])
            for step in run.get("steps", [])
            if step.get("status") == "passed"
        ]
        if workflow.get("status") != "passed" or step_ids != [
            "unauthenticated",
            "login",
            "authenticated",
        ]:
            print("ERROR: Authentication workflow evidence is incomplete", file=sys.stderr)
            return 2
        if result.get("status") not in {"passed", "failed"}:
            print(f"ERROR: Unexpected normalized status: {result.get('status')}", file=sys.stderr)
            return 2
        all_results = result_text + workflow_text + schema_text
        if password in all_results or "eyJ" in all_results:
            print("ERROR: Credential material leaked into normalized results", file=sys.stderr)
            return 2
        if "[REDACTED]" not in schema_text:
            print("ERROR: Expected redaction marker is missing", file=sys.stderr)
            return 2

        print(
            "PASS: DummyJSON auth live eval completed; target status="
            f"{result['status']}, workflow={workflow['status']}"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
