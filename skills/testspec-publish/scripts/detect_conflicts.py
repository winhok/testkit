#!/usr/bin/env python3
"""Detect deterministic TestLib publish conflicts without modifying files."""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any


def normalize_title(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).casefold().strip()
    text = re.sub(r"[\s_\-—–/]+", " ", text)
    text = re.sub(r"[^\w\u3400-\u9fff ]+", "", text)
    return " ".join(text.split())


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def existing_cases(testlib: Path):
    modules = testlib / "modules"
    if not modules.exists():
        return
    for path in sorted(modules.rglob("*.json")):
        data = load_json(path)
        for case in data.get("cases", []):
            yield path, case


def detect(incoming_path: Path, testlib: Path) -> dict[str, Any]:
    incoming_data = load_json(incoming_path)
    incoming_cases = incoming_data.get("testcases")
    if not isinstance(incoming_cases, list):
        raise ValueError("incoming JSON must contain a testcases array")

    existing = list(existing_cases(testlib))
    updates: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []

    for incoming in incoming_cases:
        incoming_id = str(incoming.get("id", ""))
        incoming_title = str(incoming.get("title", ""))
        incoming_feature = str(incoming.get("feature", ""))
        incoming_key = incoming.get("scenario_key")
        normalized_incoming = normalize_title(incoming_title)

        for path, current in existing:
            current_id = str(current.get("id", ""))
            current_title = str(current.get("title", ""))
            current_feature = str(current.get("feature", ""))
            current_key = current.get("scenario_key")

            if incoming_id and incoming_id == current_id:
                if incoming_feature == current_feature:
                    updates.append(
                        {
                            "kind": "same_id_update",
                            "incoming_id": incoming_id,
                            "existing_id": current_id,
                            "existing_file": str(path),
                        }
                    )
                else:
                    conflicts.append(
                        {
                            "kind": "same_id_cross_feature",
                            "incoming_id": incoming_id,
                            "existing_id": current_id,
                            "incoming_feature": incoming_feature,
                            "existing_feature": current_feature,
                            "existing_file": str(path),
                        }
                    )
                continue

            same_title = (
                bool(normalized_incoming)
                and normalized_incoming == normalize_title(current_title)
            )
            same_scenario_key = (
                incoming_key is not None
                and current_key is not None
                and str(incoming_key) == str(current_key)
            )
            if same_title or same_scenario_key:
                conflicts.append(
                    {
                        "kind": (
                            "different_id_same_title"
                            if same_title
                            else "different_id_same_scenario_key"
                        ),
                        "incoming_id": incoming_id,
                        "existing_id": current_id,
                        "incoming_title": incoming_title,
                        "existing_title": current_title,
                        "normalized_title": normalized_incoming if same_title else None,
                        "scenario_key": incoming_key if same_scenario_key else None,
                        "existing_file": str(path),
                    }
                )

    return {
        "incoming_count": len(incoming_cases),
        "same_id_updates": updates,
        "conflicts": conflicts,
        "conflict_count": len(conflicts),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--incoming", required=True, type=Path)
    parser.add_argument("--testlib", required=True, type=Path)
    parser.add_argument("--fail-on-conflict", action="store_true")
    args = parser.parse_args()

    try:
        report = detect(args.incoming, args.testlib)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1

    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.fail_on_conflict and report["conflict_count"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
