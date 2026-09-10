#!/usr/bin/env python3
"""Check synthetic eval fixtures/assertions; optionally probe acceptance helpers.

This is not a model evaluation runner and does not produce model pass scores.
"""
import argparse
import hashlib
import json
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAMES = ("app-test", "web-runtime-analysis", "defect-verification", "video-to-issue", "test-acceptance")


def materialize(directory, files):
    seen = set()
    for fixture in files:
        name = fixture["path"]
        path = Path(name)
        if path.is_absolute() or ".." in path.parts or name in seen:
            raise ValueError("unsafe or duplicate fixture path")
        seen.add(name)
        destination = directory / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(fixture["content"], encoding="utf-8")


def check(probe=False):
    summary = {"kind": "fixture-validation", "model_evaluation_run": False, "cases": 0,
               "programmatic_assertions": 0, "qualitative_assertions": 0, "acceptance_probes": [], "defect_probes": []}
    for name in NAMES:
        data = json.loads((ROOT / "skills" / name / "evals" / "evals.json").read_text())
        for case in data["evals"]:
            summary["cases"] += 1
            with tempfile.TemporaryDirectory(prefix="testkit-eval-fixture-") as tmp:
                directory = Path(tmp)
                materialize(directory, case["files"])
                ids = set()
                for assertion in case["assertions"]:
                    if assertion["id"] in ids:
                        raise ValueError("duplicate assertion ID")
                    ids.add(assertion["id"])
                    if assertion["check"] != "programmatic":
                        summary["qualitative_assertions"] += 1
                        continue
                    summary["programmatic_assertions"] += 1
                    command = shlex.split(assertion["script"])
                    if command[:2] != ["python3", "-c"] or len(command) != 3:
                        raise ValueError("new eval assertion must be one Python expression command")
                    compile(command[2], "<eval-assertion>", "exec")
                    command[0] = sys.executable
                    if assertion["id"] == "inputs-unchanged":
                        subprocess.run(command, cwd=directory, check=True, capture_output=True, timeout=30)
                        first = directory / case["files"][0]["path"]
                        original = first.read_bytes()
                        first.write_bytes(original + b"\nchanged")
                        changed = subprocess.run(command, cwd=directory, capture_output=True, timeout=30)
                        if changed.returncode == 0:
                            raise ValueError("input integrity assertion did not detect mutation")
                        first.write_bytes(original)
                    else:
                        # Missing required output must never count as a passing answer.
                        (directory / "eval-result.json").write_text("{}")
                        empty = subprocess.run(command, cwd=directory, capture_output=True, timeout=30)
                        if empty.returncode == 0:
                            raise ValueError(f"empty answer passed {name}/{case['id']}/{assertion['id']}")
                if name == "test-acceptance" and (directory / "run" / "scope.json").is_file():
                    scope_path = directory / "run" / "scope.json"
                    scope = json.loads(scope_path.read_text())
                    for source in scope["sources"]:
                        if hashlib.sha256((directory / source["path"]).read_bytes()).hexdigest() != source["sha256"]:
                            raise ValueError("fixture source hash mismatch")
                    for path in (directory / "run" / "attempts").glob("*.json"):
                        attempt = json.loads(path.read_text())
                        if hashlib.sha256(scope_path.read_bytes()).hexdigest() != attempt["scope_sha256"]:
                            raise ValueError("fixture scope hash mismatch")
                        for evidence in attempt["evidence"]:
                            if hashlib.sha256((directory / evidence["path"]).read_bytes()).hexdigest() != evidence["sha256"]:
                                raise ValueError("fixture evidence hash mismatch")
                    if probe:
                        command = [sys.executable, str(ROOT / "skills/_test-run-shared/scripts/test_run.py"), "evaluate", "--root", str(directory), "--run-dir", str(directory / "run"), "--current-targets", str(directory / "targets.json")]
                        result = subprocess.run(command, capture_output=True, text=True, timeout=20)
                        actual = json.loads(result.stdout)
                        (directory / "eval-result.json").write_text(json.dumps(actual))
                        verdict = next(a for a in case["assertions"] if a["id"] == "verdict")
                        grade_command = shlex.split(verdict["script"])
                        grade_command[0] = sys.executable
                        grade = subprocess.run(grade_command, cwd=directory, capture_output=True, timeout=30)
                        summary["acceptance_probes"].append({"case_id": case["id"], "helper_exit_code": result.returncode,
                            "actual": actual.get("acceptance_status", actual.get("record_validity")), "meets_expected_verdict": grade.returncode == 0})
                if probe and name == "defect-verification" and (directory / "defect.json").exists():
                    command = [sys.executable, str(ROOT / "skills/defect-verification/scripts/verify_defect.py"), "--root", str(directory), "--input", str(directory / "defect.json"), "--output", str(directory / "tool-result.json")]
                    result = subprocess.run(command, capture_output=True, text=True, timeout=20)
                    actual = json.loads(result.stdout)
                    (directory / "eval-result.json").write_text(json.dumps(actual))
                    grade_command = shlex.split(case["assertions"][0]["script"])
                    grade_command[0] = sys.executable
                    grade = subprocess.run(grade_command, cwd=directory, capture_output=True, timeout=30)
                    summary["defect_probes"].append({"case_id": case["id"], "helper_exit_code": result.returncode,
                        "actual": actual.get("status"), "meets_expected_verdict": grade.returncode == 0})
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe-helpers", action="store_true")
    args = parser.parse_args()
    report = check(args.probe_helpers)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(1 if any(not item["meets_expected_verdict"] for item in report["acceptance_probes"] + report["defect_probes"]) else 0)
