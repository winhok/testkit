#!/usr/bin/env python3
"""Rebuild TestLib index.json and .testlib.json from feature files."""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any


DEFAULT_TESTLIB = Path("testspec/testlib")
STATUS_KEYS = ("active", "deprecated", "archived")
PRIORITY_KEYS = ("P1", "P2", "P3")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def feature_files(testlib: Path) -> list[Path]:
    modules_dir = testlib / "modules"
    if not modules_dir.exists():
        return []
    return sorted(modules_dir.glob("*/*.json"))


def feature_path(path: Path, testlib: Path) -> str:
    return path.relative_to(testlib / "modules").with_suffix("").as_posix()


def related_paths(doc: dict[str, Any]) -> list[str]:
    refs = []
    for item in doc.get("related_features") or []:
        if isinstance(item, dict) and item.get("path"):
            refs.append(str(item["path"]))
        elif isinstance(item, str):
            refs.append(item)
    return sorted(set(refs))


def compact_counter(counter: Counter[str], preferred_keys: tuple[str, ...] = ()) -> dict[str, int]:
    result: dict[str, int] = {}
    for key in preferred_keys:
        if counter.get(key):
            result[key] = counter[key]
    for key in sorted(k for k in counter if k not in preferred_keys):
        if counter[key]:
            result[key] = counter[key]
    return result


def collect_feature(path: Path, testlib: Path) -> dict[str, Any]:
    doc = read_json(path)
    cases = doc.get("cases") or []
    priorities = Counter(str(case.get("priority", "")) for case in cases if case.get("priority"))
    statuses = Counter(str(case.get("status", "")) for case in cases if case.get("status"))
    tp_ids = sorted({
        str(tp_id)
        for case in cases
        for tp_id in (case.get("tp_refs") or [])
        if tp_id
    })
    rel = path.relative_to(testlib / "modules").as_posix()

    return {
        "module": str(doc.get("module", "")),
        "module_key": str(doc.get("module_key", "")),
        "dir": path.parent.name,
        "feature": str(doc.get("feature", "")),
        "feature_key": str(doc.get("feature_key", "")),
        "file": rel,
        "case_count": len(cases),
        "by_priority": compact_counter(priorities, PRIORITY_KEYS),
        "by_status": compact_counter(statuses, STATUS_KEYS),
        "tp_ids": tp_ids,
        "last_updated": str(doc.get("last_updated", "")),
        "related_features": related_paths(doc),
    }


def build_index(testlib: Path, today: str) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in feature_files(testlib):
        grouped[path.parent.name].append(collect_feature(path, testlib))

    modules = []
    for module_dir in sorted(grouped):
        features = sorted(grouped[module_dir], key=lambda item: item["file"])
        first = features[0]
        modules.append({
            "module": first["module"],
            "module_key": first["module_key"],
            "dir": module_dir,
            "features": [
                {
                    "feature": feature["feature"],
                    "feature_key": feature["feature_key"],
                    "file": feature["file"],
                    "case_count": feature["case_count"],
                    "by_priority": feature["by_priority"],
                    "by_status": feature["by_status"],
                    "tp_ids": feature["tp_ids"],
                    "last_updated": feature["last_updated"],
                    "related_features": feature["related_features"],
                }
                for feature in features
            ],
            "total_cases": sum(feature["case_count"] for feature in features),
            "last_updated": max((feature["last_updated"] for feature in features), default=""),
        })

    return {
        "schema_version": 1,
        "last_updated": today,
        "modules": modules,
    }


def build_config(testlib: Path, today: str, existing: dict[str, Any] | None = None) -> dict[str, Any]:
    status_counts: Counter[str] = Counter()
    priority_counts: Counter[str] = Counter()
    total_cases = 0

    for path in feature_files(testlib):
        doc = read_json(path)
        cases = doc.get("cases") or []
        total_cases += len(cases)
        status_counts.update(str(case.get("status", "")) for case in cases if case.get("status"))
        priority_counts.update(str(case.get("priority", "")) for case in cases if case.get("priority"))

    modules = {path.parent.name for path in feature_files(testlib)}
    created_at = today
    if existing:
        created_at = str(existing.get("created_at") or today)

    return {
        "schema_version": 1,
        "created_at": created_at,
        "last_updated": today,
        "stats": {
            "total_modules": len(modules),
            "total_features": len(feature_files(testlib)),
            "total_cases": total_cases,
            "by_status": compact_counter(status_counts, STATUS_KEYS),
            "by_priority": compact_counter(priority_counts, PRIORITY_KEYS),
        },
    }


def rebuild(testlib: Path, today: str) -> dict[str, Any]:
    testlib.mkdir(parents=True, exist_ok=True)
    (testlib / "modules").mkdir(parents=True, exist_ok=True)
    (testlib / "changelog").mkdir(parents=True, exist_ok=True)

    existing_config = read_json(testlib / ".testlib.json") if (testlib / ".testlib.json").exists() else None
    index = build_index(testlib, today)
    config = build_config(testlib, today, existing_config)

    write_json(testlib / "index.json", index)
    write_json(testlib / ".testlib.json", config)
    return {
        "index": index,
        "config": config,
        "feature_files": len(feature_files(testlib)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--testlib", default=str(DEFAULT_TESTLIB), help="Path to testspec/testlib")
    parser.add_argument("--date", default=date.today().isoformat(), help="YYYY-MM-DD date for generated metadata")
    args = parser.parse_args()

    result = rebuild(Path(args.testlib), args.date)
    print(json.dumps({
        "status": "ok",
        "feature_files": result["feature_files"],
        "index": "index.json",
        "config": ".testlib.json",
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
