#!/usr/bin/env python3
"""Migrate one TestSpec change from the legacy context schema to v2."""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from validate_question_graph import validate_context


MARKDOWN_CONTEXT = re.compile(
    r"<!--\s*testspec-context\s*(\{.*?\})\s*-->",
    flags=re.DOTALL,
)
ARTIFACT_PATHS = (
    "proposal.md",
    "requirements.md",
    "requirements-analysis.md",
    "strategy.md",
    "specs/testpoints.md",
    "artifacts/testcases.json",
    "review-report.md",
)
ALL_DOWNSTREAM_STAGES = ["analysis", "plan", "points", "generate", "review", "publish"]


def _load_artifact(path: Path) -> tuple[Any, dict[str, Any]]:
    if path.suffix == ".json":
        text = path.read_text(encoding="utf-8")
        root = json.loads(text)
        if not isinstance(root, dict) or not isinstance(root.get("_context"), dict):
            raise ValueError(f"{path}: missing object _context")
        return text, root["_context"]
    text = path.read_text(encoding="utf-8")
    matches = list(MARKDOWN_CONTEXT.finditer(text))
    if not matches:
        raise ValueError(f"{path}: missing testspec-context block")
    context = json.loads(matches[-1].group(1))
    if not isinstance(context, dict):
        raise ValueError(f"{path}: testspec-context must be an object")
    return text, context


