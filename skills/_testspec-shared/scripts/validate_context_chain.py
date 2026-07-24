#!/usr/bin/env python3
"""Validate TestSpec context propagation for one change directory."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


STAGES = {
    "analysis": ("requirements-analysis.md", "testspec-analysis"),
    "points": ("specs/testpoints.md", "testspec-points"),
    "generate": ("artifacts/testcases.json", "testspec-generate"),
    "review": ("review-report.md", "testspec-review"),
}

SELF_ARTIFACT_NAMES = {
    "analysis": {"requirements-analysis.md"},
    "points": {"testpoints.md", "specs/testpoints.md"},
    "generate": {"testcases.json", "artifacts/testcases.json"},
    "review": {"review-report.md"},
}

REQUIRED_ENVELOPE_FIELDS = {
    "source_revision",
    "blocking_open_questions",
    "dynamic_followups",
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
    return json.loads(matches[-1])


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
    if expected_version is not None and canonical_version != expected_version:
        errors.append(
            f"canonical source_revision.version={canonical_version!r}, "
            f"expected {expected_version}"
        )

    through_index = list(STAGES).index(through)
    for stage, (relative_path, expected_skill) in list(STAGES.items())[: through_index + 1]:
        path = change_dir / relative_path
        if not path.exists() and stage == "generate":
            fallback = change_dir / "testcases.json"
            if fallback.exists():
                path = fallback
        if not path.exists():
            errors.append(f"{stage}: missing {relative_path}")
            continue

        try:
            context = load_context(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(str(exc))
            continue

        if context.get("source_skill") != expected_skill:
            errors.append(
                f"{stage}: source_skill={context.get('source_skill')!r}, "
                f"expected {expected_skill!r}"
            )

        if canonical_version is None:
            if context.get("source_revision") is not None:
                errors.append(f"{stage}: legacy canonical source must not gain a fabricated revision")
            continue

        missing = sorted(REQUIRED_ENVELOPE_FIELDS - context.keys())
        if missing:
            errors.append(f"{stage}: missing envelope fields: {', '.join(missing)}")

        if context.get("source_revision") != canonical_revision:
            errors.append(f"{stage}: source_revision differs from canonical source")

        stale = context.get("stale_downstream_artifacts")
        if not isinstance(stale, list):
            errors.append(f"{stage}: stale_downstream_artifacts must be an array")
            continue
        stale_names = {str(item) for item in stale}
        if stale_names & SELF_ARTIFACT_NAMES[stage]:
            errors.append(f"{stage}: propagated stale list still contains its own artifact")
        if not stale and ("stale_reason" in context or "next_skill" in context):
            errors.append(f"{stage}: empty stale list must omit stale_reason and next_skill")

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
    print("PASS: TestSpec context chain is consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
