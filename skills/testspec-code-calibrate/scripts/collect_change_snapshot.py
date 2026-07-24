#!/usr/bin/env python3
"""Collect a privacy-safe Git change snapshot without persisting diff content."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


SAFE_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
HUNK_HEADER = re.compile(
    r"^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))? "
    r"\+(?P<new_start>\d+)(?:,(?P<new_count>\d+))? @@"
)


def run_git(repo: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", "-c", "core.quotePath=false", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if check and result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or "git command failed"
        raise RuntimeError(detail)
    return result.stdout


def safe_scope(value: str) -> bool:
    if value == ".":
        return True
    if (
        not value
        or value.startswith(("/", "~"))
        or "\\" in value
        or "://" in value
        or any(ord(char) < 32 for char in value)
    ):
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts and not value.endswith("/")


def resolve(repo: Path, ref: str) -> str:
    value = run_git(repo, "rev-parse", "--verify", f"{ref}^{{commit}}").strip()
    if not re.fullmatch(r"[0-9a-fA-F]{40,64}", value):
        raise RuntimeError(f"cannot resolve Git ref: {ref}")
    return value.lower()


def diff_command(args: argparse.Namespace, scopes: list[str]) -> tuple[list[str], str]:
    stable_options = [
        "--no-ext-diff",
        "--no-textconv",
        "--no-color",
        "--src-prefix=a/",
        "--dst-prefix=b/",
        "--unified=0",
    ]
    if args.staged:
        command = ["diff", "--cached", *stable_options, args.base_ref]
        mode = "staged"
    elif args.include_worktree:
        command = ["diff", *stable_options, args.base_ref]
        mode = "worktree"
    else:
        separator = ".." if args.diff_mode == "two-dot" else "..."
        command = [
            "diff",
            *stable_options,
            f"{args.base_ref}{separator}{args.head_ref}",
        ]
        mode = args.diff_mode
    if scopes != ["."]:
        command.extend(["--", *scopes])
    return command, mode


def changed_paths(repo: Path, command: list[str]) -> list[str]:
    name_command = [*command]
    name_command.insert(1, "--name-only")
    name_command.insert(2, "-z")
    raw = run_git(repo, *name_command)
    return sorted({item for item in raw.split("\0") if item})


def file_numstat(repo: Path, command: list[str], path: str) -> tuple[int | None, int | None]:
    scoped = [*command]
    if "--" in scoped:
        scoped = scoped[: scoped.index("--")]
    scoped.insert(1, "--numstat")
    scoped.extend(["--", path])
    output = run_git(repo, *scoped).strip()
    if not output:
        return 0, 0
    first = output.splitlines()[0].split("\t", 2)
    if len(first) < 2 or first[0] == "-" or first[1] == "-":
        return None, None
    return int(first[0]), int(first[1])


def file_status(repo: Path, command: list[str], path: str) -> str:
    scoped = [*command]
    if "--" in scoped:
        scoped = scoped[: scoped.index("--")]
    scoped.insert(1, "--name-status")
    scoped.extend(["--", path])
    output = run_git(repo, *scoped).strip()
    return output.split("\t", 1)[0] if output else "M"


def hunk_ranges(raw_diff: str) -> dict[str, list[dict[str, int]]]:
    current = ""
    old_path = ""
    result: dict[str, list[dict[str, int]]] = {}
    for line in raw_diff.splitlines():
        if line.startswith("--- a/"):
            old_path = line[6:]
            continue
        if line.startswith("+++ b/"):
            current = line[6:]
            result.setdefault(current, [])
            continue
        if line == "+++ /dev/null":
            current = old_path
            if current:
                result.setdefault(current, [])
            continue
        if not current:
            continue
        match = HUNK_HEADER.match(line)
        if not match:
            continue
        old_count = int(match.group("old_count") or "1")
        new_count = int(match.group("new_count") or "1")
        result[current].append(
            {
                "old_start": int(match.group("old_start")),
                "old_count": old_count,
                "new_start": int(match.group("new_start")),
                "new_count": new_count,
            }
        )
    return result


def collect(args: argparse.Namespace) -> dict[str, Any]:
    repo = Path(args.repo_root).resolve()
    if run_git(repo, "rev-parse", "--is-inside-work-tree").strip() != "true":
        raise RuntimeError("repo root is not a Git worktree")

    scopes = list(dict.fromkeys(args.scope))
    if any(not safe_scope(scope) for scope in scopes):
        raise RuntimeError("scope must contain repository-relative paths only")
    if "." in scopes and len(scopes) > 1:
        raise RuntimeError("root scope cannot be combined with narrower scopes")
    for label in (args.repository_label, args.base_label, args.head_label):
        if not SAFE_LABEL.fullmatch(label):
            raise RuntimeError("repository/base/head labels must be non-sensitive safe labels")

    base_commit = resolve(repo, args.base_ref)
    head_commit = resolve(repo, "HEAD" if args.include_worktree or args.staged else args.head_ref)
    command, mode = diff_command(args, scopes)
    raw_diff = run_git(repo, *command)
    paths = changed_paths(repo, command)
    if any(not safe_scope(path) or path == "." for path in paths):
        raise RuntimeError(
            "a changed file path cannot be represented safely in the snapshot"
        )
    ranges = hunk_ranges(raw_diff)
    files: list[dict[str, Any]] = []
    total_additions = 0
    total_deletions = 0
    binary_files = 0
    for path in paths:
        additions, deletions = file_numstat(repo, command, path)
        if additions is None or deletions is None:
            binary_files += 1
        else:
            total_additions += additions
            total_deletions += deletions
        files.append(
            {
                "path": path,
                "status": file_status(repo, command, path),
                "additions": additions,
                "deletions": deletions,
                "hunks": ranges.get(path, []),
            }
        )

    status_command = ["status", "--porcelain"]
    if scopes != ["."]:
        status_command.extend(["--", *scopes])
    dirty = bool(run_git(repo, *status_command).strip())
    warnings: list[str] = []
    if dirty and not args.include_worktree and not args.staged:
        warnings.append("worktree-dirty-but-excluded")
    if not raw_diff:
        warnings.append("empty-diff")

    merge_base = ""
    if not args.include_worktree and not args.staged:
        merge_base = run_git(
            repo,
            "merge-base",
            args.base_ref,
            args.head_ref,
            check=False,
        ).strip()

    collected_at = datetime.now(timezone.utc).isoformat()
    digest = "sha256:" + hashlib.sha256(raw_diff.encode("utf-8")).hexdigest()
    snapshot_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        + "-"
        + digest[-8:]
    )
    return {
        "schema_version": 1,
        "snapshot_id": snapshot_id,
        "repository_label": args.repository_label,
        "comparison": {
            "mode": mode,
            "base_label": args.base_label,
            "head_label": args.head_label,
            "base_commit": base_commit,
            "head_commit": head_commit,
            "merge_base": merge_base or None,
            "include_worktree": bool(args.include_worktree),
            "staged": bool(args.staged),
        },
        "scope": scopes,
        "collected_at": collected_at,
        "worktree_dirty": dirty,
        "diff_digest": digest,
        "stats": {
            "file_count": len(files),
            "hunk_count": sum(len(item["hunks"]) for item in files),
            "additions": total_additions,
            "deletions": total_deletions,
            "binary_files": binary_files,
        },
        "warnings": warnings,
        "files": files,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--repository-label", required=True)
    parser.add_argument("--base-ref", required=True)
    parser.add_argument("--head-ref", default="HEAD")
    parser.add_argument("--base-label", required=True)
    parser.add_argument("--head-label", required=True)
    parser.add_argument("--scope", action="append", required=True)
    parser.add_argument("--diff-mode", choices=("three-dot", "two-dot"), default="three-dot")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--include-worktree", action="store_true")
    modes.add_argument("--staged", action="store_true")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    if args.output.exists() and not args.overwrite:
        parser.error("refusing to overwrite an existing change snapshot")
    try:
        result = collect(args)
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "ok",
                "snapshot_id": result["snapshot_id"],
                "file_count": result["stats"]["file_count"],
                "warnings": result["warnings"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