def _atomic_write(path: Path, text: str) -> None:
    original_mode = path.stat().st_mode & 0o777
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        os.chmod(temporary, original_mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _write_artifact(path: Path, root: Any, context: dict[str, Any]) -> None:
    if path.suffix == ".json":
        key = re.search(r'(?m)^([ \t]*)"_context"\s*:\s*', root)
        if key is None:
            raise ValueError(f"{path}: missing _context key")
        start = key.end()
        _, consumed = json.JSONDecoder().raw_decode(root[start:])
        end = start + consumed
        lines = json.dumps(context, ensure_ascii=False, indent=2).splitlines()
        replacement = lines[0]
        if len(lines) > 1:
            replacement += "\n" + "\n".join(key.group(1) + line for line in lines[1:])
        _atomic_write(path, root[:start] + replacement + root[end:])
        return
    matches = list(MARKDOWN_CONTEXT.finditer(root))
    match = matches[-1]
    replacement = "<!-- testspec-context\n" + json.dumps(
        context, ensure_ascii=False, indent=2
    ) + "\n-->"
    _atomic_write(path, root[: match.start()] + replacement + root[match.end() :])


def _question_overrides(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not all(
        isinstance(key, str) and isinstance(item, dict) for key, item in value.items()
    ):
        raise ValueError("question map must be an object keyed by Q-ID")
    return value


def _legacy_questions(
    contexts: list[dict[str, Any]],
    overrides: dict[str, dict[str, Any]],
    warnings: list[str] | None = None,
) -> list[dict[str, Any]]:
    ordered: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_text: set[str] = set()
    blocking_text: set[str] = set()
    dynamic_text: set[str] = set()

    canonical_has_registry = any(
        isinstance(item, dict)
        and isinstance(item.get("id"), str)
        and isinstance(item.get("question"), str)
        for item in contexts[0].get("questions", [])
    )
    registry_contexts = contexts[:1] if canonical_has_registry else contexts
    for context in contexts:
        blocking_text.update(
            item for item in context.get("blocking_open_questions", []) if isinstance(item, str)
        )
        dynamic_text.update(
            item for item in context.get("dynamic_followups", []) if isinstance(item, str)
        )
    for context in registry_contexts:
        for item in context.get("questions", []):
            if not isinstance(item, dict):
                continue
            question_id = item.get("id")
            text = item.get("question")
            if not isinstance(question_id, str) or not isinstance(text, str):
                continue
            if question_id in seen_ids:
                continue
            ordered.append(copy.deepcopy(item))
            seen_ids.add(question_id)
            seen_text.add(text)

    next_number = 1
    compatibility_only = [] if canonical_has_registry else [
        *((item, True) for item in sorted(blocking_text - seen_text)),
        *((item, False) for item in sorted(dynamic_text - seen_text)),
    ]
    for text, blocking in compatibility_only:
        while f"Q-{next_number:03d}" in seen_ids:
            next_number += 1
        question_id = f"Q-{next_number:03d}"
        ordered.append(
            {
                "id": question_id,
                "status": "open",
                "question": text,
                "_legacy_blocking": blocking,
            }
        )
        seen_ids.add(question_id)
        next_number += 1

    migrated: list[dict[str, Any]] = []
    for item in ordered:
        question_id = item["id"]
        override = overrides.get(question_id, {})
        text = item["question"]
        legacy_blocking = bool(item.pop("_legacy_blocking", False)) or bool(
            item.get("blocking")
        ) or text in blocking_text
        status = item.get("status") if item.get("status") in {
            "open", "resolved", "invalidated", "deferred"
        } else "open"
        old_resolution = item.get("resolution")
        kind = override.get("kind", item.get("kind"))
        if kind not in {"fact", "decision"}:
            kind = "decision" if legacy_blocking or status in {"resolved", "invalidated"} else "fact"
            if warnings is not None:
                warnings.append(
                    f"{question_id}: inferred kind={kind}; confirm with --question-map"
                )

        recommendation = override.get("recommendation", item.get("recommendation"))
        if isinstance(recommendation, str) and recommendation.strip():
            recommendation = {"value": recommendation, "status": "proposed"}
        if not isinstance(recommendation, dict):
            recommendation = None

        resolution = override.get("resolution", old_resolution)
        if resolution is None and isinstance(old_resolution, str) and old_resolution.strip():
            resolution = {
                "outcome": "accepted" if kind == "decision" else "verified",
                "value": old_resolution,
                "source_ref": item.get("source", "legacy-context"),
            }
        elif isinstance(resolution, str) and resolution.strip():
            resolution = {
                "outcome": "accepted" if kind == "decision" else "verified",
                "value": resolution,
                "source_ref": item.get("source", "legacy-context"),
            }
        if status == "open":
            resolution = None

        depends_on = override.get("depends_on", item.get("depends_on", []))
        blocks_stages = override.get(
            "blocks_stages",
            ALL_DOWNSTREAM_STAGES if legacy_blocking and status in {"open", "deferred"} else [],
        )
        question: dict[str, Any] = {
            "id": question_id,
            "kind": kind,
            "status": status,
            "question": text,
            "depends_on": depends_on,
            "blocks_stages": blocks_stages,
            "recommendation": recommendation,
            "resolution": resolution,
        }
        for key in ("affects", "source"):
            if key in item:
                question[key] = item[key]
        migrated.append(question)
    return migrated


def migrate(
    change_dir: Path,
    *,
    question_map: Path | None = None,
    write: bool = False,
) -> tuple[list[Path], list[str], list[str]]:
    paths = [change_dir / relative for relative in ARTIFACT_PATHS]
    paths = [path for path in paths if path.exists()]
    if not paths:
        return [], [f"{change_dir}: no TestSpec artifacts found"], []

    loaded: list[tuple[Path, Any, dict[str, Any]]] = []
    errors: list[str] = []
    for path in paths:
        try:
            root, context = _load_artifact(path)
            loaded.append((path, root, context))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(str(exc))
    if errors:
        return [], errors, []

    if all(context.get("context_schema_version") == 2 for _, _, context in loaded):
        for path, _, context in loaded:
            errors.extend(f"{path}: {error}" for error in validate_context(context))
        return [], errors, []

    canonical_path = change_dir / "requirements.md"
    if not canonical_path.exists():
        canonical_path = change_dir / "proposal.md"
    canonical_index = next(
        (index for index, item in enumerate(loaded) if item[0] == canonical_path), None
    )
    if canonical_index is None:
        return [], [f"{change_dir}: missing requirements.md and proposal.md context"], []
    ordered_contexts = [loaded[canonical_index][2]] + [
        item[2] for index, item in enumerate(loaded) if index != canonical_index
    ]
    canonical_strategy = ordered_contexts[0].get("strategy_requirement")
    if not (
        isinstance(canonical_strategy, dict)
        and canonical_strategy.get("status") in {"required", "skipped"}
        and isinstance(canonical_strategy.get("reasons"), list)
        and canonical_strategy["reasons"]
    ):
        canonical_strategy = {
            "status": "skipped",
            "reasons": ["migrated-existing-revision"],
        }

    warnings: list[str] = []
    try:
        overrides = _question_overrides(question_map)
        questions = _legacy_questions(
            ordered_contexts,
            overrides,
            warnings,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [], [str(exc)], warnings
    unknown_overrides = sorted(set(overrides) - {item["id"] for item in questions})
    if unknown_overrides:
        return [], ["question map contains unknown IDs: " + ", ".join(unknown_overrides)], warnings

    changed: list[Path] = []
    migrated_items: list[tuple[Path, Any, dict[str, Any]]] = []
    for path, root, old_context in loaded:
        context = copy.deepcopy(old_context)
        context["context_schema_version"] = 2
        context["questions"] = copy.deepcopy(questions)
        context["strategy_requirement"] = copy.deepcopy(canonical_strategy)
        context.pop("blocking_open_questions", None)
        context.pop("dynamic_followups", None)
        validation_errors = validate_context(context)
        if validation_errors:
            errors.extend(f"{path}: {error}" for error in validation_errors)
            continue
        migrated_items.append((path, root, context))
        if context != old_context:
            changed.append(path)

    if errors:
        return [], errors, warnings
    if write and warnings:
        return [], ["question classification review required before --write"], warnings
    if write:
        for path, root, context in migrated_items:
            _write_artifact(path, root, context)
    return changed, [], warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--change-dir", required=True, type=Path)
    parser.add_argument("--question-map", type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    args = parser.parse_args()

    changed, errors, warnings = migrate(
        args.change_dir,
        question_map=args.question_map,
        write=args.write,
    )
    for warning in warnings:
        print(f"REVIEW: {warning}")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    if not changed:
        print("PASS: change already uses TestSpec context schema v2")
        return 0
    action = "migrated" if args.write else "would migrate"
    for path in changed:
        print(f"{action}: {path}")
    if args.check:
        print("MIGRATION REQUIRED: rerun with --write")
        return 2
    print(f"PASS: migrated {len(changed)} TestSpec artifacts to context schema v2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
