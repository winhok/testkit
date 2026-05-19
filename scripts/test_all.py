#!/usr/bin/env python3
"""Run the repository's stable verification checks."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

CHECKS = {
    "packaging": [
        [sys.executable, "tests/test_plugin_packaging.py"],
    ],
    "contracts": [
        [sys.executable, "skills/_testspec-shared/scripts/validate_skill_contracts.py"],
    ],
    "unit": [
        [sys.executable, "skills/api2jmx/tests/test_generate_jmx.py"],
        [sys.executable, "skills/testspec-generate/tests/test_generate_excel.py"],
        [sys.executable, "skills/testspec-generate/tests/test_generate_xmind.py"],
        [sys.executable, "skills/testspec-generate/tests/test_smoke_testcase.py"],
        [sys.executable, "skills/_testspec-shared/tests/test_validate_skill_contracts.py"],
        [sys.executable, "skills/_testspec-shared/tests/test_testlib_tools.py"],
    ],
}


def run_check(name: str) -> int:
    print(f"== {name} ==")
    for command in CHECKS[name]:
        print("+ " + " ".join(command))
        env = {**os.environ, "TESTKIT_TEST_ALL_CHILD": "1"}
        result = subprocess.run(command, cwd=REPO_ROOT, env=env)
        if result.returncode != 0:
            return result.returncode
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--only",
        choices=sorted(CHECKS),
        help="Run a single check group instead of the full suite.",
    )
    args = parser.parse_args()

    names = [args.only] if args.only else ["packaging", "contracts", "unit"]
    for name in names:
        code = run_check(name)
        if code:
            return code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
