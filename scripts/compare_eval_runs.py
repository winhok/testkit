#!/usr/bin/env python3
"""Compare same-prompt skill eval runs and detect regressions or weak assertions."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


class EvalComparisonError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvalComparisonError(f"{path}: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise EvalComparisonError(f"{path}: schema_version must be 1")
    digest = payload.get("eval_set_sha256")
    if (
        not isinstance(digest, str)
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest.lower())
    ):
        raise EvalComparisonError(f"{path}: eval_set_sha256 must be a SHA-256 hex digest")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise EvalComparisonError(f"{path}: cases must be non-empty")
    return payload


def _index(payload: dict[str, Any], label: str) -> dict[str, dict[str, bool]]:
    result: dict[str, dict[str, bool]] = {}
    for case in payload["cases"]:
        if not isinstance(case, dict) or not isinstance(case.get("id"), str):
            raise EvalComparisonError(f"{label}: each case requires a string id")
        case_id = case["id"]
        if case_id in result:
            raise EvalComparisonError(f"{label}: duplicate case id {case_id}")
        assertions = case.get("assertions")
        if not isinstance(assertions, list) or not assertions:
            raise EvalComparisonError(f"{label}: {case_id} requires assertions")
        indexed: dict[str, bool] = {}
        for assertion in assertions:
            if (
                not isinstance(assertion, dict)
                or not isinstance(assertion.get("id"), str)
                or type(assertion.get("passed")) is not bool
            ):
                raise EvalComparisonError(
                    f"{label}: {case_id} assertions require string id and boolean passed"
                )
            assertion_id = assertion["id"]
            if assertion_id in indexed:
                raise EvalComparisonError(
                    f"{label}: duplicate assertion {case_id}/{assertion_id}"
                )
            indexed[assertion_id] = assertion["passed"]
        result[case_id] = indexed
    return result


def _same_shape(
    reference: dict[str, dict[str, bool]],
    other: dict[str, dict[str, bool]],
    label: str,
) -> None:
    if reference.keys() != other.keys():
        raise EvalComparisonError(f"{label}: case ids differ from baseline")
    for case_id in reference:
        if reference[case_id].keys() != other[case_id].keys():
            raise EvalComparisonError(f"{label}: assertion ids differ for {case_id}")


def compare(
    baseline_payload: dict[str, Any],
    candidate_payload: dict[str, Any],
    without_skill_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    digest = baseline_payload["eval_set_sha256"]
    if candidate_payload["eval_set_sha256"] != digest:
        raise EvalComparisonError("candidate eval_set_sha256 differs from baseline")
    if without_skill_payload and without_skill_payload["eval_set_sha256"] != digest:
        raise EvalComparisonError("without-skill eval_set_sha256 differs from baseline")

    baseline = _index(baseline_payload, "baseline")
    candidate = _index(candidate_payload, "candidate")
    _same_shape(baseline, candidate, "candidate")
    without_skill = None
    if without_skill_payload is not None:
        without_skill = _index(without_skill_payload, "without-skill")
        _same_shape(baseline, without_skill, "without-skill")

    regressions: list[str] = []
    improvements: list[str] = []
    weak_cases: list[str] = []
    no_lift_cases: list[str] = []
    for case_id, assertions in baseline.items():
        for assertion_id, old_passed in assertions.items():
            new_passed = candidate[case_id][assertion_id]
            key = f"{case_id}/{assertion_id}"
            if old_passed and not new_passed:
                regressions.append(key)
            elif not old_passed and new_passed:
                improvements.append(key)
        if without_skill is not None:
            control_passes = sum(without_skill[case_id].values())
            candidate_passes = sum(candidate[case_id].values())
            if control_passes == len(without_skill[case_id]):
                weak_cases.append(case_id)
            if candidate_passes <= control_passes:
                no_lift_cases.append(case_id)

    total = sum(len(assertions) for assertions in baseline.values())
    baseline_passes = sum(sum(assertions.values()) for assertions in baseline.values())
    candidate_passes = sum(sum(assertions.values()) for assertions in candidate.values())
    failed = bool(regressions or weak_cases or no_lift_cases)
    return {
        "schema_version": 1,
        "status": "failed" if failed else "passed",
        "eval_set_sha256": digest,
        "summary": {
            "cases": len(baseline),
            "assertions": total,
            "baseline_passed": baseline_passes,
            "candidate_passed": candidate_passes,
        },
        "regressions": sorted(regressions),
        "improvements": sorted(improvements),
        "weak_cases": sorted(set(weak_cases)),
        "no_lift_cases": sorted(set(no_lift_cases)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--without-skill", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = compare(
            _load(args.baseline),
            _load(args.candidate),
            _load(args.without_skill) if args.without_skill else None,
        )
    except EvalComparisonError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    try:
        if args.output:
            if args.output.exists():
                print(f"ERROR: output already exists: {args.output}", file=sys.stderr)
                return 2
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8")
        else:
            print(rendered, end="")
    except OSError as exc:
        print(f"ERROR: cannot write comparison: {exc}", file=sys.stderr)
        return 2
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
