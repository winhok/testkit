#!/usr/bin/env python3
"""Read-only semantic and provenance audit for a TestSpec TestLib."""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Iterable

SHARED_SCRIPTS = Path(__file__).resolve().parents[2] / "_testspec-shared" / "scripts"
sys.path.insert(0, str(SHARED_SCRIPTS))

from validate_testlib import validate as validate_structure
from provenance import classify_provenance


def normalize(value: Any) -> str:
    return re.sub(r"[\W_]+", "", str(value or ""), flags=re.UNICODE).lower()


def body_signature(case: dict[str, Any]) -> str:
    return normalize("|".join(str(case.get(key, "")) for key in (
        "preconditions",
        "steps",
        "expected_result",
    )))


def feature_files(testlib: Path) -> Iterable[Path]:
    modules = testlib / "modules"
    if not modules.exists():
        return []
    return sorted(modules.glob("*/*.json"))


def finding(
    finding_type: str,
    severity: str,
    message: str,
    case_ids: list[str] | None = None,
    paths: list[str] | None = None,
    recommendation: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "type": finding_type,
        "severity": severity,
        "message": message,
    }
    if case_ids:
        result["case_ids"] = sorted(set(case_ids))
    if paths:
        result["paths"] = sorted(set(paths))
    if recommendation:
        result["recommendation"] = recommendation
    return result


def semantic_audit(testlib: Path) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    records: list[tuple[dict[str, Any], str, str]] = []
    paths = list(feature_files(testlib))

    if not testlib.exists():
        findings.append(finding(
            "MISSING_TESTLIB",
            "error",
            "testlib directory does not exist",
            recommendation="repair-structure",
        ))
        return semantic_report(findings, len(paths), 0)

    for path in paths:
        relative = path.relative_to(testlib).as_posix()
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            findings.append(finding(
                "INVALID_JSON",
                "error",
                f"feature document cannot be parsed: {exc}",
                paths=[relative],
                recommendation="repair-structure",
            ))
            continue

        cases = doc.get("cases")
        if not isinstance(cases, list):
            findings.append(finding(
                "INVALID_CASES",
                "error",
                "feature document cases must be an array",
                paths=[relative],
                recommendation="repair-structure",
            ))
            continue

        module_name = normalize(doc.get("module"))
        for index, case in enumerate(cases):
            if not isinstance(case, dict):
                findings.append(finding(
                    "INVALID_CASE",
                    "error",
                    "case must be an object",
                    paths=[f"{relative}#cases[{index}]"],
                    recommendation="repair-structure",
                ))
                continue
            case_id = str(case.get("id") or f"anonymous-{index + 1}")
            records.append((case, relative, module_name))

            title = str(case.get("title", ""))
            title_module = normalize(re.split(r"[\s_\-—–/]+", title, maxsplit=1)[0])
            if module_name and title_module and title_module != module_name:
                findings.append(finding(
                    "FEATURE_MISMATCH",
                    "warning",
                    "case title module does not match its feature document module",
                    case_ids=[case_id],
                    paths=[relative],
                    recommendation="relocate-or-revise",
                ))

            provenance_state = classify_provenance(case.get("origin"), case.get("trust"))
            if provenance_state == "unknown":
                findings.append(finding(
                    "MISSING_PROVENANCE",
                    "warning",
                    "case lacks origin or trust metadata",
                    case_ids=[case_id],
                    paths=[relative],
                    recommendation="provenance-review",
                ))
            elif provenance_state == "invalid":
                findings.append(finding(
                    "INVALID_PROVENANCE",
                    "warning",
                    "case has an unrecognized or inconsistent origin/trust combination",
                    case_ids=[case_id],
                    paths=[relative],
                    recommendation="provenance-review",
                ))
            elif provenance_state == "legacy-import/unverified" and case.get("status", "active") == "active":
                findings.append(finding(
                    "UNVERIFIED_LEGACY_ACTIVE",
                    "warning",
                    "unverified legacy import is active in TestLib",
                    case_ids=[case_id],
                    paths=[relative],
                    recommendation="reconcile",
                ))

    grouped: dict[str, dict[str, list[tuple[str, str]]]] = {
        "id": defaultdict(list),
        "title": defaultdict(list),
        "body": defaultdict(list),
    }
    for case, path, _module in records:
        case_id = str(case.get("id") or "")
        if case_id:
            grouped["id"][case_id].append((case_id, path))
        title = normalize(case.get("title"))
        if title:
            grouped["title"][title].append((case_id, path))
        body = body_signature(case)
        if body:
            grouped["body"][body].append((case_id, path))

    duplicate_specs = (
        ("id", "DUPLICATE_CASE_ID", "case ID appears more than once"),
        ("title", "DUPLICATE_TITLE", "normalized title appears more than once"),
        ("body", "DUPLICATE_BODY", "case body appears more than once"),
    )
    for key, finding_type, message in duplicate_specs:
        for items in grouped[key].values():
            if len(items) > 1:
                findings.append(finding(
                    finding_type,
                    "warning",
                    message,
                    case_ids=[item[0] for item in items],
                    paths=[item[1] for item in items],
                    recommendation="merge-review",
                ))

    return semantic_report(findings, len(paths), len(records))


