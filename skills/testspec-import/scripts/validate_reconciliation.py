#!/usr/bin/env python3
"""Validate legacy import reconciliation coverage and readiness."""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ALLOWED_STATUSES = {"keep", "revise", "merge", "retire", "unresolved"}
CURRENT_REQUIREMENT_PATTERN = re.compile(r"^(?:REQ|AC)-[A-Za-z0-9_-]+$")
QUESTION_PATTERN = re.compile(r"^Q-[A-Za-z0-9_-]+$")


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path.name}: top level must be an object")
    return data


def validate(
    imported_path: Path,
    reconciliation_path: Path,
    ready_for_generate: bool = False,
) -> list[str]:
    errors: list[str] = []
    try:
        imported = read_json(imported_path)
        reconciliation = read_json(reconciliation_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [str(exc)]

    cases = imported.get("testcases")
    records = reconciliation.get("records")
    if not isinstance(cases, list):
        return ["imported artifact: testcases must be an array"]
    if not isinstance(records, list):
        return ["reconciliation artifact: records must be an array"]

    imported_ids = [
        str(case.get("id"))
        for case in cases
        if isinstance(case, dict) and case.get("id")
    ]
    record_ids = [
        str(record.get("legacy_case_id"))
        for record in records
        if isinstance(record, dict) and record.get("legacy_case_id")
    ]
    duplicate_ids = sorted(case_id for case_id, count in Counter(record_ids).items() if count > 1)
    if duplicate_ids:
        errors.append("duplicate reconciliation records: " + ", ".join(duplicate_ids))
    if sorted(imported_ids) != sorted(record_ids):
        missing = sorted(set(imported_ids) - set(record_ids))
        extra = sorted(set(record_ids) - set(imported_ids))
        if missing:
            errors.append("missing reconciliation records: " + ", ".join(missing))
        if extra:
            errors.append("unknown reconciliation records: " + ", ".join(extra))

    counts: Counter[str] = Counter()
    for index, record in enumerate(records):
        prefix = f"records[{index}]"
        if not isinstance(record, dict):
            errors.append(f"{prefix}: record must be an object")
            continue
        status = record.get("status")
        if status not in ALLOWED_STATUSES:
            errors.append(f"{prefix}: invalid status {status!r}")
            continue
        counts[status] += 1

        requirement_refs = record.get("requirement_refs")
        question_refs = record.get("question_refs")
        if not isinstance(requirement_refs, list):
            errors.append(f"{prefix}: requirement_refs must be an array")
            requirement_refs = []
        if not isinstance(question_refs, list):
            errors.append(f"{prefix}: question_refs must be an array")
            question_refs = []
        invalid_requirements = [
            str(ref)
            for ref in requirement_refs
            if not CURRENT_REQUIREMENT_PATTERN.fullmatch(str(ref))
        ]
        invalid_questions = [
            str(ref)
            for ref in question_refs
            if not QUESTION_PATTERN.fullmatch(str(ref))
        ]
        if invalid_requirements:
            errors.append(f"{prefix}: invalid requirement refs: {', '.join(invalid_requirements)}")
        if invalid_questions:
            errors.append(f"{prefix}: invalid question refs: {', '.join(invalid_questions)}")
        if status in {"keep", "revise"} and not requirement_refs:
            errors.append(f"{prefix}: {status} requires current REQ/AC evidence")
        if status == "merge" and not record.get("replacement_candidate_id"):
            errors.append(f"{prefix}: merge requires replacement_candidate_id")
        if ready_for_generate and status == "unresolved":
            errors.append(f"{prefix}: unresolved record blocks generation")

    summary = reconciliation.get("summary")
    expected_summary = {status: counts.get(status, 0) for status in sorted(ALLOWED_STATUSES)}
    if not isinstance(summary, dict):
        errors.append("reconciliation artifact: summary must be an object")
    else:
        actual_summary = {status: summary.get(status, 0) for status in sorted(ALLOWED_STATUSES)}
        if actual_summary != expected_summary:
            errors.append("reconciliation summary does not match records")

    context = reconciliation.get("_context")
    if not isinstance(context, dict):
        errors.append("reconciliation artifact: _context must be an object")
    else:
        if context.get("canonical_source_policy") != "prd-first":
            errors.append("reconciliation artifact: canonical_source_policy must be prd-first")
        status = context.get("status")
        if status not in {"pending", "ready-for-generate"}:
            errors.append(
                "reconciliation artifact: status must be pending or ready-for-generate"
            )
        if ready_for_generate and status != "ready-for-generate":
            errors.append(
                "reconciliation artifact: set _context.status to ready-for-generate "
                "after completing all decisions"
            )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--imported", required=True, type=Path)
    parser.add_argument("--reconciliation", required=True, type=Path)
    parser.add_argument("--ready-for-generate", action="store_true")
    args = parser.parse_args()

    errors = validate(args.imported, args.reconciliation, args.ready_for_generate)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("PASS: reconciliation is consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
