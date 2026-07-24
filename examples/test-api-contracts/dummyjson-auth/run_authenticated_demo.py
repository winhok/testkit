#!/usr/bin/env python3
"""Login to DummyJSON, then run Schemathesis against the authenticated /auth/me API."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path


BASE_URL = "https://dummyjson.com"
EXAMPLE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = EXAMPLE_ROOT.parents[2]
RUNNER = REPO_ROOT / "skills" / "test-api-contracts" / "scripts" / "run_api.py"
SCHEMA = EXAMPLE_ROOT / "openapi.yaml"


class DemoTransportError(RuntimeError):
    """Raised when the external practice API cannot be reached reliably."""


def _json_request(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 20,
) -> tuple[int, dict[str, object]]:
    body = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={
            "Accept": "application/json",
            "User-Agent": "testkit-test-api-contracts-demo/1.0",
            **({"Content-Type": "application/json"} if body else {}),
            **(headers or {}),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        parsed = json.loads(raw) if raw else {}
        return exc.code, parsed
    except (TimeoutError, urllib.error.URLError) as exc:
        raise DemoTransportError("DummyJSON transport request failed") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--username-env",
        default="DUMMYJSON_USERNAME",
        help="Environment variable containing the public demo username",
    )
    parser.add_argument(
        "--password-env",
        default="DUMMYJSON_PASSWORD",
        help="Environment variable containing the public demo password",
    )
    parser.add_argument(
        "--output",
        default="reports/dummyjson-auth-run.json",
        help="Normalized Schemathesis result path",
    )
    parser.add_argument("--timeout", type=float, default=20)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    username = os.environ.get(args.username_env)
    password = os.environ.get(args.password_env)
    if not username or not password:
        print(
            f"ERROR: Set {args.username_env} and {args.password_env} before running",
            file=sys.stderr,
        )
        return 2

    unauthenticated_status, _ = _json_request(
        f"{BASE_URL}/auth/me",
        timeout=args.timeout,
    )
    if unauthenticated_status != 401:
        print(
            f"ERROR: Expected unauthenticated /auth/me to return 401, got "
            f"{unauthenticated_status}",
            file=sys.stderr,
        )
        return 2
    print(
        "Precondition verified: /auth/me rejects a missing token with 401",
        flush=True,
    )

    login_status, login = _json_request(
        f"{BASE_URL}/auth/login",
        method="POST",
        payload={"username": username, "password": password, "expiresInMins": 15},
        timeout=args.timeout,
    )
    token = login.get("accessToken")
    if login_status != 200 or not isinstance(token, str) or not token:
        print(f"ERROR: DummyJSON login failed with status {login_status}", file=sys.stderr)
        return 2
    print(
        f"Login succeeded for public demo user: {login.get('username', username)}",
        flush=True,
    )

    authenticated_status, authenticated_user = _json_request(
        f"{BASE_URL}/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        timeout=args.timeout,
    )
    if authenticated_status != 200 or authenticated_user.get("username") != username:
        print(
            f"ERROR: Authenticated /auth/me verification failed with status "
            f"{authenticated_status}",
            file=sys.stderr,
        )
        return 2
    print("Authenticated precondition verified: /auth/me returned the login user", flush=True)

    runner_env = {
        **os.environ,
        "DUMMYJSON_AUTHORIZATION": f"Bearer {token}",
        "PATH": f"{Path(sys.executable).parent}{os.pathsep}{os.environ.get('PATH', '')}",
    }
    command = [
        sys.executable,
        str(RUNNER),
        str(SCHEMA),
        "--url",
        BASE_URL,
        "--mode",
        "smoke",
        "--header-env",
        "Authorization=DUMMYJSON_AUTHORIZATION",
        "--output",
        args.output,
    ]
    if args.force:
        command.append("--force")
    return subprocess.run(command, env=runner_env).returncode


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except DemoTransportError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
