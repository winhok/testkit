#!/usr/bin/env python3
"""Validate a TestSpec context v2 question dependency graph."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


CONTEXT_SCHEMA_VERSION = 2
QUESTION_ID = re.compile(r"Q-\d{3,}")
QUESTION_KINDS = {"fact", "decision"}
QUESTION_STATUSES = {"open", "resolved", "invalidated", "deferred"}
STAGES = {"analysis", "plan", "points", "generate", "review", "publish"}
ACTIVE_STATUSES = {"open", "deferred"}
DECISION_OUTCOMES = {"accepted", "modified", "rejected"}
FACT_OUTCOMES = {"verified", "refuted", "inconclusive"}


def markdown_context(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    matches = re.findall(
        r"<!--\s*testspec-context\s*(\{.*?\})\s*-->",
        text,
        flags=re.DOTALL,
    )
    if not matches:
        raise ValueError(f"{path}: missing testspec-context block")
    value = json.loads(matches[-1])
    if not isinstance(value, dict):
        raise ValueError(f"{path}: testspec-context must be an object")
    return value


def load_context(path: Path) -> dict[str, Any]:
    if path.suffix.lower() in {".md", ".markdown"}:
        return markdown_context(path)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: JSON root must be an object")
    context = value.get("_context", value)
    if not isinstance(context, dict):
        raise ValueError(f"{path}: _context must be an object")
    return context


def _nonempty_strings(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) == len(set(value))
        and all(isinstance(item, str) and item.strip() for item in value)
    )


def _validate_recommendation(question_id: str, value: Any, errors: list[str]) -> None:
    if value is None:
        return
    if not isinstance(value, dict):
        errors.append(f"{question_id}: recommendation must be null or an object")
        return
    if value.get("status") != "proposed":
        errors.append(f"{question_id}: recommendation.status must be 'proposed'")
    answer = value.get("value")
    if not isinstance(answer, str) or not answer.strip():
        errors.append(f"{question_id}: recommendation.value must be a non-empty string")


def _validate_resolution(
    question_id: str,
    kind: Any,
    status: Any,
    value: Any,
    errors: list[str],
) -> None:
    if status == "open" and value is not None:
        errors.append(f"{question_id}: open question must have null resolution")
        return
    if status == "resolved" and not isinstance(value, dict):
        errors.append(f"{question_id}: resolved question requires an object resolution")
        return
    if value is None:
        return
    if not isinstance(value, dict):
        errors.append(f"{question_id}: resolution must be null or an object")
        return

    outcome = value.get("outcome")
    allowed = DECISION_OUTCOMES if kind == "decision" else FACT_OUTCOMES
    if outcome not in allowed:
        errors.append(
            f"{question_id}: resolution.outcome={outcome!r} is invalid for kind={kind!r}"
        )
    if status == "resolved" and outcome in {"rejected", "inconclusive"}:
        errors.append(
            f"{question_id}: outcome {outcome!r} cannot use resolved status"
        )
    if status == "invalidated" and kind == "decision" and outcome not in {None, "rejected"}:
        errors.append(f"{question_id}: invalidated decision may only use rejected outcome")
    if status == "deferred" and outcome not in {None, "inconclusive"}:
        errors.append(f"{question_id}: deferred question may only use inconclusive outcome")
    resolution_text = value.get("value")
    if outcome is not None and (not isinstance(resolution_text, str) or not resolution_text.strip()):
        errors.append(f"{question_id}: resolution.value must describe the outcome")
    source_ref = value.get("source_ref")
    if outcome is not None and (not isinstance(source_ref, str) or not source_ref.strip()):
        errors.append(f"{question_id}: resolution.source_ref must identify the evidence or decision")


def _cycles(graph: dict[str, list[str]]) -> list[list[str]]:
    state: dict[str, int] = {}
    stack: list[str] = []
    cycles: list[list[str]] = []

    def visit(node: str) -> None:
        marker = state.get(node, 0)
        if marker == 2:
            return
        if marker == 1:
            start = stack.index(node)
            cycles.append(stack[start:] + [node])
            return
        state[node] = 1
        stack.append(node)
        for dependency in graph.get(node, []):
            if dependency in graph:
                visit(dependency)
        stack.pop()
        state[node] = 2

    for node in graph:
        visit(node)
    return cycles


def frontier(context: dict[str, Any]) -> list[str]:
    questions = context.get("questions")
    if not isinstance(questions, list):
        return []
    by_id = {
        item.get("id"): item
        for item in questions
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    ready: list[str] = []
    for question_id, item in by_id.items():
        if item.get("status") != "open":
            continue
        dependencies = item.get("depends_on")
        if not isinstance(dependencies, list):
            continue
        if all(
            dependency in by_id and by_id[dependency].get("status") == "resolved"
            for dependency in dependencies
        ):
            ready.append(question_id)
    return sorted(ready)


def validate_context(
    context: dict[str, Any],
    *,
    target_stage: str | None = None,
) -> list[str]:
    errors: list[str] = []
    if context.get("context_schema_version") != CONTEXT_SCHEMA_VERSION:
        errors.append(
            f"context_schema_version must be {CONTEXT_SCHEMA_VERSION}; run migrate_change_context.py"
        )

    questions = context.get("questions")
    if not isinstance(questions, list):
        return errors + ["questions must be an array"]

    by_id: dict[str, dict[str, Any]] = {}
    graph: dict[str, list[str]] = {}
    for index, item in enumerate(questions):
        if not isinstance(item, dict):
            errors.append(f"questions[{index}] must be an object")
            continue
        missing_fields = sorted(
            {
                "id",
                "kind",
                "status",
                "question",
                "depends_on",
                "blocks_stages",
                "recommendation",
                "resolution",
            }
            - item.keys()
        )
        if missing_fields:
            errors.append(
                f"questions[{index}] missing required fields: {', '.join(missing_fields)}"
            )
        question_id = item.get("id")
        if not isinstance(question_id, str) or not QUESTION_ID.fullmatch(question_id):
            errors.append(f"questions[{index}].id must match Q-###")
            continue
        if question_id in by_id:
            errors.append(f"duplicate question id: {question_id}")
            continue
        by_id[question_id] = item

        kind = item.get("kind")
        status = item.get("status")
        if kind not in QUESTION_KINDS:
            errors.append(f"{question_id}: kind must be fact or decision")
        if status not in QUESTION_STATUSES:
            errors.append(f"{question_id}: invalid status {status!r}")
        text = item.get("question")
        if not isinstance(text, str) or not text.strip():
            errors.append(f"{question_id}: question must be a non-empty string")

        dependencies = item.get("depends_on")
        if not _nonempty_strings(dependencies):
            errors.append(f"{question_id}: depends_on must be an array of unique question IDs")
            dependencies = []
        graph[question_id] = list(dependencies)

        blocks = item.get("blocks_stages")
        if not _nonempty_strings(blocks):
            errors.append(f"{question_id}: blocks_stages must be an array of unique stage names")
        elif unknown := sorted(set(blocks) - STAGES):
            errors.append(f"{question_id}: unknown blocked stages: {', '.join(unknown)}")

        _validate_recommendation(question_id, item.get("recommendation"), errors)
        _validate_resolution(question_id, kind, status, item.get("resolution"), errors)

    for question_id, dependencies in graph.items():
        for dependency in dependencies:
            if dependency == question_id:
                errors.append(f"{question_id}: question cannot depend on itself")
            elif dependency not in by_id:
                errors.append(f"{question_id}: unknown dependency {dependency}")
    for cycle in _cycles(graph):
        errors.append("question dependency cycle: " + " -> ".join(cycle))

    if target_stage is not None:
        if target_stage not in STAGES:
            errors.append(f"unknown target stage: {target_stage}")
        else:
            ready = set(frontier(context))
            for question_id, item in by_id.items():
                if item.get("status") not in ACTIVE_STATUSES:
                    continue
                blocks = item.get("blocks_stages")
                if not isinstance(blocks, list) or target_stage not in blocks:
                    continue
                errors.append(f"{target_stage}: blocked by unresolved question {question_id}")
                unresolved_dependencies = [
                    dependency
                    for dependency in graph.get(question_id, [])
                    if dependency in by_id
                    and by_id[dependency].get("status") != "resolved"
                ]
                if question_id not in ready and unresolved_dependencies:
                    errors.append(
                        f"{target_stage}: hidden blocker {question_id} waits for "
                        + ", ".join(unresolved_dependencies)
                    )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--target-stage", choices=sorted(STAGES))
    parser.add_argument("--print-frontier", action="store_true")
    args = parser.parse_args()

    try:
        context = load_context(args.input)
        errors = validate_context(context, target_stage=args.target_stage)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors = [str(exc)]
        context = {}

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    if args.print_frontier:
        print(json.dumps(frontier(context), ensure_ascii=False))
    print("PASS: TestSpec question graph is valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
