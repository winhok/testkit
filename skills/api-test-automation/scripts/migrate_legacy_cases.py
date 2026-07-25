#!/usr/bin/env python3
"""Migrate a legacy API automation project into an Arazzo 1.1 document."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from legacy_case_adapter import LegacyMigrationError, migrate_legacy_project


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    targets = [args.output, *([args.manifest] if args.manifest else [])]
    resolved_targets = [path.resolve() for path in targets]
    if len(set(resolved_targets)) != len(resolved_targets):
        print(
            "configuration: workflow output and manifest must be distinct",
            file=sys.stderr,
        )
        return 2
    protected = {args.project.resolve(), args.schema.resolve()}
    if set(resolved_targets) & protected:
        print(
            "configuration: outputs must not overwrite project.yaml or the schema",
            file=sys.stderr,
        )
        return 2
    existing = [str(path) for path in targets if path and path.exists()]
    if existing and not args.force:
        print(
            "configuration: output already exists: " + ", ".join(existing),
            file=sys.stderr,
        )
        return 2
    try:
        manifest = migrate_legacy_project(args.project, args.schema, args.output)
        if args.manifest:
            args.manifest.parent.mkdir(parents=True, exist_ok=True)
            args.manifest.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
    except LegacyMigrationError as exc:
        print(f"conversion: {exc}", file=sys.stderr)
        return 2
    print(
        f"migrated {manifest['workflow_count']} workflows -> {args.output}; "
        f"required env: {', '.join(manifest['required_environment']) or 'none'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
