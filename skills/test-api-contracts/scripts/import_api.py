#!/usr/bin/env python3
"""Inspect and import API definitions or an explicitly requested source-code scan."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from source_adapters import (
    SourceError,
    dump_api_description,
    import_code_source,
    import_source,
    import_yapi_project,
    operation_inventory,
)


def _load(args: argparse.Namespace):
    if args.code_root:
        return import_code_source(
            args.code_root,
            url_prefix=args.code_prefix,
            max_files=args.code_max_files,
            max_bytes=args.code_max_bytes,
        )
    if args.yapi_base_url:
        token = os.environ.get(args.yapi_token_env, "")
        return import_yapi_project(
            args.yapi_base_url,
            args.yapi_project_id,
            token,
            timeout=args.timeout,
        )
    return import_source(args.source)


def _summary(imported) -> dict:
    return {
        **imported.manifest(),
        "operations": operation_inventory(imported.document),
    }


def _add_source_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("source", nargs="?", help="File, raw spec URL, or Swagger UI URL")
    parser.add_argument(
        "--code-root",
        help="Explicitly scan this local source directory and emit an OpenAPI skeleton",
    )
    parser.add_argument(
        "--code-prefix",
        help="Keep discovered routes under these comma-separated URL prefixes",
    )
    parser.add_argument("--code-max-files", type=int, default=5000)
    parser.add_argument("--code-max-bytes", type=int, default=50 * 1024 * 1024)
    parser.add_argument("--yapi-base-url", help="YApi server base URL")
    parser.add_argument("--yapi-project-id", type=int, help="YApi project ID")
    parser.add_argument(
        "--yapi-token-env",
        default="YAPI_TOKEN",
        help="Environment variable containing the YApi project token",
    )
    parser.add_argument("--timeout", type=float, default=20)


def _validate_source_args(args: argparse.Namespace) -> None:
    using_yapi = bool(args.yapi_base_url or args.yapi_project_id)
    using_code = bool(args.code_root)
    if using_yapi and not (args.yapi_base_url and args.yapi_project_id is not None):
        raise SourceError("--yapi-base-url and --yapi-project-id must be used together")
    selected = int(bool(args.source)) + int(using_yapi) + int(using_code)
    if selected != 1:
        raise SourceError(
            "Provide exactly one source: SOURCE, the YApi project options, or --code-root"
        )
    if args.code_prefix and not using_code:
        raise SourceError("--code-prefix requires --code-root")
    if args.command == "import":
        description_name = Path(args.description_name)
        if (
            description_name.is_absolute()
            or len(description_name.parts) != 1
            or description_name.name in {"", ".", "..", "source-manifest.json"}
        ):
            raise SourceError(
                "--description-name must be a filename inside --output-dir "
                "and cannot be source-manifest.json"
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="Detect and summarize a source")
    _add_source_args(inspect_parser)
    inspect_parser.add_argument("--output", "-o", help="Write summary JSON")
    inspect_parser.add_argument("--force", action="store_true", help="Overwrite output")

    import_parser = subparsers.add_parser(
        "import", help="Write the canonical API description and provenance manifest"
    )
    _add_source_args(import_parser)
    import_parser.add_argument("--output-dir", "-o", required=True)
    import_parser.add_argument(
        "--description-name", default="openapi.yaml", help="Output API description filename"
    )
    import_parser.add_argument("--force", action="store_true", help="Overwrite imported artifacts")

    args = parser.parse_args(argv)
    try:
        _validate_source_args(args)
        imported = _load(args)
        summary = _summary(imported)
        if args.command == "inspect":
            payload = json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
            if args.output:
                output = Path(args.output)
                if output.exists() and not args.force:
                    raise SourceError(f"Output already exists; use --force to replace it: {output}")
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(payload, encoding="utf-8")
                print(f"Wrote inspection summary to {output}")
            else:
                print(payload, end="")
            return 0

        output_dir = Path(args.output_dir)
        description_path = output_dir / args.description_name
        manifest_path = output_dir / "source-manifest.json"
        existing = [path for path in (description_path, manifest_path) if path.exists()]
        if existing and not args.force:
            joined = ", ".join(str(path) for path in existing)
            raise SourceError(f"Output already exists; use --force to replace it: {joined}")
        dump_api_description(imported.document, description_path)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(imported.manifest(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Imported {imported.kind} {imported.version}")
        print(f"API description: {description_path}")
        print(f"Source manifest: {manifest_path}")
        for warning in imported.warnings:
            print(f"WARNING: {warning}", file=sys.stderr)
        for feature in imported.unsupported_features:
            print(f"UNSUPPORTED: {feature}", file=sys.stderr)
        return 0
    except SourceError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
