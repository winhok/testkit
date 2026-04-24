#!/usr/bin/env python3
"""Validate TestLib feature files, index.json, and .testlib.json consistency."""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rebuild_testlib_index import build_config, build_index, feature_files, feature_path, read_json


DEFAULT_TESTLIB = Path("testspec/testlib")
FEATURE_REQUIRED = {
    "schema_version",
    "module",
    "module_key",
    "feature",
    "feature_key",
    "last_updated",
    "case_count",
    "cases",
}
CASE_REQUIRED = {
    "id",
    "title",
    "priority",
    "type",
    "status",
    "feature",
    "steps",
    "expected_result",
    "source_change",
    "created_at",
    "updated_at",
}


def issue(issue_type: str, severity: str, path: Path | str, message: str, **extra: Any) -> dict[str, Any]:
    item = {
        "type": issue_type,
        "severity": severity,
        "path": str(path),
        "message": message,
    }
    item.update(extra)
    return item


def comparable_index(index: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": index.get("schema_version"),
        "modules": index.get("modules") or [],
    }


def comparable_config(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": config.get("schema_version"),
        "stats": config.get("stats") or {},
    }


def validate(testlib: Path, today: str) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    case_locations: dict[str, list[str]] = defaultdict(list)
    known_features = {feature_path(path, testlib) for path in feature_files(testlib)}
    has_invalid_feature_json = False

    if not testlib.exists():
        issues.append(issue("MISSING_TESTLIB", "error", testlib, "testlib directory does not exist"))
        return report(issues, testlib, 0)

    for path in feature_files(testlib):
        try:
            doc = read_json(path)
        except json.JSONDecodeError as exc:
            has_invalid_feature_json = True
            issues.append(issue("INVALID_JSON", "error", path, f"invalid JSON: {exc}"))
            continue

        missing = sorted(field for field in FEATURE_REQUIRED if field not in doc)
        if missing:
            issues.append(issue("MISSING_FEATURE_FIELD", "error", path, "feature file is missing required fields", fields=missing))

        cases = doc.get("cases")
        if not isinstance(cases, list):
            issues.append(issue("INVALID_CASES", "error", path, "cases must be an array"))
            continue

        if doc.get("case_count") != len(cases):
            issues.append(issue(
                "CASE_COUNT_MISMATCH",
                "error",
                path,
                "case_count does not match cases length",
                expected=len(cases),
                actual=doc.get("case_count"),
            ))

        for ref in doc.get("related_features") or []:
            ref_path = ref.get("path") if isinstance(ref, dict) else ref
            if ref_path and str(ref_path) not in known_features:
                issues.append(issue(
                    "BROKEN_RELATED_FEATURE",
                    "error",
                    path,
                    "related_features points to a missing feature",
                    related_feature=str(ref_path),
                ))

        for idx, case in enumerate(cases):
            case_path = f"{path}#cases[{idx}]"
            if not isinstance(case, dict):
                issues.append(issue("INVALID_CASE", "error", case_path, "case must be an object"))
                continue

            missing_case_fields = sorted(field for field in CASE_REQUIRED if not case.get(field))
            if missing_case_fields:
                issues.append(issue(
                    "MISSING_CASE_FIELD",
                    "error",
                    case_path,
                    "case is missing required fields",
                    fields=missing_case_fields,
                ))

            case_id = case.get("id")
            if case_id:
                case_locations[str(case_id)].append(path.relative_to(testlib / "modules").as_posix())

    for case_id, locations in sorted(case_locations.items()):
        unique_locations = sorted(set(locations))
        if len(unique_locations) > 1:
            issues.append(issue(
                "DUPLICATE_CASE_ID",
                "error",
                ",".join(unique_locations),
                "case id appears in multiple feature files",
                case_id=case_id,
                locations=unique_locations,
            ))

    if has_invalid_feature_json:
        return report(issues, testlib, len(feature_files(testlib)))

    expected_index = build_index(testlib, today)
    index_path = testlib / "index.json"
    if not index_path.exists():
        issues.append(issue("MISSING_INDEX", "error", index_path, "index.json is missing"))
    else:
        try:
            current_index = read_json(index_path)
            if comparable_index(current_index) != comparable_index(expected_index):
                issues.append(issue("INDEX_OUT_OF_DATE", "error", index_path, "index.json does not match modules/*.json"))
        except json.JSONDecodeError as exc:
            issues.append(issue("INVALID_JSON", "error", index_path, f"invalid JSON: {exc}"))

    config_path = testlib / ".testlib.json"
    if not config_path.exists():
        issues.append(issue("MISSING_CONFIG", "error", config_path, ".testlib.json is missing"))
    else:
        try:
            current_config = read_json(config_path)
            expected_config = build_config(testlib, today, current_config)
            if comparable_config(current_config) != comparable_config(expected_config):
                issues.append(issue("STATS_OUT_OF_DATE", "error", config_path, ".testlib.json stats do not match modules/*.json"))
        except json.JSONDecodeError as exc:
            issues.append(issue("INVALID_JSON", "error", config_path, f"invalid JSON: {exc}"))

    return report(issues, testlib, len(feature_files(testlib)))


def report(issues: list[dict[str, Any]], testlib: Path, feature_file_count: int) -> dict[str, Any]:
    errors = sum(1 for item in issues if item["severity"] == "error")
    warnings = sum(1 for item in issues if item["severity"] == "warning")
    return {
        "status": "pass" if errors == 0 else "fail",
        "testlib": str(testlib),
        "summary": {
            "feature_files": feature_file_count,
            "errors": errors,
            "warnings": warnings,
        },
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--testlib", default=str(DEFAULT_TESTLIB), help="Path to testspec/testlib")
    parser.add_argument("--date", default=date.today().isoformat(), help="YYYY-MM-DD date for consistency comparison")
    args = parser.parse_args()

    result = validate(Path(args.testlib), args.date)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
