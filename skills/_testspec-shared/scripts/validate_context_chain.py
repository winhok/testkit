#!/usr/bin/env python3
"""Validate TestSpec context schema v2 propagation for one change directory."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
from validate_question_graph import validate_context as validate_question_context  # noqa: E402


STAGES = {
    "analysis": ("requirements-analysis.md", "testspec-analysis"),
    "plan": ("strategy.md", "testspec-plan"),
    "points": ("specs/testpoints.md", "testspec-points"),
    "generate": ("artifacts/testcases.json", "testspec-generate"),
    "review": ("review-report.md", "testspec-review"),
}
SELF_ARTIFACT_NAMES = {
    "analysis": {"requirements-analysis.md"},
    "plan": {"strategy.md"},
    "points": {"testpoints.md", "specs/testpoints.md"},
    "generate": {"testcases.json", "artifacts/testcases.json"},
    "review": {"review-report.md"},
}
REQUIRED_ENVELOPE_FIELDS = {
    "context_schema_version",
    "source_revision",
    "questions",
    "strategy_requirement",
    "material_quality",
    "stale_downstream_artifacts",
}


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


def json_context(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    context = data.get("_context")
    if not isinstance(context, dict):
        raise ValueError(f"{path}: missing object _context")
    return context


def load_context(path: Path) -> dict[str, Any]:
    return json_context(path) if path.suffix == ".json" else markdown_context(path)


def canonical_path(change_dir: Path) -> Path:
    requirements = change_dir / "requirements.md"
    if requirements.exists():
        return requirements
    proposal = change_dir / "proposal.md"
    if proposal.exists():
        return proposal
    raise ValueError(f"{change_dir}: missing requirements.md and proposal.md")


def _strategy_requirement(context: dict[str, Any], label: str) -> tuple[str | None, list[str]]:
    errors: list[str] = []
    requirement = context.get("strategy_requirement")
    if not isinstance(requirement, dict):
        return None, [f"{label}: strategy_requirement must be an object"]
    status = requirement.get("status")
    if status not in {"required", "skipped"}:
        errors.append(f"{label}: strategy_requirement.status must be required or skipped")
    reasons = requirement.get("reasons")
    if not isinstance(reasons, list) or not reasons or not all(
        isinstance(item, str) and item.strip() for item in reasons
    ):
        errors.append(f"{label}: strategy_requirement.reasons must be a non-empty string array")
    return status, errors


def _artifact_path(change_dir: Path, stage: str) -> Path:
    relative_path = STAGES[stage][0]
    return change_dir / relative_path


def _stage_order(change_dir: Path, through: str, plan_required: bool) -> list[str]:
    order = ["analysis"]
    if through == "analysis":
        return order
    if plan_required or through == "plan" or (change_dir / "strategy.md").exists():
        order.append("plan")
    if through != "plan":
        order.extend(["points", "generate", "review"])
        order = order[: order.index(through) + 1]
    return order


def validate_analysis_authority(canonical: dict[str, Any], analysis: dict[str, Any]) -> list[str]:
    """Analysis may verify facts/add questions, but cannot author product decisions."""
    original_questions = canonical.get('questions')
    updated_questions = analysis.get('questions')
    if not isinstance(original_questions, list) or not isinstance(updated_questions, list):
        return []  # The question/schema validator reports malformed registries.
    original = {q['id']: q for q in original_questions if isinstance(q, dict) and isinstance(q.get('id'), str)}
    updated = {q['id']: q for q in updated_questions if isinstance(q, dict) and isinstance(q.get('id'), str)}
    errors = []
    for question_id, item in original.items():
        if item.get('kind') == 'decision' and updated.get(question_id) != item:
            errors.append(f'analysis: canonical decision {question_id} must be preserved unchanged; product changes require testspec-update')
    for question_id, item in updated.items():
        if item.get('kind') == 'decision' and original.get(question_id, {}).get('kind') != 'decision':
            if item.get('status') not in ('open', 'deferred') or item.get('resolution') is not None:
                errors.append(f'analysis: new decision {question_id} must remain unresolved until testspec-update')
    return errors


def validate(change_dir: Path, through: str, expected_version: int | None) -> list[str]:
    errors: list[str] = []
    try:
        canonical = load_context(canonical_path(change_dir))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [str(exc)]

    canonical_revision = canonical.get("source_revision")
    canonical_version = (
        canonical_revision.get("version")
        if isinstance(canonical_revision, dict)
        else None
    )
    if not isinstance(canonical_version, int) or canonical_version < 1:
        errors.append("canonical source_revision.version must be a positive integer")
    if expected_version is not None and canonical_version != expected_version:
        errors.append(
            f"canonical source_revision.version={canonical_version!r}, expected {expected_version}"
        )
    missing = sorted(REQUIRED_ENVELOPE_FIELDS - canonical.keys())
    if missing:
        errors.append(f"canonical: missing envelope fields: {', '.join(missing)}")
    errors.extend(
        f"canonical: {error}" for error in validate_question_context(canonical, target_stage="analysis")
    )
    _, strategy_errors = _strategy_requirement(canonical, "canonical")
    errors.extend(strategy_errors)

    analysis_path = _artifact_path(change_dir, "analysis")
    analysis_context: dict[str, Any] | None = None
    if analysis_path.exists():
        try:
            analysis_context = load_context(analysis_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(str(exc))
    strategy_source = analysis_context or canonical
    plan_status, plan_status_errors = _strategy_requirement(strategy_source, "analysis")
    errors.extend(plan_status_errors)
    plan_required = plan_status == "required"

    previous_context = canonical
    for stage in _stage_order(change_dir, through, plan_required):
        relative_path, expected_skill = STAGES[stage]
        path = _artifact_path(change_dir, stage)
        if not path.exists():
            errors.append(f"{stage}: missing {relative_path}")
            continue
        try:
            context = analysis_context if stage == "analysis" and analysis_context is not None else load_context(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(str(exc))
            continue
        assert context is not None

        errors.extend(
            f"{stage}: {error}"
            for error in validate_question_context(previous_context, target_stage=stage)
        )
        errors.extend(f"{stage}: {error}" for error in validate_question_context(context))
        if context.get("source_skill") != expected_skill:
            errors.append(
                f"{stage}: source_skill={context.get('source_skill')!r}, expected {expected_skill!r}"
            )
        missing = sorted(REQUIRED_ENVELOPE_FIELDS - context.keys())
        if missing:
            errors.append(f"{stage}: missing envelope fields: {', '.join(missing)}")
        if context.get("source_revision") != canonical_revision:
            errors.append(f"{stage}: source_revision differs from canonical source")

        _, stage_strategy_errors = _strategy_requirement(context, stage)
        errors.extend(stage_strategy_errors)
        if stage == 'analysis':
            errors.extend(validate_analysis_authority(canonical, context))
        else:
            if context.get("questions") != previous_context.get("questions"):
                errors.append(f"{stage}: questions differ from direct upstream")
            if context.get("strategy_requirement") != previous_context.get("strategy_requirement"):
                errors.append(f"{stage}: strategy_requirement differs from direct upstream")

        stale = context.get("stale_downstream_artifacts")
        if not isinstance(stale, list):
            errors.append(f"{stage}: stale_downstream_artifacts must be an array")
        else:
            stale_names = {str(item) for item in stale}
            if stale_names & SELF_ARTIFACT_NAMES[stage]:
                errors.append(f"{stage}: propagated stale list still contains its own artifact")
            if not stale and ("stale_reason" in context or "next_skill" in context):
                errors.append(f"{stage}: empty stale list must omit stale_reason and next_skill")
        previous_context = context
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--change-dir", required=True, type=Path)
    parser.add_argument("--through", required=True, choices=tuple(STAGES))
    parser.add_argument("--expected-version", type=int)
    args = parser.parse_args()

    errors = validate(args.change_dir, args.through, args.expected_version)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("PASS: TestSpec context schema v2 chain is consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
