#!/usr/bin/env python3
"""Run deterministic Arazzo API workflows."""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from typing import Any

from workflow_engine import (
    WorkflowConfigurationError,
    WorkflowError,
    WorkflowRunner,
    WorkflowTransportError,
)
from workflow_reports import ReportWriteError, write_allure_results, write_junit


class CliConfigurationError(ValueError):
    """Raised for invalid CLI input before any network request."""


def _typed(value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _assign(items: list[str], *, label: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in items:
        name, separator, value = item.partition("=")
        if not separator or not name.strip():
            raise CliConfigurationError(f"{label} must use NAME=VALUE: {item}")
        name = name.strip()
        if name in result and result[name] != value:
            raise CliConfigurationError(f"Conflicting {label} value for {name}")
        result[name] = value
    return result


def parse_inputs(items: list[str]) -> dict[str, Any]:
    return {name: _typed(value) for name, value in _assign(items, label="input").items()}


def parse_input_env(items: list[str]) -> tuple[dict[str, str], list[str]]:
    bindings = _assign(items, label="input-env")
    missing = sorted({env_name for env_name in bindings.values() if env_name not in os.environ})
    if missing:
        raise CliConfigurationError(
            "Required environment variables are missing: " + ", ".join(missing)
        )
    inputs = {name: os.environ[env_name] for name, env_name in bindings.items()}
    return inputs, list(dict.fromkeys(inputs.values()))


def load_datasets(path: Path, *, max_runs: int) -> list[dict[str, Any]]:
    if max_runs < 1:
        raise CliConfigurationError("--max-runs must be at least 1")
    if not path.is_file():
        raise CliConfigurationError(f"Dataset not found: {path}")
    suffix = path.suffix.lower()
    try:
        if suffix == ".csv":
            with path.open(encoding="utf-8-sig", newline="") as handle:
                rows = [
                    {name: _typed(value) for name, value in row.items()}
                    for row in csv.DictReader(handle)
                ]
        elif suffix == ".json":
            value = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
                raise CliConfigurationError("JSON dataset must be an array of objects")
            rows = value
        else:
            raise CliConfigurationError("Dataset must be CSV or JSON")
    except (OSError, UnicodeError, csv.Error, json.JSONDecodeError) as exc:
        raise CliConfigurationError(f"Unable to read dataset: {exc}") from exc
    if not rows:
        raise CliConfigurationError("Dataset is empty")
    return rows[:max_runs]


def write_json_result(path: Path, result: dict[str, Any], *, force: bool) -> None:
    if path.exists() and not force:
        raise CliConfigurationError(f"Output already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def validate_report_targets(
    *,
    output: Path,
    junit: Path | None,
    allure_results: Path | None,
    force: bool,
) -> None:
    """Reject unsafe report destinations before the first network request."""
    file_targets = [path for path in (output, junit) if path is not None]
    resolved_files = [path.resolve() for path in file_targets]
    if len(set(resolved_files)) != len(resolved_files):
        raise CliConfigurationError("JSON and JUnit report targets must be distinct")
    for path in file_targets:
        if path.exists() and path.is_dir():
            raise CliConfigurationError(f"Report file target is a directory: {path}")
    if allure_results:
        resolved_allure = allure_results.resolve()
        if allure_results.exists() and not allure_results.is_dir():
            raise CliConfigurationError(
                f"Allure report target is not a directory: {allure_results}"
            )
        if any(
            resolved_allure == file_path or resolved_allure in file_path.parents
            for file_path in resolved_files
        ):
            raise CliConfigurationError(
                "JSON/JUnit reports must not be written inside the Allure directory"
            )
    existing = [
        path for path in file_targets if path.exists() and not force
    ]
    if (
        allure_results
        and allure_results.exists()
        and any(allure_results.iterdir())
    ):
        existing.append(allure_results)
    if existing:
        raise CliConfigurationError(
            "Report target already exists: " + ", ".join(str(path) for path in existing)
        )
    try:
        for path in file_targets:
            path.parent.mkdir(parents=True, exist_ok=True)
        if allure_results:
            allure_results.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise CliConfigurationError(f"Unable to prepare report target: {exc}") from exc


def validate_protected_targets(
    *,
    reports: list[Path],
    protected: list[Path],
) -> None:
    protected_paths = {path.resolve() for path in protected}
    collisions = [
        path
        for path in reports
        if path.resolve() in protected_paths
    ]
    if collisions:
        raise CliConfigurationError(
            "Report targets must not overwrite workflow/schema inputs: "
            + ", ".join(str(path) for path in collisions)
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workflow", type=Path, help="Local Arazzo YAML/JSON document")
    parser.add_argument("--url", required=True, help="Credential-free target base URL")
    parser.add_argument("--schema", type=Path, help="Override local OpenAPI source path")
    parser.add_argument("--workflow", dest="workflow_ids", action="append", default=[])
    parser.add_argument("--tag", action="append", default=[])
    parser.add_argument("--input", action="append", default=[], metavar="NAME=VALUE")
    parser.add_argument(
        "--input-env",
        action="append",
        default=[],
        metavar="NAME=ENV_VAR",
        help="Read a secret workflow input from an environment variable",
    )
    parser.add_argument("--data", type=Path, help="CSV/JSON input rows")
    parser.add_argument("--max-runs", type=int, default=100)
    parser.add_argument("--output", type=Path, default=Path("workflow-result.json"))
    parser.add_argument("--junit", type=Path)
    parser.add_argument("--allure-results", type=Path)
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--allow-mutating-target",
        action="store_true",
        help="Confirm that the selected target is isolated and may be mutated",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        direct_inputs = parse_inputs(args.input)
        secret_inputs, secrets = parse_input_env(args.input_env)
        overlap = set(direct_inputs) & set(secret_inputs)
        if overlap:
            raise CliConfigurationError(
                "Inputs cannot be provided by both --input and --input-env: "
                + ", ".join(sorted(overlap))
            )
        datasets = load_datasets(args.data, max_runs=args.max_runs) if args.data else None
        explicit_protected = [args.workflow, *([args.schema] if args.schema else [])]
        report_files = [args.output, *([args.junit] if args.junit else [])]
        validate_protected_targets(
            reports=report_files,
            protected=explicit_protected,
        )
        validate_report_targets(
            output=args.output,
            junit=args.junit,
            allure_results=args.allure_results,
            force=args.force,
        )
        runner = WorkflowRunner(
            args.workflow,
            base_url=args.url,
            schema_path=args.schema,
        )
        validate_protected_targets(
            reports=report_files,
            protected=[args.workflow, runner.schema_path],
        )
        result = runner.run(
            workflow_ids=args.workflow_ids,
            tags=args.tag,
            inputs={**direct_inputs, **secret_inputs},
            datasets=datasets,
            secret_values=secrets,
            allow_mutating_target=args.allow_mutating_target,
        )
        write_json_result(args.output, result, force=args.force)
        if args.junit:
            write_junit(result, args.junit, force=args.force)
        if args.allure_results:
            write_allure_results(result, args.allure_results, force=args.force)
    except (CliConfigurationError, WorkflowConfigurationError, ReportWriteError) as exc:
        print(f"configuration: {exc}", file=sys.stderr)
        return 2
    except WorkflowTransportError as exc:
        print(f"transport: {exc}", file=sys.stderr)
        return 2
    except WorkflowError as exc:
        print(f"execution: {exc}", file=sys.stderr)
        return 2
    print(
        f"{result['status']}: {result['summary']['passed']}/"
        f"{result['summary']['total']} workflow runs passed -> {args.output}"
    )
    return 0 if result["status"] == "passed" else 1 if result["status"] == "failed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