def semantic_report(
    findings: list[dict[str, Any]],
    feature_count: int,
    case_count: int,
) -> dict[str, Any]:
    errors = sum(item["severity"] == "error" for item in findings)
    warnings = sum(item["severity"] == "warning" for item in findings)
    recommended_findings = [
        item for item in findings if item.get("recommendation")
    ]
    candidate_case_ids = {
        str(case_id)
        for item in recommended_findings
        for case_id in item.get("case_ids", [])
    }
    return {
        "schema_version": 1,
        "summary": {
            "feature_files": feature_count,
            "cases": case_count,
            "errors": errors,
            "warnings": warnings,
            "recommended_findings": len(recommended_findings),
            "lifecycle_candidates": len(candidate_case_ids),
        },
        "findings": findings,
    }


def audit(testlib: Path, today: str) -> dict[str, Any]:
    structural = validate_structure(testlib, today)
    semantic = semantic_audit(testlib)
    structural_findings = [
        {**item, "source": "structural"}
        for item in structural["issues"]
    ]
    deduplicated_types = {
        "DUPLICATE_CASE_ID",
        "INVALID_PROVENANCE",
        "MISSING_PROVENANCE",
        "UNVERIFIED_LEGACY_ACTIVE",
    }
    structural_finding_keys = {
        (item.get("type"), str(item.get("case_id", "")))
        for item in structural["issues"]
        if item.get("type") in deduplicated_types
    }
    semantic_findings = []
    for item in semantic["findings"]:
        case_ids = item.get("case_ids") or [""]
        if (
            item.get("type") in deduplicated_types
            and all(
                (item.get("type"), str(case_id)) in structural_finding_keys
                for case_id in case_ids
            )
        ):
            continue
        semantic_findings.append({**item, "source": "semantic"})

    combined_findings = structural_findings + semantic_findings
    errors = sum(item["severity"] == "error" for item in combined_findings)
    warnings = sum(item["severity"] == "warning" for item in combined_findings)
    health = "structurally-invalid" if errors else ("needs-review" if warnings else "clean")
    return {
        "schema_version": 1,
        "health": health,
        "structural_health": "clean" if structural["summary"]["errors"] == 0 else "invalid",
        "semantic_health": (
            "invalid"
            if semantic["summary"]["errors"]
            else ("clean" if semantic["summary"]["warnings"] == 0 else "needs-review")
        ),
        "read_only": True,
        "summary": {
            "feature_files": semantic["summary"]["feature_files"],
            "cases": semantic["summary"]["cases"],
            "errors": errors,
            "warnings": warnings,
            "recommended_findings": semantic["summary"]["recommended_findings"],
            "lifecycle_candidates": semantic["summary"]["lifecycle_candidates"],
        },
        "structural": structural,
        "semantic": semantic,
        "findings": combined_findings,
        "mutation_performed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--testlib", default="testspec/testlib", help="TestLib directory")
    parser.add_argument("--output", help="Optional audit report path")
    parser.add_argument("--date", default=date.today().isoformat(), help="Date used for index consistency")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Explicitly replace an existing audit report",
    )
    args = parser.parse_args()

    result = audit(Path(args.testlib), args.date)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        output = Path(args.output)
        if output.exists() and not args.overwrite:
            parser.error(
                f"refusing to overwrite existing audit report {output.name}; "
                "pass --overwrite only after explicit authorization"
            )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 1 if result["summary"]["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
