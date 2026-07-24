#!/usr/bin/env python3
"""Validate a privacy-safe TestSpec Git change snapshot."""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any


SAFE_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
COMMIT = re.compile(r"^[0-9a-f]{40,64}$")
SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
SNAPSHOT_ID = re.compile(r"^\d{8}T\d{12}Z-[0-9a-f]{8}$")
GIT_STATUS = re.compile(r"^[ACDMRTUXB](?:\d{1,3})?$")
FORBIDDEN_KEYS = {"raw_diff", "snippet", "repo_root", "repository_path", "remote_url"}
ABSOLUTE_PATH = re.compile(
    r"(?:/Users/|/home/|[A-Za-z]:\\Users\\|"
    r"(?:^|[\s\"'`(])/(?:tmp|private|var|root|workspace|Volumes)/)"
)
URL = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PRIVATE_MARKERS = (".cursor/projects", "agent-transcripts")


def safe_path(value: Any, *, allow_root: bool = False) -> bool:
    if value == ".":
        return allow_root
    if not isinstance(value, str) or not value or value.startswith(("/", "~")):
        return False
    if (
        "\\" in value
        or "://" in value
        or value.endswith("/")
        or any(ord(char) < 32 for char in value)
    ):
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts


def unknown_keys(value: dict[str, Any], allowed: set[str], prefix: str) -> list[str]:
    extra = sorted(set(value) - allowed)
    return [f"{prefix} contains unsupported fields: {', '.join(extra)}"] if extra else []


def contains_forbidden_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any(key in FORBIDDEN_KEYS or contains_forbidden_key(item) for key, item in value.items())
    if isinstance(value, list):
        return any(contains_forbidden_key(item) for item in value)
    return False


def iter_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from iter_strings(key)
            yield from iter_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from iter_strings(item)


