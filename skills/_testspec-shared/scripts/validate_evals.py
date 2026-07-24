#!/usr/bin/env python3
"""Validate deterministic, synthetic TestSpec eval definitions."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[3]
EVAL_PATHS = sorted((ROOT / "skills").glob("testspec-*/evals/evals.json"))
EVAL_PATHS.append(ROOT / "skills" / "_testspec-shared" / "evals" / "evals.json")

AMBIENT_SELECTORS = ("find testspec/changes", "head -1")
URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+")
EXTERNAL_TICKET_PATTERN = re.compile(r"\bT\d{3,}\b")
ABSOLUTE_HOME_PATTERN = re.compile(r"(?:/Users/|/home/|[A-Za-z]:\\Users\\)")
EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
IPV4_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
UUID_PATTERN = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)
PRIVATE_PATH_MARKERS = (".cursor/projects", "agent-transcripts")


def iter_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from iter_strings(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from iter_strings(item)


def validate_eval_file(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{path}: {exc}"]

    policy = data.get("fixture_policy")
    if policy != {"origin": "synthetic", "contains_proprietary_data": False}:
        errors.append(f"{path}: fixture_policy must declare synthetic, non-proprietary data")

    evals = data.get("evals")
    if not isinstance(evals, list) or not evals:
        errors.append(f"{path}: evals must be a non-empty array")
        return errors

    seen_ids: set[Any] = set()
    for case in evals:
        case_id = case.get("id")
        prefix = f"{path}: eval {case_id!r}"
        if case_id in seen_ids:
            errors.append(f"{prefix}: duplicate id")
        seen_ids.add(case_id)

        files = case.get("files")
        if not isinstance(files, list) or not files:
            errors.append(f"{prefix}: deterministic eval requires at least one fixture file")
        else:
            for fixture in files:
                fixture_path = fixture.get("path", "")
                pure = Path(fixture_path)
                if not fixture_path or pure.is_absolute() or ".." in pure.parts:
                    errors.append(f"{prefix}: unsafe fixture path {fixture_path!r}")
                if "content" not in fixture:
                    errors.append(f"{prefix}: fixture {fixture_path!r} lacks inline content")

        assertions = case.get("assertions")
        if not isinstance(assertions, list) or len(assertions) < 3:
            errors.append(f"{prefix}: requires at least three assertions")
            continue
        if not any(item.get("check") == "programmatic" for item in assertions):
            errors.append(f"{prefix}: requires at least one programmatic assertion")

        for assertion in assertions:
            if assertion.get("check") == "programmatic":
                script = assertion.get("script", "")
                if not script:
                    errors.append(f"{prefix}: programmatic assertion lacks script")
                if any(token in script for token in AMBIENT_SELECTORS):
                    errors.append(f"{prefix}: assertion uses ambient workspace selector")

        for text in iter_strings(case):
            if EXTERNAL_TICKET_PATTERN.search(text):
                errors.append(f"{prefix}: contains external ticket-like identifier")
            if ABSOLUTE_HOME_PATTERN.search(text):
                errors.append(f"{prefix}: contains an absolute user-home path")
            if EMAIL_PATTERN.search(text):
                errors.append(f"{prefix}: contains an email address")
            if IPV4_PATTERN.search(text):
                errors.append(f"{prefix}: contains an IPv4 address")
            if UUID_PATTERN.search(text):
                errors.append(f"{prefix}: contains a UUID-like identifier")
            if any(marker in text for marker in PRIVATE_PATH_MARKERS):
                errors.append(f"{prefix}: contains a private transcript path marker")
            for url in URL_PATTERN.findall(text):
                hostname = (urlparse(url).hostname or "").lower()
                if hostname and hostname != "example.invalid":
                    errors.append(f"{prefix}: URL host must be example.invalid, got {hostname}")

    return errors


def main() -> int:
    errors: list[str] = []
    for path in EVAL_PATHS:
        errors.extend(validate_eval_file(path))
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print(f"PASS: validated {len(EVAL_PATHS)} synthetic TestSpec eval files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
