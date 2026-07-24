#!/usr/bin/env python3
"""Import legacy cases into an isolated, unverified TestSpec staging artifact."""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


FIELD_ALIASES = {
    "id": ("id", "case_id", "编号"),
    "title": ("title", "标题", "用例标题"),
    "priority": ("priority", "优先级", "级别"),
    "preconditions": ("preconditions", "前置条件", "预置条件"),
    "steps": ("steps", "步骤", "操作步骤"),
    "expected_result": ("expected_result", "预期结果", "测试预期内容"),
    "type": ("type", "类型"),
    "feature": ("feature", "功能", "模块"),
}
ALIASES = {
    alias.strip().lower(): canonical
    for canonical, aliases in FIELD_ALIASES.items()
    for alias in aliases
}


def clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def canonical_row(row: dict[str, Any]) -> dict[str, str]:
    result = {field: "" for field in FIELD_ALIASES}
    for key, value in row.items():
        canonical = ALIASES.get(clean(key).lower())
        if canonical and not result[canonical]:
            result[canonical] = clean(value)
    return result


def load_rows(path: Path) -> list[tuple[int, dict[str, Any]]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return [(index, dict(row)) for index, row in enumerate(csv.DictReader(handle), start=2)]
    if suffix == ".json":
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            raw = raw.get("testcases", raw.get("cases"))
        if not isinstance(raw, list):
            raise ValueError("JSON input must be an array or contain a testcases/cases array")
        return [(index, row) for index, row in enumerate(raw, start=1) if isinstance(row, dict)]
    if suffix == ".xlsx":
        try:
            from openpyxl import load_workbook
        except ImportError as exc:  # pragma: no cover - dependency guidance
            raise RuntimeError("openpyxl is required to import .xlsx files") from exc
        workbook = load_workbook(path, read_only=True, data_only=True)
        sheet = workbook.active
        rows = sheet.iter_rows(values_only=True)
        headers = [clean(value) for value in next(rows, ())]
        return [
            (index, dict(zip(headers, values)))
            for index, values in enumerate(rows, start=2)
        ]
    raise ValueError("unsupported input format; expected .xlsx, .csv, or .json")


def normalized_text(value: str) -> str:
    return re.sub(r"[\W_]+", "", value, flags=re.UNICODE).lower()


def duplicate_values(values: Iterable[str]) -> set[str]:
    normalized = [normalized_text(value) for value in values if value]
    counts = Counter(normalized)
    return {value for value, count in counts.items() if count > 1}


def import_cases(input_path: Path, source_label: str) -> dict[str, Any]:
    rows = load_rows(input_path)
    imported: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    used_case_ids: set[str] = set()
    skipped = 0

    for sequence, (source_row, raw) in enumerate(rows, start=1):
        row = canonical_row(raw)
        if not any(row.values()):
            skipped += 1
            continue
        missing = [
            field
            for field in ("title", "steps", "expected_result")
            if not row[field]
        ]
        if missing:
            warnings.append({
                "type": "missing_key_fields",
                "source_row": source_row,
                "fields": missing,
            })
        source_case_id = row["id"]
        case_id = source_case_id or f"LEGACY_{sequence:04d}"
        if case_id in used_case_ids:
            base_id = case_id
            duplicate_number = 2
            while case_id in used_case_ids:
                case_id = f"{base_id}__DUP_{duplicate_number}"
                duplicate_number += 1
            warnings.append({
                "type": "duplicate_source_id_candidate",
                "case_id": case_id,
                "source_case_id": source_case_id,
                "source_row": source_row,
            })
        used_case_ids.add(case_id)
        origin: dict[str, Any] = {
            "kind": "legacy-import",
            "source_label": source_label,
            "source_row": source_row,
        }
        if source_case_id:
            origin["source_case_id"] = source_case_id
        imported.append({
            "id": case_id,
            "title": row["title"] or f"待补充标题_{sequence:04d}",
            "priority": row["priority"] or "P2",
            "type": row["type"] or "其他",
            "feature": row["feature"] or "待分类",
            "preconditions": row["preconditions"],
            "steps": row["steps"],
            "expected_result": row["expected_result"],
            "tp_refs": [],
            "origin": origin,
            "trust": {
                "status": "unverified",
                "reason": "pending-current-prd-reconciliation",
            },
            "reconciliation": {
                "status": "unresolved",
                "requirement_refs": [],
            },
        })

    duplicate_titles = duplicate_values(case["title"] for case in imported)
    duplicate_bodies = duplicate_values(
        f"{case['preconditions']}|{case['steps']}|{case['expected_result']}"
        for case in imported
    )
    for case in imported:
        if normalized_text(case["title"]) in duplicate_titles:
            warnings.append({
                "type": "duplicate_title_candidate",
                "case_id": case["id"],
                "source_row": case["origin"]["source_row"],
            })
        body = normalized_text(
            f"{case['preconditions']}|{case['steps']}|{case['expected_result']}"
        )
        if body and body in duplicate_bodies:
            warnings.append({
                "type": "duplicate_body_candidate",
                "case_id": case["id"],
                "source_row": case["origin"]["source_row"],
            })

    return {
        "schema_version": 2,
        "_context": {
            "source_skill": "testspec-import",
            "canonical_source_policy": "prd-first",
            "publish_eligibility": "blocked",
            "origin": {"kind": "legacy-import"},
            "trust": {"status": "unverified"},
        },
        "import_summary": {
            "input_rows": len(rows),
            "imported_cases": len(imported),
            "skipped_rows": skipped,
            "warning_count": len(warnings),
        },
        "warnings": warnings,
        "testcases": imported,
    }


def build_reconciliation(imported: dict[str, Any]) -> dict[str, Any]:
    records = [
        {
            "legacy_case_id": case["id"],
            "source_row": case["origin"]["source_row"],
            "status": "unresolved",
            "requirement_refs": [],
            "question_refs": [],
            "replacement_candidate_id": "",
            "reason": "",
        }
        for case in imported["testcases"]
    ]
    return {
        "schema_version": 1,
        "_context": {
            "source_skill": "testspec-import",
            "canonical_source_policy": "prd-first",
            "status": "pending",
        },
        "summary": {
            "keep": 0,
            "revise": 0,
            "merge": 0,
            "retire": 0,
            "unresolved": len(records),
        },
        "records": records,
    }


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Legacy .xlsx, .csv, or .json input")
    parser.add_argument("--output", required=True, help="Isolated staging JSON output")
    parser.add_argument(
        "--reconciliation-output",
        help="Reconciliation JSON output; defaults to reconciliation.json beside --output",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Explicitly replace existing staging outputs",
    )
    parser.add_argument(
        "--source-label",
        default="legacy-source",
        help="Non-sensitive logical label stored in provenance; never use a local path",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    reconciliation_path = (
        Path(args.reconciliation_output)
        if args.reconciliation_output
        else output_path.with_name("reconciliation.json")
    )
    if output_path == reconciliation_path:
        parser.error("--output and --reconciliation-output must be different paths")
    existing = [path.name for path in (output_path, reconciliation_path) if path.exists()]
    if existing and not args.overwrite:
        parser.error(
            "refusing to overwrite existing staging output(s): "
            + ", ".join(existing)
            + "; pass --overwrite only after explicit authorization"
        )

    result = import_cases(input_path, args.source_label)
    reconciliation = build_reconciliation(result)
    write_json(output_path, result)
    write_json(reconciliation_path, reconciliation)
    print(json.dumps({
        **result["import_summary"],
        "reconciliation_records": len(reconciliation["records"]),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