def validate(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    errors.extend(
        unknown_keys(
            data,
            {
                "schema_version",
                "snapshot_id",
                "repository_label",
                "comparison",
                "scope",
                "collected_at",
                "worktree_dirty",
                "diff_digest",
                "stats",
                "warnings",
                "files",
            },
            "snapshot",
        )
    )
    if data.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if not isinstance(data.get("snapshot_id"), str) or not SNAPSHOT_ID.fullmatch(data["snapshot_id"]):
        errors.append("snapshot_id is invalid")
    if not isinstance(data.get("repository_label"), str) or not SAFE_LABEL.fullmatch(data["repository_label"]):
        errors.append("repository_label must be a safe non-sensitive label")
    if not isinstance(data.get("diff_digest"), str) or not SHA256.fullmatch(data["diff_digest"]):
        errors.append("diff_digest must be sha256")
    try:
        collected_at = datetime.fromisoformat(str(data.get("collected_at")))
    except ValueError:
        collected_at = None
    if collected_at is None or collected_at.tzinfo is None:
        errors.append("collected_at must be an ISO timestamp")
    if type(data.get("worktree_dirty")) is not bool:
        errors.append("worktree_dirty must be boolean")
    if contains_forbidden_key(data):
        errors.append("snapshot must not persist raw diff, snippets, repository roots, or remotes")
    for value in iter_strings(data):
        if ABSOLUTE_PATH.search(value):
            errors.append("snapshot contains a private absolute path")
        if URL.search(value):
            errors.append("snapshot contains a remote URL")
        if EMAIL.search(value):
            errors.append("snapshot contains an email address")
        if any(marker in value for marker in PRIVATE_MARKERS):
            errors.append("snapshot contains a private workspace identifier")

    comparison = data.get("comparison")
    if not isinstance(comparison, dict):
        errors.append("comparison must be an object")
        comparison = {}
    else:
        errors.extend(
            unknown_keys(
                comparison,
                {
                    "mode",
                    "base_label",
                    "head_label",
                    "base_commit",
                    "head_commit",
                    "merge_base",
                    "include_worktree",
                    "staged",
                },
                "comparison",
            )
        )
    mode = comparison.get("mode")
    if mode not in {"three-dot", "two-dot", "worktree", "staged"}:
        errors.append("comparison.mode is invalid")
    for field in ("base_label", "head_label"):
        value = comparison.get(field)
        if not isinstance(value, str) or not SAFE_LABEL.fullmatch(value):
            errors.append(f"comparison.{field} must be a safe label")
    for field in ("base_commit", "head_commit"):
        value = comparison.get(field)
        if not isinstance(value, str) or not COMMIT.fullmatch(value):
            errors.append(f"comparison.{field} must be a full commit hash")
    merge_base = comparison.get("merge_base")
    if merge_base is not None and (
        not isinstance(merge_base, str) or not COMMIT.fullmatch(merge_base)
    ):
        errors.append("comparison.merge_base must be null or a full commit hash")
    if type(comparison.get("include_worktree")) is not bool:
        errors.append("comparison.include_worktree must be boolean")
    if type(comparison.get("staged")) is not bool:
        errors.append("comparison.staged must be boolean")
    if mode == "worktree" and comparison.get("include_worktree") is not True:
        errors.append("worktree mode must set include_worktree=true")
    if mode == "staged" and comparison.get("staged") is not True:
        errors.append("staged mode must set staged=true")
    if mode in {"three-dot", "two-dot"} and (
        comparison.get("include_worktree") or comparison.get("staged")
    ):
        errors.append("commit-only modes cannot include worktree or staged changes")

    scopes = data.get("scope")
    if not isinstance(scopes, list) or not scopes:
        errors.append("scope must be a non-empty array")
        scopes = []
    elif any(not safe_path(item, allow_root=True) for item in scopes):
        errors.append("scope contains an unsafe path")
    elif len(set(scopes)) != len(scopes) or ("." in scopes and len(scopes) > 1):
        errors.append("scope contains duplicates or overlaps root")

    files = data.get("files")
    if not isinstance(files, list):
        errors.append("files must be an array")
        files = []
    seen_paths: set[str] = set()
    additions = deletions = binary_files = hunk_count = 0
    for index, item in enumerate(files):
        prefix = f"files[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        errors.extend(
            unknown_keys(
                item,
                {"path", "status", "additions", "deletions", "hunks"},
                prefix,
            )
        )
        path = item.get("path")
        if not safe_path(path):
            errors.append(f"{prefix}.path must be repository-relative")
        elif path in seen_paths:
            errors.append(f"{prefix}.path is duplicated")
        else:
            seen_paths.add(path)
            if scopes and not any(
                scope == "." or path == scope or path.startswith(scope.rstrip("/") + "/")
                for scope in scopes
            ):
                errors.append(f"{prefix}.path is outside snapshot scope")
        if (
            not isinstance(item.get("status"), str)
            or not GIT_STATUS.fullmatch(item["status"])
        ):
            errors.append(f"{prefix}.status is not a supported Git name-status code")
        add = item.get("additions")
        delete = item.get("deletions")
        if add is None and delete is None:
            binary_files += 1
        elif type(add) is not int or type(delete) is not int or add < 0 or delete < 0:
            errors.append(f"{prefix} additions/deletions must be non-negative or both null")
        else:
            additions += add
            deletions += delete
        hunks = item.get("hunks")
        if not isinstance(hunks, list):
            errors.append(f"{prefix}.hunks must be an array")
            continue
        hunk_count += len(hunks)
        for hunk_index, hunk in enumerate(hunks):
            hunk_prefix = f"{prefix}.hunks[{hunk_index}]"
            if not isinstance(hunk, dict):
                errors.append(f"{hunk_prefix} must be an object")
                continue
            errors.extend(
                unknown_keys(
                    hunk,
                    {"old_start", "old_count", "new_start", "new_count"},
                    hunk_prefix,
                )
            )
            for field in ("old_start", "old_count", "new_start", "new_count"):
                value = hunk.get(field)
                minimum = 0
                if type(value) is not int or value < minimum:
                    errors.append(f"{hunk_prefix}.{field} is invalid")

    stats = data.get("stats")
    expected_stats = {
        "file_count": len(files),
        "hunk_count": hunk_count,
        "additions": additions,
        "deletions": deletions,
        "binary_files": binary_files,
    }
    if stats != expected_stats:
        errors.append("stats do not match files")
    warnings = data.get("warnings")
    if not isinstance(warnings, list) or any(not isinstance(item, str) for item in warnings):
        errors.append("warnings must be an array of strings")
    elif len(warnings) != len(set(warnings)):
        errors.append("warnings contain duplicates")
    return list(dict.fromkeys(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    args = parser.parse_args()
    try:
        data = json.loads(args.input.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("top level must be an object")
        errors = validate(data)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors = [str(exc)]
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("PASS: change snapshot is privacy-safe and internally consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
