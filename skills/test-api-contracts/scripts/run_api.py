#!/usr/bin/env python3
"""Run an imported API description through Schemathesis."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path


PHASES = {
    "smoke": "examples,coverage",
    "full": "examples,coverage,fuzzing,stateful",
    "stateful": "stateful",
}
MANAGED_RUNNER_OPTIONS = {
    "--auth",
    "--header",
    "--output-sanitize",
    "--phases",
    "--proxy",
    "--report-allure-path",
    "--url",
    "-a",
    "-H",
}


def _redact(text: str, secret_values: list[str]) -> str:
    redacted = text
    for value in sorted((v for v in secret_values if v), key=len, reverse=True):
        redacted = redacted.replace(value, "[REDACTED]")
    return redacted


def _managed_passthrough_option(arguments: list[str]) -> str | None:
    for argument in arguments:
        option = argument.split("=", 1)[0]
        if option in MANAGED_RUNNER_OPTIONS:
            return option
        if argument.startswith("-H") and argument != "-H":
            return "-H"
        if argument.startswith("-a") and argument != "-a":
            return "-a"
    return None


def _result_payload(
    *,
    status: str,
    returncode: int,
    mode: str,
    schema: Path,
    command: list[str],
    stdout: str,
    stderr: str,
    started_at: str,
) -> dict:
    return {
        "schema_version": 1,
        "runner": "schemathesis",
        "status": status,
        "returncode": returncode,
        "mode": mode,
        "schema": str(schema),
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "command": command,
        "stdout": stdout,
        "stderr": stderr,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("schema", help="Imported OpenAPI/Swagger file")
    parser.add_argument("--url", required=True, help="Base URL of the API under test")
    parser.add_argument("--mode", choices=sorted(PHASES), default="smoke")
    parser.add_argument(
        "--header-env",
        action="append",
        default=[],
        metavar="HEADER=ENV_VAR",
        help="Read a request header value from an environment variable",
    )
    parser.add_argument(
        "--output", "-o", default="reports/run-result.json", help="Normalized result JSON"
    )
    parser.add_argument(
        "--allure-results",
        help="Optional directory for Schemathesis Allure results",
    )
    parser.add_argument(
        "--allow-mutating-target",
        action="store_true",
        help="Confirm that full/stateful execution targets an isolated non-production environment",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite an existing result file")
    args, runner_args = parser.parse_known_args(argv)

    executable = shutil.which("schemathesis") or shutil.which("st")
    if not executable:
        print(
            "ERROR: Schemathesis is not installed. Install the project dependencies first.",
            file=sys.stderr,
        )
        return 2
    schema = Path(args.schema).resolve()
    if not schema.is_file():
        print(f"ERROR: Schema file not found: {schema}", file=sys.stderr)
        return 2
    parsed_url = urllib.parse.urlsplit(args.url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.hostname:
        print("ERROR: --url must be an absolute HTTP(S) URL", file=sys.stderr)
        return 2
    if parsed_url.username or parsed_url.password:
        print("ERROR: Put credentials in environment-backed headers, not --url", file=sys.stderr)
        return 2
    if args.mode in {"full", "stateful"} and not args.allow_mutating_target:
        print(
            "ERROR: Full/stateful testing requires --allow-mutating-target after confirming "
            "an isolated non-production environment",
            file=sys.stderr,
        )
        return 2
    output = Path(args.output)
    if output.exists() and not args.force:
        print(
            f"ERROR: Result already exists; use --force to replace it: {output}",
            file=sys.stderr,
        )
        return 2

    command = [
        executable,
        "run",
        str(schema),
        "--url",
        args.url,
        f"--phases={PHASES[args.mode]}",
    ]
    secret_values: list[str] = []
    for mapping in args.header_env:
        if "=" not in mapping:
            print(f"ERROR: Invalid --header-env value: {mapping}", file=sys.stderr)
            return 2
        header, env_name = mapping.split("=", 1)
        if (
            not header
            or not env_name
            or not re.fullmatch(r"[A-Za-z0-9!#$%&'*+.^_`|~-]+", header)
        ):
            print(f"ERROR: Invalid --header-env value: {mapping}", file=sys.stderr)
            return 2
        value = os.environ.get(env_name)
        if not value:
            print(
                f"ERROR: Required environment variable is missing: {env_name}",
                file=sys.stderr,
            )
            return 2
        command.extend(["--header", f"{header}:{value}"])
        secret_values.append(value)
    if args.allure_results:
        command.extend(["--report-allure-path", args.allure_results])
    passthrough = runner_args[1:] if runner_args[:1] == ["--"] else runner_args
    managed_option = _managed_passthrough_option(passthrough)
    if managed_option:
        print(
            f"ERROR: {managed_option} is managed by this wrapper and cannot be passed through",
            file=sys.stderr,
        )
        return 2
    command.extend(passthrough)

    started_at = datetime.now(timezone.utc).isoformat()
    completed = subprocess.run(command, text=True, capture_output=True)
    safe_command = [
        "[REDACTED]"
        if any(secret and secret in item for secret in secret_values)
        else item
        for item in command
    ]
    stdout = _redact(completed.stdout, secret_values)
    stderr = _redact(completed.stderr, secret_values)
    status = {0: "passed", 1: "failed"}.get(completed.returncode, "error")
    payload = _result_payload(
        status=status,
        returncode=completed.returncode,
        mode=args.mode,
        schema=schema,
        command=safe_command,
        stdout=stdout,
        stderr=stderr,
        started_at=started_at,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if stdout:
        print(stdout, end="" if stdout.endswith("\n") else "\n")
    if stderr:
        print(stderr, file=sys.stderr, end="" if stderr.endswith("\n") else "\n")
    print(f"Run result: {output}")
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
