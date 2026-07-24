#!/usr/bin/env python3
"""Run and validate the opt-in DummyJSON authentication integration eval."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
DEMO = (
    REPO_ROOT
    / "examples"
    / "test-api-contracts"
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
        if completed.returncode not in {0, 1}:
            print(completed.stdout, end="")
            print(completed.stderr, end="", file=sys.stderr)
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
        required_messages = (
            "Precondition verified: /auth/me rejects a missing token with 401",
            "Login succeeded for public demo user:",
            "Authenticated precondition verified: /auth/me returned the login user",
        )
        if any(message not in completed.stdout for message in required_messages):
            print("ERROR: Authentication precondition evidence is incomplete", file=sys.stderr)
            return 2
        if result.get("status") not in {"passed", "failed"}:
            print(f"ERROR: Unexpected normalized status: {result.get('status')}", file=sys.stderr)
            return 2
        if password in result_text or "eyJ" in result_text:
            print("ERROR: Credential material leaked into run-result.json", file=sys.stderr)
            return 2
        if "[REDACTED]" not in result_text:
            print("ERROR: Expected redaction marker is missing", file=sys.stderr)
            return 2

        print(
            "PASS: DummyJSON auth live eval completed; target status="
            f"{result['status']}, runner returncode={result['returncode']}"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
