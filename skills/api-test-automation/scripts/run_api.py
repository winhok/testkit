#!/usr/bin/env python3
"""Run an imported API description through Schemathesis."""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from execution_provenance import ExecutionProvenance


PHASES = {
    "smoke": "examples,coverage",
    "full": "examples,coverage,fuzzing,stateful",
    "stateful": "stateful",
}
MANAGED_RUNNER_OPTIONS = {
    "--auth",
    "--header",
    "--include-method",
    "--include-method-regex",
    "--output-sanitize",
    "--phases",
    "--proxy",
    "--report-allure-path",
    "--url",
    "-a",
    "-H",
}


def _runner_executable() -> str | None:
    for name in ("schemathesis", "st"):
        resolved = shutil.which(name)
        if resolved:
            return resolved
    executable_dirs = [
        Path(sys.executable).parent,
        Path(sys.executable).resolve().parent,
    ]
    for executable_dir in dict.fromkeys(executable_dirs):
        for name in ("schemathesis", "st"):
            candidate = executable_dir / name
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate.resolve())
    return None


def _redact(text: str, secret_values: list[str]) -> str:
    redacted = text
    for value in sorted((v for v in secret_values if v), key=len, reverse=True):
        if redacted == value:
            return "[REDACTED]"
        redacted = re.sub(
            rf"(?<![A-Za-z0-9]){re.escape(value)}(?![A-Za-z0-9])",
            "[REDACTED]",
            redacted,
        )
    return redacted


def _contains_secret(text: str, secret_values: list[str]) -> bool:
    return any(
        text == secret
        or re.search(
            rf"(?<![A-Za-z0-9]){re.escape(secret)}(?![A-Za-z0-9])",
            text,
        )
        is not None
        for secret in secret_values
        if secret
    )


def _managed_passthrough_option(arguments: list[str]) -> str | None:
    for argument in arguments:
        option = argument.split("=", 1)[0]
        if option == "--report" or option.startswith("--report-"):
            return option
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
        "--secret-env",
        action="append",
        default=[],
        metavar="ENV_VAR",
        help=argparse.SUPPRESS,
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
    parser.add_argument('--runner-timeout', type=float, default=300, help='Maximum runner duration in seconds')
    parser.add_argument('--runner-output-limit', type=int, default=65536, help='Maximum retained characters per runner output stream')
    args, runner_args = parser.parse_known_args(argv)
    if not math.isfinite(args.runner_timeout) or args.runner_timeout <= 0 or args.runner_output_limit <= 0:
        print('ERROR: runner timeout and output limit must be finite and positive', file=sys.stderr)
        return 2

    executable = _runner_executable()
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
    if (
        parsed_url.username
        or parsed_url.password
        or parsed_url.query
        or parsed_url.fragment
    ):
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
    if output.resolve() == schema or (output.exists() and output.samefile(schema)):
        print("ERROR: Result output must not overwrite the input schema", file=sys.stderr)
        return 2
    if output.exists() and output.is_dir():
        print(f"ERROR: Result output is a directory: {output}", file=sys.stderr)
        return 2
    if output.exists() and not args.force:
        print(
            f"ERROR: Result already exists; use --force to replace it: {output}",
            file=sys.stderr,
        )
        return 2
    if args.allure_results:
        allure_path = Path(args.allure_results)
        if allure_path.exists() and not allure_path.is_dir():
            print(
                f"ERROR: Allure result target is not a directory: {allure_path}",
                file=sys.stderr,
            )
            return 2
        if output.resolve().is_relative_to(allure_path.resolve()):
            print(
                "ERROR: Result JSON and Allure directory targets must be distinct",
                file=sys.stderr,
            )
            return 2
        if allure_path.exists() and any(allure_path.iterdir()):
            print(
                "ERROR: Allure result directory must be empty; choose a fresh "
                f"directory: {allure_path}",
                file=sys.stderr,
            )
            return 2
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        if args.allure_results:
            Path(args.allure_results).mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"ERROR: Unable to prepare report target: {exc}", file=sys.stderr)
        return 2

    command = [
        executable,
        "run",
        str(schema),
        "--url",
        args.url,
        f"--phases={PHASES[args.mode]}",
    ]
    if args.mode == "smoke" and not args.allow_mutating_target:
        for method in ("GET", "HEAD", "OPTIONS", "TRACE"):
            command.extend(["--include-method", method])
    secret_values: list[str] = []
    for env_name in args.secret_env:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", env_name):
            print(f"ERROR: Invalid --secret-env value: {env_name}", file=sys.stderr)
            return 2
        value = os.environ.get(env_name)
        if not value:
            print(
                f"ERROR: Required environment variable is missing: {env_name}",
                file=sys.stderr,
            )
            return 2
        secret_values.append(value)
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
        if value not in secret_values:
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

    provenance = ExecutionProvenance(schema, target_url=args.url)
    started_at = provenance.started_at
    # Spool to temporary files so runner output cannot grow Python memory without bound.
    # Keep extra bytes before redaction to avoid retaining a truncated secret prefix.
    byte_limit = args.runner_output_limit * 4 + max((len(v.encode('utf-8')) for v in secret_values), default=0)
    with tempfile.TemporaryFile() as stdout_file, tempfile.TemporaryFile() as stderr_file:
        try:
            completed = subprocess.run(command, text=True, stdout=stdout_file, stderr=stderr_file, timeout=args.runner_timeout)
        except subprocess.TimeoutExpired:
            completed = subprocess.CompletedProcess(command, 124, None, None)
        except OSError as exc:
            print(f'ERROR: runner could not start ({type(exc).__name__})', file=sys.stderr)
            return 2
        stdout_file.seek(0)
        stderr_file.seek(0)
        raw_stdout = completed.stdout if isinstance(completed.stdout, str) else stdout_file.read(byte_limit + 1).decode('utf-8', errors='replace')
        raw_stderr = completed.stderr if isinstance(completed.stderr, str) else stderr_file.read(byte_limit + 1).decode('utf-8', errors='replace')
    execution = provenance.finish()
    safe_command = [
        "[REDACTED]"
        if _contains_secret(item, secret_values)
        else item
        for item in command
    ]
    stdout = _redact(raw_stdout, secret_values)
    stderr = _redact(raw_stderr, secret_values)
    stdout_truncated = len(stdout) > args.runner_output_limit
    stderr_truncated = len(stderr) > args.runner_output_limit
    stdout = stdout[:args.runner_output_limit] + ('\n[TRUNCATED]' if stdout_truncated else '')
    stderr = stderr[:args.runner_output_limit] + ('\n[TRUNCATED]' if stderr_truncated else '')
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
    payload["execution"] = execution
    payload['stdout_truncated'] = stdout_truncated
    payload['stderr_truncated'] = stderr_truncated
    if completed.returncode == 124:
        payload['error_type'] = 'timeout'
    payload["finished_at"] = execution["finished_at"]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if stdout:
        print(stdout, end="" if stdout.endswith("\n") else "\n")
    if stderr:
        print(stderr, file=sys.stderr, end="" if stderr.endswith("\n") else "\n")
    print(f"Run result: {output}")
    return 0 if completed.returncode == 0 else 1 if completed.returncode == 1 else 2


if __name__ == "__main__":
    raise SystemExit(main())
