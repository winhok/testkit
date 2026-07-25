#!/usr/bin/env python3
"""Run a deterministic preflight, then seed Schemathesis from workflow outputs."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import run_api
from run_workflows import (
    CliConfigurationError,
    parse_input_env,
    parse_inputs,
    validate_protected_targets,
    validate_report_targets,
    write_json_result,
)
from workflow_engine import WorkflowConfigurationError, WorkflowError, WorkflowRunner


_HEADER = re.compile(r"[A-Za-z0-9!#$%&'*+.^_`|~-]+")


def _mapping(items: list[str], *, label: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in items:
        name, separator, value = item.partition("=")
        if not separator or not name or not value:
            raise CliConfigurationError(f"{label} must use NAME=VALUE: {item}")
        if name in result:
            raise CliConfigurationError(f"Duplicate {label} for {name}")
        result[name] = value
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workflow", type=Path)
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--preflight-workflow", required=True)
    parser.add_argument("--input", action="append", default=[])
    parser.add_argument("--input-env", action="append", default=[])
    parser.add_argument(
        "--schema-header-from-output",
        action="append",
        default=[],
        metavar="HEADER=OUTPUT",
        help="Inject one captured workflow output into Schemathesis",
    )
    parser.add_argument(
        "--header-template",
        action="append",
        default=[],
        metavar="HEADER=TEMPLATE",
        help="Format a captured value, for example 'Authorization=Bearer {value}'",
    )
    parser.add_argument("--mode", choices=sorted(run_api.PHASES), default="smoke")
    parser.add_argument("--workflow-output", type=Path, default=Path("workflow-result.json"))
    parser.add_argument("--schema-output", type=Path, default=Path("schema-result.json"))
    parser.add_argument("--output", type=Path, default=Path("automation-result.json"))
    parser.add_argument("--allure-results", type=Path)
    parser.add_argument(
        "--allow-preflight-mutating-target",
        action="store_true",
        help="Confirm that deterministic workflow writes are safe for this target",
    )
    parser.add_argument(
        "--allow-schema-mutating-target",
        action="store_true",
        help="Confirm that generated unsafe-method tests may mutate this target",
    )
    parser.add_argument(
        "--allow-mutating-target",
        action="store_true",
        help="Confirm both preflight and generated writes (convenience alias)",
    )
    parser.add_argument("--force", action="store_true")
    return parser


def _validate_before_network(args: argparse.Namespace) -> None:
    if not args.workflow.is_file():
        raise CliConfigurationError(f"Workflow not found: {args.workflow}")
    if not args.schema.is_file():
        raise CliConfigurationError(f"Schema not found: {args.schema}")
    if not run_api._runner_executable():
        raise CliConfigurationError("Schemathesis is not installed")
    if args.mode in {"full", "stateful"} and not (
        args.allow_mutating_target or args.allow_schema_mutating_target
    ):
        raise CliConfigurationError(
            "Full/stateful schema testing requires "
            "--allow-schema-mutating-target on an isolated target"
        )
    validate_protected_targets(
        reports=[args.workflow_output, args.schema_output, args.output],
        protected=[args.workflow, args.schema],
    )
    validate_report_targets(
        output=args.workflow_output,
        junit=args.schema_output,
        allure_results=args.allure_results,
        force=args.force,
    )
    resolved_combined = args.output.resolve()
    if resolved_combined in {
        args.workflow_output.resolve(),
        args.schema_output.resolve(),
    }:
        raise CliConfigurationError(
            "Combined, workflow, and schema report targets must be distinct"
        )
    if args.output.exists():
        if args.output.is_dir():
            raise CliConfigurationError(
                f"Combined report file target is a directory: {args.output}"
            )
        if not args.force:
            raise CliConfigurationError(
                f"Report target already exists: {args.output}"
            )
    if args.allure_results and (
        args.allure_results.resolve() == resolved_combined
        or args.allure_results.resolve() in resolved_combined.parents
    ):
        raise CliConfigurationError(
            "Combined report must not be written inside the Allure directory"
        )
    try:
        args.output.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise CliConfigurationError(f"Unable to prepare report target: {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    temporary_environment: dict[str, str | None] = {}
    try:
        _validate_before_network(args)
        inputs = parse_inputs(args.input)
        secret_inputs, secret_values = parse_input_env(args.input_env)
        overlap = set(inputs) & set(secret_inputs)
        if overlap:
            raise CliConfigurationError(
                "Inputs cannot be provided twice: " + ", ".join(sorted(overlap))
            )
        header_outputs = _mapping(
            args.schema_header_from_output,
            label="schema-header-from-output",
        )
        templates = _mapping(args.header_template, label="header-template")
        if set(templates) - set(header_outputs):
            raise CliConfigurationError(
                "Header templates require a matching output mapping: "
                + ", ".join(sorted(set(templates) - set(header_outputs)))
            )
        if not all(_HEADER.fullmatch(header) for header in header_outputs):
            raise CliConfigurationError("Invalid HTTP header name in output mapping")
        runner = WorkflowRunner(
            args.workflow,
            base_url=args.url,
            schema_path=args.schema,
        )
        missing_outputs = sorted(
            set(header_outputs)
            and set(header_outputs.values())
            - runner.declared_output_names(args.preflight_workflow)
        )
        if missing_outputs:
            raise CliConfigurationError(
                "Workflow outputs are not declared: " + ", ".join(missing_outputs)
            )
        captured: dict[str, Any] = {}
        workflow_result = runner.run(
            workflow_ids=[args.preflight_workflow],
            inputs={**inputs, **secret_inputs},
            secret_values=secret_values,
            allow_mutating_target=(
                args.allow_mutating_target
                or args.allow_preflight_mutating_target
            ),
            output_sink=captured,
        )
        write_json_result(
            args.workflow_output,
            workflow_result,
            force=args.force,
        )
        if workflow_result["status"] != "passed":
            workflow_status = workflow_result["status"]
            combined = {
                "schema_version": 1,
                "status": workflow_status,
                "workflow_status": workflow_status,
                "schema_status": "not-run",
                "workflow_result": str(args.workflow_output),
                "schema_result": None,
            }
            write_json_result(args.output, combined, force=args.force)
            return 1 if workflow_status == "failed" else 2

        schema_args = [
            str(args.schema),
            "--url",
            args.url,
            "--mode",
            args.mode,
            "--output",
            str(args.schema_output),
        ]
        if args.force:
            schema_args.append("--force")
        if args.allow_mutating_target or args.allow_schema_mutating_target:
            schema_args.append("--allow-mutating-target")
        if args.allure_results:
            schema_args.extend(["--allure-results", str(args.allure_results)])
        for index, (header, output_name) in enumerate(header_outputs.items()):
            if output_name not in captured:
                raise CliConfigurationError(
                    f"Workflow output is unavailable: {output_name}"
                )
            template = templates.get(header, "{value}")
            try:
                value = template.format(value=captured[output_name])
            except (KeyError, ValueError) as exc:
                raise CliConfigurationError(
                    f"Invalid header template for {header}: {exc}"
                ) from exc
            env_name = f"TESTKIT_AUTOMATION_HEADER_{index}"
            temporary_environment[env_name] = os.environ.get(env_name)
            os.environ[env_name] = value
            schema_args.extend(["--header-env", f"{header}={env_name}"])
            raw_env_name = f"TESTKIT_AUTOMATION_SECRET_{index}"
            temporary_environment[raw_env_name] = os.environ.get(raw_env_name)
            os.environ[raw_env_name] = str(captured[output_name])
            schema_args.extend(["--secret-env", raw_env_name])
        schema_code = run_api.main(schema_args)
        schema_status = (
            json.loads(args.schema_output.read_text(encoding="utf-8")).get("status")
            if args.schema_output.is_file()
            else "error"
        )
        combined = {
            "schema_version": 1,
            "status": (
                "passed" if schema_code == 0 else "failed" if schema_code == 1 else "error"
            ),
            "workflow_status": workflow_result["status"],
            "schema_status": schema_status,
            "workflow_result": str(args.workflow_output),
            "schema_result": str(args.schema_output),
        }
        write_json_result(args.output, combined, force=args.force)
        return 0 if schema_code == 0 else 1 if schema_code == 1 else 2
    except (CliConfigurationError, WorkflowConfigurationError) as exc:
        print(f"configuration: {exc}", file=sys.stderr)
        return 2
    except WorkflowError as exc:
        print(f"execution: {exc}", file=sys.stderr)
        return 2
    finally:
        for name, previous in temporary_environment.items():
            if previous is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = previous


if __name__ == "__main__":
    raise SystemExit(main())
