#!/usr/bin/env python3
"""Inspect OpenAPI and generate Postman, Apifox, or JMeter artifacts."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from generator import JmxGenerator
from parsers import HTTP_METHODS, OpenApiParser


class ArtifactError(ValueError):
    """Raised for source, configuration, or conversion failures."""


def _load_source(source: str) -> tuple[Path, OpenApiParser, dict[str, Any], bytes]:
    path = Path(source).expanduser().resolve()
    if not path.is_file():
        raise ArtifactError(f"Source file not found: {path}")
    raw = path.read_bytes()
    if len(raw) > 20 * 1024 * 1024:
        raise ArtifactError("Source exceeds the 20 MiB limit")
    parser = OpenApiParser()
    try:
        document = parser.parse(str(path))
    except (ValueError, ImportError, json.JSONDecodeError) as exc:
        raise ArtifactError(str(exc)) from exc
    return path, parser, document, raw


def _operations(document: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    items: list[tuple[str, str, dict[str, Any]]] = []
    for path, path_item in document.get("paths", {}).items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method.lower() in HTTP_METHODS and isinstance(operation, dict):
                items.append((method.upper(), path, operation))
    return items


def inspect_source(source: str) -> dict[str, Any]:
    path, parser, document, raw = _load_source(source)
    operations = _operations(document)
    servers = (
        document.get("servers", [])
        if parser.version != "2.0"
        else [{"url": parser.get_base_url()}] if parser.get_base_url() else []
    )
    unresolved_servers = [
        server.get("url", "")
        for server in servers
        if isinstance(server, dict) and "{" in str(server.get("url", ""))
    ]
    missing_operation_ids = [
        f"{method} {path}"
        for method, path, operation in operations
        if not operation.get("operationId")
    ]
    missing_success_responses = []
    for method, path, operation in operations:
        responses = operation.get("responses", {})
        has_success = isinstance(responses, dict) and any(
            str(code).isdigit() and 200 <= int(str(code)) < 300 for code in responses
        )
        if not has_success:
            missing_success_responses.append(f"{method} {path}")
    return {
        "source": str(path),
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "source_kind": "swagger" if parser.version == "2.0" else "openapi",
        "source_version": parser.version,
        "operation_count": len(operations),
        "unresolved_server_variables": unresolved_servers,
        "missing_operation_ids": missing_operation_ids,
        "operations_without_documented_success": missing_success_responses,
    }


def _artifact_name(document: dict[str, Any]) -> str:
    title = str(document.get("info", {}).get("title", "api")).strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", title).strip("-")
    return value or "api"


def _target_paths(
    source_path: Path,
    document: dict[str, Any],
    output_dir: Path,
    targets: list[str],
) -> dict[str, Path]:
    name = _artifact_name(document)
    suffix = ".json" if source_path.suffix.lower() == ".json" else ".yaml"
    paths = {"manifest": output_dir / "artifact-manifest.json"}
    if "apifox" in targets:
        paths["apifox"] = output_dir / f"{name}.apifox-openapi{suffix}"
    if "postman" in targets:
        paths["postman"] = output_dir / f"{name}.postman_collection.json"
    if "jmeter" in targets:
        paths["jmeter"] = output_dir / f"{name}.jmx"
    return paths


def _preflight(paths: dict[str, Path], force: bool) -> None:
    existing = [str(path) for path in paths.values() if path.exists()]
    if existing and not force:
        raise ArtifactError(
            "Output already exists; use --force to replace it: " + ", ".join(existing)
        )


def _jmeter_base_url(parser: OpenApiParser, override: str | None) -> str:
    value = override or parser.get_base_url()
    parsed = urllib.parse.urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or "{" in value
        or "}" in value
    ):
        raise ArtifactError(
            "JMeter generation requires a concrete credential-free HTTP(S) base URL; "
            "set an OpenAPI server or pass --base-url."
        )
    return value


def _generate_postman(
    source_path: Path,
    output_path: Path,
    converter: str,
) -> None:
    executable = shutil.which(converter)
    if executable is None:
        raise ArtifactError(
            f"Postman converter not found: {converter}. "
            "Install openapi-to-postmanv2 or pass --postman-converter."
        )
    result = subprocess.run(
        [
            executable,
            "-s",
            str(source_path),
            "-o",
            str(output_path),
            "-p",
            "-O",
            "folderStrategy=Tags,requestParametersResolution=Example",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode:
        raise ArtifactError(
            "Postman conversion failed: "
            + (result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}")
        )
    try:
        collection = json.loads(output_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactError(f"Postman converter produced invalid JSON: {exc}") from exc
    schema = str(collection.get("info", {}).get("schema", ""))
    if "collection/v2.1" not in schema:
        raise ArtifactError("Postman converter did not produce Collection v2.1")


def generate(args: argparse.Namespace) -> dict[str, Any]:
    source_path, parser, document, raw = _load_source(args.source)
    targets = list(dict.fromkeys(args.target))
    output_dir = Path(args.output_dir).expanduser().resolve()
    paths = _target_paths(source_path, document, output_dir, targets)
    _preflight(paths, args.force)
    jmeter_base_url = (
        _jmeter_base_url(parser, args.base_url) if "jmeter" in targets else None
    )
    if "postman" in targets and shutil.which(args.postman_converter) is None:
        raise ArtifactError(
            f"Postman converter not found: {args.postman_converter}. "
            "Install openapi-to-postmanv2 or pass --postman-converter."
        )
    output_dir.mkdir(parents=True, exist_ok=True)

    generated: list[dict[str, str]] = []
    warnings: list[str] = []
    follow_ups: list[str] = []
    if "apifox" in targets:
        paths["apifox"].write_bytes(raw)
        generated.append(
            {"target": "apifox", "path": str(paths["apifox"]), "format": parser.version}
        )
        follow_ups.append(
            "Preview the Apifox import and choose duplicate handling; native test suites "
            "are not generated from OpenAPI."
        )

    if "postman" in targets:
        _generate_postman(source_path, paths["postman"], args.postman_converter)
        generated.append(
            {"target": "postman", "path": str(paths["postman"]), "format": "2.1"}
        )
        follow_ups.append(
            "Review generated examples, collection variables, auth placeholders, and folders."
        )

    if "jmeter" in targets:
        generator = JmxGenerator()
        generator.generate_from_openapi(
            str(source_path),
            test_plan_name=str(document.get("info", {}).get("title", "API load skeleton")),
            num_threads=args.threads,
            ramp_time=args.ramp_seconds,
            loops=args.loops,
            base_url=jmeter_base_url,
        )
        generator.save_jmx(str(paths["jmeter"]))
        generated.append(
            {"target": "jmeter", "path": str(paths["jmeter"]), "format": "JMX"}
        )
        warnings.append(
            "JMX is a sampler skeleton, not a reviewed workload model; no traffic mix, "
            "pacing, dynamic correlation, test data, or cleanup was inferred."
        )
        follow_ups.append(
            "Review workload, request order, correlation, data uniqueness, assertions, "
            "timeouts, cleanup, and monitoring before load execution."
        )

    summary = inspect_source(str(source_path))
    manifest = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        **summary,
        "requested_targets": targets,
        "generated": generated,
        "warnings": warnings,
        "manual_follow_ups": follow_ups,
    }
    paths["manifest"].write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def _positive(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def main(argv: list[str] | None = None) -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    commands = cli.add_subparsers(dest="command", required=True)

    inspect_parser = commands.add_parser("inspect", help="Inspect without writing artifacts")
    inspect_parser.add_argument("source")

    generate_parser = commands.add_parser("generate", help="Generate target artifacts")
    generate_parser.add_argument("source")
    generate_parser.add_argument(
        "--target",
        action="append",
        choices=("postman", "apifox", "jmeter"),
        required=True,
    )
    generate_parser.add_argument("--output-dir", required=True)
    generate_parser.add_argument("--postman-converter", default="openapi2postmanv2")
    generate_parser.add_argument(
        "--base-url",
        help="Concrete credential-free HTTP(S) base URL for the JMeter target",
    )
    generate_parser.add_argument("--threads", type=_positive, default=1)
    generate_parser.add_argument("--ramp-seconds", type=_positive, default=1)
    generate_parser.add_argument("--loops", type=_positive, default=1)
    generate_parser.add_argument("--force", action="store_true")

    args = cli.parse_args(argv)
    try:
        result = inspect_source(args.source) if args.command == "inspect" else generate(args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except ArtifactError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
