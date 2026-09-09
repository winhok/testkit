#!/usr/bin/env python3
"""Validate repository-wide skill structure, eval hygiene, and routing coverage."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
ROUTING_EVALS = ROOT / "evals" / "skill-routing.json"
FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
ROUTING_URL = re.compile(r"https?://[^\s\"'<>]+")
ROUTING_PRIVATE_PATTERNS = (
    (re.compile(r"(?:/Users/|/home/|[A-Za-z]:\\Users\\)"), "absolute user-home path"),
    (re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE), "email address"),
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "IPv4 address"),
    (
        re.compile(
            r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
            re.IGNORECASE,
        ),
        "UUID-like identifier",
    ),
)


def _public_skill_dirs() -> list[Path]:
    return sorted(
        path
        for path in SKILLS.iterdir()
        if path.is_dir() and not path.name.startswith("_") and (path / "SKILL.md").is_file()
    )


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{path.relative_to(ROOT)}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{path.relative_to(ROOT)}: root must be an object")
    return payload


def _iter_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _iter_strings(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from _iter_strings(item)


def _frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER.match(text)
    if match is None:
        raise ValueError(f"{path.relative_to(ROOT)}: missing YAML frontmatter")
    try:
        metadata = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        raise ValueError(f"{path.relative_to(ROOT)}: invalid frontmatter: {exc}") from exc
    if not isinstance(metadata, dict):
        raise ValueError(f"{path.relative_to(ROOT)}: frontmatter must be an object")
    return metadata, text


def validate() -> list[str]:
    errors: list[str] = []
    public_dirs = _public_skill_dirs()
    public_names = {path.name for path in public_dirs}
    if not public_dirs:
        return ["skills/: no public skills found"]

    if (SKILLS / "__init__.py").exists():
        errors.append("skills/__init__.py: repository skills root must not be a Python package")

    for directory in public_dirs:
        skill_file = directory / "SKILL.md"
        try:
            metadata, text = _frontmatter(skill_file)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        relative = skill_file.relative_to(ROOT)
        allowed = {"name", "description", "license", "allowed-tools", "metadata"}
        extra = sorted(set(metadata) - allowed)
        if extra:
            errors.append(f"{relative}: unsupported frontmatter fields: {', '.join(extra)}")
        if metadata.get("name") != directory.name:
            errors.append(f"{relative}: name must match directory {directory.name}")
        description = metadata.get("description")
        if not isinstance(description, str) or len(description.strip()) < 50:
            errors.append(f"{relative}: description must contain at least 50 characters")
        if metadata.get("license") != "MIT":
            errors.append(f"{relative}: license must be MIT")
        line_count = len(text.splitlines())
        if line_count > 500:
            errors.append(f"{relative}: SKILL.md has {line_count} lines; maximum is 500")
        for reference in sorted((directory / "references").glob("*.md")):
            if reference.name not in text:
                errors.append(
                    f"{reference.relative_to(ROOT)}: reference is not routed from SKILL.md"
                )

        eval_path = directory / "evals" / "evals.json"
        if not eval_path.is_file():
            errors.append(f"{directory.relative_to(ROOT)}: missing public behavioral evals")
        else:
            try:
                data = _load_json(eval_path)
            except ValueError as exc:
                errors.append(str(exc))
                continue
            if data.get("skill_name") != directory.name:
                errors.append(f"{eval_path.relative_to(ROOT)}: skill_name mismatch")
            if data.get("fixture_policy") != {
                "origin": "synthetic",
                "contains_proprietary_data": False,
            }:
                errors.append(
                    f"{eval_path.relative_to(ROOT)}: fixture_policy must be synthetic and non-proprietary"
                )
            evals = data.get("evals")
            if not isinstance(evals, list) or not evals:
                errors.append(f"{eval_path.relative_to(ROOT)}: evals must be non-empty")

    try:
        routing = _load_json(ROUTING_EVALS)
    except ValueError as exc:
        errors.append(str(exc))
        routing = {}
    if routing.get("schema_version") != 1:
        errors.append("evals/skill-routing.json: schema_version must be 1")
    if routing.get("fixture_policy") != {
        "origin": "synthetic",
        "contains_proprietary_data": False,
    }:
        errors.append("evals/skill-routing.json: fixture_policy must be synthetic and non-proprietary")
    cases = routing.get("cases")
    if not isinstance(cases, list):
        errors.append("evals/skill-routing.json: cases must be an array")
        cases = []
    seen_ids: set[str] = set()
    positive: set[str] = set()
    excluded: set[str] = set()
    for case in cases:
        if not isinstance(case, dict):
            errors.append("evals/skill-routing.json: each case must be an object")
            continue
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id:
            errors.append("evals/skill-routing.json: each case requires a string id")
            continue
        if case_id in seen_ids:
            errors.append(f"evals/skill-routing.json: duplicate case id {case_id}")
        seen_ids.add(case_id)
        kind = case.get("kind")
        expected = case.get("expected_skill")
        forbidden = case.get("forbidden_skills")
        if kind not in {"should-trigger", "near-miss"}:
            errors.append(f"evals/skill-routing.json: {case_id} has invalid kind")
        if expected is not None and expected not in public_names:
            errors.append(f"evals/skill-routing.json: {case_id} has unknown expected_skill {expected}")
        if not isinstance(forbidden, list) or not all(
            isinstance(name, str) and name in public_names for name in forbidden
        ):
            errors.append(f"evals/skill-routing.json: {case_id} has invalid forbidden_skills")
            forbidden = []
        if expected in forbidden:
            errors.append(f"evals/skill-routing.json: {case_id} both expects and forbids {expected}")
        prompt = case.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            errors.append(f"evals/skill-routing.json: {case_id} requires a prompt")
        if kind == "should-trigger" and isinstance(expected, str):
            positive.add(expected)
        if kind == "near-miss":
            excluded.update(forbidden)
            contrast = case.get("contrast_with")
            if not isinstance(contrast, str) or not contrast:
                errors.append(f"evals/skill-routing.json: {case_id} requires contrast_with")
        for value in _iter_strings(case):
            for pattern, label in ROUTING_PRIVATE_PATTERNS:
                if pattern.search(value):
                    errors.append(
                        f"evals/skill-routing.json: {case_id} contains {label}"
                    )
            if ".cursor/projects" in value or "agent-transcripts" in value:
                errors.append(
                    f"evals/skill-routing.json: {case_id} contains a private transcript path marker"
                )
            for url in ROUTING_URL.findall(value):
                hostname = (urlparse(url).hostname or "").lower()
                if hostname and not (
                    hostname == "example.invalid"
                    or hostname.endswith(".example.invalid")
                ):
                    errors.append(
                        f"evals/skill-routing.json: {case_id} contains a non-synthetic URL"
                    )

    missing_positive = sorted(public_names - positive)
    missing_negative = sorted(public_names - excluded)
    if missing_positive:
        errors.append(
            "evals/skill-routing.json: missing should-trigger coverage for "
            + ", ".join(missing_positive)
        )
    if missing_negative:
        errors.append(
            "evals/skill-routing.json: missing near-miss exclusion coverage for "
            + ", ".join(missing_negative)
        )
    for case in cases:
        if isinstance(case, dict) and case.get("kind") == "near-miss":
            contrast = case.get("contrast_with")
            if isinstance(contrast, str) and contrast not in seen_ids:
                errors.append(
                    f"evals/skill-routing.json: {case.get('id')} references unknown contrast {contrast}"
                )

    tracked = subprocess.run(
        ["git", "ls-files", "skills"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if tracked.returncode == 0:
        for item in tracked.stdout.splitlines():
            if "__pycache__" in Path(item).parts or item.endswith((".pyc", ".pyo")):
                errors.append(f"{item}: generated Python cache must not be tracked")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print(f"PASS: validated {len(_public_skill_dirs())} public skills and routing boundaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
