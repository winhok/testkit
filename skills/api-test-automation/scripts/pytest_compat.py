#!/usr/bin/env python3
"""Collect and run explicitly selected pytest assets through a safe subprocess boundary."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence
from xml.etree import ElementTree


MANIFEST_SCHEMA_VERSION = 1
RESULT_SCHEMA_VERSION = 1
PLUGIN_NAME = "pytest_manifest_plugin"
COLLECTION_OUTPUT_ENV = "TESTKIT_PYTEST_COLLECTION_OUTPUT"
EXPLICIT_PLUGINS_ENV = "TESTKIT_PYTEST_EXPLICIT_PLUGINS"
CONFIG_NAMES = ("pytest.ini", "pyproject.toml", "tox.ini", "setup.cfg")
PYTEST_VERSION = re.compile(r"pytest\s+([0-9][^\s]*)")


class PytestCompatibilityError(ValueError):
    """A configuration, source, or normalization error."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as temporary:
        temporary.write(text)
        temporary_path = Path(temporary.name)
    temporary_path.replace(path)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    _atomic_write_text(
        path,
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    )


def _prepare_output(path: Path, *, force: bool) -> Path:
    resolved = path.expanduser().resolve()
    if resolved.exists() and not force:
        raise PytestCompatibilityError(
            f"Output already exists; choose a fresh path or use --force: {resolved}"
        )
    if resolved.exists() and not resolved.is_file():
        raise PytestCompatibilityError(f"Output is not a regular file: {resolved}")
    return resolved


def _reject_path_overlap(outputs: Sequence[Path], protected: Sequence[Path]) -> None:
    if len(set(outputs)) != len(outputs):
        raise PytestCompatibilityError("Output paths must be distinct")
    protected_set = {path.expanduser().resolve() for path in protected}
    overlap = [path for path in outputs if path in protected_set]
    if overlap:
        raise PytestCompatibilityError(
            "Output must not overwrite an input or source file: "
            + ", ".join(str(path) for path in overlap)
        )


def _project_root(path: str) -> Path:
    root = Path(path).expanduser().resolve()
    if not root.is_dir():
        raise PytestCompatibilityError(f"Project root is not a directory: {root}")
    return root


def _relative_path(path: Path, root: Path, *, label: str) -> str:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(root)
    except ValueError as exc:
        raise PytestCompatibilityError(f"{label} escapes the project root: {path}") from exc
    return relative.as_posix() or "."


def _normalize_selector(selector: str, root: Path) -> str:
    if not selector or selector.startswith("-"):
        raise PytestCompatibilityError(f"Invalid pytest selector: {selector!r}")
    path_part, separator, suffix = selector.partition("::")
    if not path_part:
        raise PytestCompatibilityError(f"Selector requires a path: {selector!r}")
    candidate = Path(path_part)
    if not candidate.is_absolute():
        candidate = root / candidate
    relative = _relative_path(candidate, root, label="Selector")
    if not candidate.exists():
        raise PytestCompatibilityError(f"Selector path does not exist: {relative}")
    return relative + (separator + suffix if separator else "")


def _secret_values(names: Sequence[str]) -> list[str]:
    values: list[str] = []
    for name in names:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise PytestCompatibilityError(f"Invalid --secret-env value: {name}")
        value = os.environ.get(name)
        if not value:
            raise PytestCompatibilityError(
                f"Required environment variable is missing: {name}"
            )
        if value not in values:
            values.append(value)
    return sorted(values, key=len, reverse=True)


def _redact(value: str, secrets: Sequence[str]) -> str:
    result = value
    for secret in secrets:
        result = result.replace(secret, "[REDACTED]")
        if len(secret) >= 8:
            result = re.sub(
                re.escape(secret[:8]) + r"[^\s]*",
                "[REDACTED]",
                result,
            )
    return result


def _bounded(value: str, limit: int) -> tuple[str, bool]:
    if len(value) <= limit:
        return value, False
    return value[:limit] + "\n[TRUNCATED]", True


def _subprocess_env(
    collection_output: Path | None = None,
    explicit_plugins: Sequence[str] = (),
) -> dict[str, str]:
    scripts_dir = str(Path(__file__).resolve().parent)
    existing_pythonpath = os.environ.get("PYTHONPATH")
    pythonpath = (
        scripts_dir + os.pathsep + existing_pythonpath
        if existing_pythonpath
        else scripts_dir
    )
    env = dict(os.environ)
    env.pop("PYTEST_ADDOPTS", None)
    env.pop("PYTEST_PLUGINS", None)
    env.update(
        {
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "PYTHONPATH": pythonpath,
        }
    )
    if collection_output is not None:
        env[COLLECTION_OUTPUT_ENV] = str(collection_output)
        env[EXPLICIT_PLUGINS_ENV] = json.dumps(list(explicit_plugins))
    return env


def _pytest_command(python: str, plugins: Sequence[str]) -> list[str]:
    command = [python, "-m", "pytest"]
    for plugin in plugins:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*", plugin):
            raise PytestCompatibilityError(f"Invalid pytest plugin name: {plugin}")
        command.extend(["-p", plugin])
    return command


def _source_files(
    root: Path,
    raw_items: Sequence[dict[str, Any]],
    config_path: str | None,
) -> tuple[list[dict[str, str]], dict[str, str]]:
    source_paths: set[Path] = set()
    node_sources: dict[str, str] = {}
    for item in raw_items:
        nodeid = item.get("nodeid")
        raw_path = item.get("path")
        if not isinstance(nodeid, str) or not nodeid:
            raise PytestCompatibilityError("Collected item lacks a nodeid")
        if not isinstance(raw_path, str) or not raw_path:
            raise PytestCompatibilityError(f"Collected item {nodeid} lacks a source path")
        source_path = Path(raw_path).resolve()
        relative = _relative_path(source_path, root, label=f"Source for {nodeid}")
        if not source_path.is_file():
            raise PytestCompatibilityError(f"Collected source is not a file: {relative}")
        node_sources[nodeid] = relative
        source_paths.add(source_path)

        parent = source_path.parent
        while True:
            conftest = parent / "conftest.py"
            if conftest.is_file():
                source_paths.add(conftest.resolve())
            if parent == root:
                break
            try:
                parent.relative_to(root)
            except ValueError:
                break
            parent = parent.parent

    if config_path:
        config = Path(config_path).resolve()
        _relative_path(config, root, label="Pytest config")
        if config.is_file():
            source_paths.add(config)
    else:
        for name in CONFIG_NAMES:
            candidate = root / name
            if candidate.is_file():
                source_paths.add(candidate.resolve())

    sources = [
        {"path": _relative_path(path, root, label="Source"), "sha256": _sha256(path)}
        for path in sorted(source_paths, key=lambda item: item.as_posix())
    ]
    return sources, node_sources


def _fingerprint(sources: Sequence[dict[str, str]]) -> str:
    digest = hashlib.sha256()
    for source in sources:
        digest.update(source["path"].encode("utf-8"))
        digest.update(b"\0")
        digest.update(source["sha256"].encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _load_manifest(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PytestCompatibilityError(f"Cannot read pytest manifest: {exc}") from exc
    if payload.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise PytestCompatibilityError("Unsupported pytest manifest schema_version")
    if payload.get("runner") != "pytest":
        raise PytestCompatibilityError("Manifest runner must be pytest")
    if payload.get("project_root") != ".":
        raise PytestCompatibilityError("Manifest project_root must be relative '.'")
    if payload.get("plugin_autoload") != "disabled":
        raise PytestCompatibilityError("Manifest must disable plugin autoload")
    if payload.get("ambient_pytest_env") != "ignored":
        raise PytestCompatibilityError("Manifest must ignore ambient pytest control variables")
    tests = payload.get("tests")
    sources = payload.get("sources")
    if not isinstance(tests, list) or not tests:
        raise PytestCompatibilityError("Manifest must contain collected tests")
    if not isinstance(sources, list) or not sources:
        raise PytestCompatibilityError("Manifest must contain source fingerprints")
    seen_sources: set[str] = set()
    for source_entry in sources:
        if not isinstance(source_entry, dict):
            raise PytestCompatibilityError("Manifest source entry must be an object")
        source_path = source_entry.get("path")
        source_digest = source_entry.get("sha256")
        if (
            not isinstance(source_path, str)
            or not source_path
            or not isinstance(source_digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", source_digest)
        ):
            raise PytestCompatibilityError("Manifest source entry is incomplete")
        if source_path in seen_sources:
            raise PytestCompatibilityError(
                f"Manifest contains duplicate source: {source_path}"
            )
        seen_sources.add(source_path)
    seen_nodeids: set[str] = set()
    for item in tests:
        if not isinstance(item, dict):
            raise PytestCompatibilityError("Manifest test entry must be an object")
        nodeid = item.get("nodeid")
        source = item.get("source")
        if not isinstance(nodeid, str) or not nodeid:
            raise PytestCompatibilityError("Manifest test entry lacks a nodeid")
        if not isinstance(source, str) or not source:
            raise PytestCompatibilityError(f"Manifest test {nodeid} lacks a source")
        if nodeid != source and not nodeid.startswith(source + "::"):
            raise PytestCompatibilityError(
                f"Manifest nodeid does not match its source: {nodeid}"
            )
        if nodeid in seen_nodeids:
            raise PytestCompatibilityError(f"Manifest contains duplicate nodeid: {nodeid}")
        seen_nodeids.add(nodeid)
    return payload


def _validate_manifest_sources(manifest: dict[str, Any], root: Path) -> None:
    current: list[dict[str, str]] = []
    for source in manifest["sources"]:
        if not isinstance(source, dict):
            raise PytestCompatibilityError("Manifest source entry must be an object")
        relative = source.get("path")
        expected = source.get("sha256")
        if not isinstance(relative, str) or not isinstance(expected, str):
            raise PytestCompatibilityError("Manifest source entry is incomplete")
        path = (root / relative).resolve()
        _relative_path(path, root, label="Manifest source")
        if not path.is_file():
            raise PytestCompatibilityError(f"Stale manifest: source is missing: {relative}")
        digest = _sha256(path)
        if digest != expected:
            raise PytestCompatibilityError(f"Stale manifest: source changed: {relative}")
        current.append({"path": relative, "sha256": digest})
    if _fingerprint(current) != manifest.get("source_fingerprint"):
        raise PytestCompatibilityError("Stale manifest: source fingerprint differs")

    expected_paths = {str(item["path"]) for item in manifest["sources"]}
    observed_paths = {str(item["source"]) for item in manifest["tests"]}
    for relative in list(observed_paths):
        parent = (root / relative).resolve().parent
        while True:
            conftest = parent / "conftest.py"
            if conftest.is_file():
                observed_paths.add(_relative_path(conftest, root, label="Conftest"))
            if parent == root:
                break
            parent = parent.parent
    config_path = manifest.get("config_path")
    if config_path:
        if not isinstance(config_path, str):
            raise PytestCompatibilityError("Manifest config_path is invalid")
        observed_paths.add(config_path)
    else:
        for name in CONFIG_NAMES:
            if (root / name).is_file():
                observed_paths.add(name)
    if observed_paths != expected_paths:
        raise PytestCompatibilityError(
            "Stale manifest: pytest source or configuration inventory changed"
        )


def _pytest_version(python: str, env: dict[str, str], timeout: float) -> str:
    try:
        completed = subprocess.run(
            [python, "-m", "pytest", "--version"],
            cwd=Path.cwd(),
            env=env,
            text=True,
            capture_output=True,
            timeout=min(timeout, 30),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PytestCompatibilityError(f"Cannot query pytest version: {exc}") from exc
    text = completed.stdout + "\n" + completed.stderr
    match = PYTEST_VERSION.search(text)
    if completed.returncode != 0 or match is None:
        raise PytestCompatibilityError("Selected Python cannot run pytest")
    return match.group(1)


def _plugin_metadata(
    python: str,
    names: Sequence[str],
    env: dict[str, str],
    timeout: float,
    cwd: Path,
) -> list[dict[str, str | None]]:
    if not names:
        return []
    snippet = (
        "import json,sys; "
        "from pytest_manifest_plugin import plugin_metadata; "
        "print(json.dumps(plugin_metadata(sys.argv[1:])))"
    )
    try:
        completed = subprocess.run(
            [python, "-c", snippet, *names],
            cwd=cwd,
            env=env,
            text=True,
            capture_output=True,
            timeout=min(timeout, 30),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PytestCompatibilityError(f"Cannot inspect pytest plugins: {exc}") from exc
    try:
        metadata = json.loads(completed.stdout.strip().splitlines()[-1])
    except json.JSONDecodeError as exc:
        raise PytestCompatibilityError("Cannot read pytest plugin metadata") from exc
    except IndexError as exc:
        raise PytestCompatibilityError("Cannot read pytest plugin metadata") from exc
    if completed.returncode != 0 or not isinstance(metadata, list):
        raise PytestCompatibilityError("Selected Python cannot load explicit pytest plugins")
    return metadata


def _sanitize_xml(root: ElementTree.Element, secrets: Sequence[str]) -> None:
    for element in root.iter():
        if element.text:
            element.text = _redact(element.text, secrets)
        if element.tail:
            element.tail = _redact(element.tail, secrets)
        for name, value in list(element.attrib.items()):
            element.attrib[name] = _redact(value, secrets)


def _testcase_result(testcase: ElementTree.Element) -> dict[str, Any]:
    outcome = "passed"
    detail = None
    for tag in ("failure", "error", "skipped"):
        child = testcase.find(tag)
        if child is not None:
            outcome = tag
            detail = {
                "message": child.attrib.get("message", ""),
                "text": child.text or "",
            }
            break
    try:
        duration = float(testcase.attrib.get("time", "0") or 0)
    except ValueError as exc:
        raise PytestCompatibilityError("JUnit testcase has invalid time") from exc
    if not math.isfinite(duration) or duration < 0:
        raise PytestCompatibilityError("JUnit testcase has invalid time")
    result: dict[str, Any] = {
        "node": "::".join(
            part
            for part in (
                testcase.attrib.get("classname", ""),
                testcase.attrib.get("name", ""),
            )
            if part
        ),
        "outcome": outcome,
        "duration_seconds": duration,
    }
    if detail is not None:
        result["detail"] = detail
    return result


def _normalize_junit(
    junit_path: Path,
    *,
    exit_code: int,
    secrets: Sequence[str],
) -> tuple[ElementTree.ElementTree, dict[str, Any]]:
    try:
        tree = ElementTree.parse(junit_path)
    except (OSError, ElementTree.ParseError) as exc:
        raise PytestCompatibilityError(f"Cannot parse JUnit XML: {exc}") from exc
    root = tree.getroot()
    if root.tag not in {"testsuite", "testsuites"}:
        raise PytestCompatibilityError(f"Unsupported JUnit root element: {root.tag}")
    _sanitize_xml(root, secrets)
    cases = [_testcase_result(item) for item in root.iter("testcase")]
    counts = {
        "total": len(cases),
        "passed": sum(item["outcome"] == "passed" for item in cases),
        "failed": sum(item["outcome"] == "failure" for item in cases),
        "errors": sum(item["outcome"] == "error" for item in cases),
        "skipped": sum(item["outcome"] == "skipped" for item in cases),
    }
    if exit_code == 0 and not cases:
        raise PytestCompatibilityError("Pytest selected zero tests")
    if exit_code == 0 and any(
        item["outcome"] in {"failure", "error"} for item in cases
    ):
        raise PytestCompatibilityError(
            "JUnit contains failures but pytest exit code reports success"
        )
    status = "passed" if exit_code == 0 else "failed" if exit_code == 1 else "error"
    return tree, {"status": status, "exit_code": exit_code, "summary": counts, "tests": cases}


def _normalized_result(
    normalized: dict[str, Any],
    *,
    manifest: str | None,
    nodeids: Sequence[str],
    pytest_version: str | None,
    stdout: str,
    stderr: str,
    output_limit: int,
) -> dict[str, Any]:
    safe_stdout, stdout_truncated = _bounded(stdout, output_limit)
    safe_stderr, stderr_truncated = _bounded(stderr, output_limit)
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "runner": "pytest",
        "status": normalized["status"],
        "exit_code": normalized["exit_code"],
        "error_type": (
            None
            if normalized["status"] == "passed"
            else "test" if normalized["status"] == "failed" else "configuration"
        ),
        "pytest_version": pytest_version,
        "manifest": manifest,
        "selected_nodeids": list(nodeids),
        "summary": normalized["summary"],
        "tests": normalized["tests"],
        "stdout": safe_stdout,
        "stderr": safe_stderr,
        "stdout_truncated": stdout_truncated,
        "stderr_truncated": stderr_truncated,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }


def collect(args: argparse.Namespace) -> int:
    root = _project_root(args.project_root)
    output = _prepare_output(Path(args.output), force=args.force)
    selectors = [_normalize_selector(item, root) for item in args.selector]
    secrets = _secret_values(args.secret_env)
    plugins = sorted(set(args.plugin))
    if PLUGIN_NAME in plugins:
        raise PytestCompatibilityError(f"{PLUGIN_NAME} is reserved by TestKit")
    command = _pytest_command(args.python, [PLUGIN_NAME, *plugins])
    command.extend(["--collect-only", "-q", *selectors])

    with tempfile.TemporaryDirectory(prefix="testkit-pytest-collect-") as directory:
        raw_output = Path(directory) / "collection.json"
        try:
            completed = subprocess.run(
                command,
                cwd=root,
                env=_subprocess_env(raw_output, plugins),
                text=True,
                capture_output=True,
                timeout=args.timeout,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise PytestCompatibilityError(f"Pytest collection failed: {exc}") from exc
        stdout = _redact(completed.stdout, secrets)
        stderr = _redact(completed.stderr, secrets)
        if completed.returncode != 0:
            if stdout:
                print(stdout, end="" if stdout.endswith("\n") else "\n")
            if stderr:
                print(stderr, file=sys.stderr, end="" if stderr.endswith("\n") else "\n")
            raise PytestCompatibilityError(
                f"Pytest collection exited with code {completed.returncode}"
            )
        if not raw_output.is_file():
            raise PytestCompatibilityError("Collection plugin did not produce metadata")
        try:
            raw = json.loads(raw_output.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise PytestCompatibilityError(f"Collection metadata is invalid: {exc}") from exc

    items = raw.get("items")
    if not isinstance(items, list) or not items:
        raise PytestCompatibilityError("Pytest collected zero tests")
    raw_root = Path(str(raw.get("rootdir", ""))).resolve()
    if raw_root != root:
        raise PytestCompatibilityError(
            "Pytest rootdir must equal the explicit project root"
        )
    sources, node_sources = _source_files(root, items, raw.get("config_path"))
    _reject_path_overlap(
        [output],
        [(root / source["path"]).resolve() for source in sources],
    )
    nodeids = [str(item["nodeid"]) for item in items]
    if len(nodeids) != len(set(nodeids)):
        raise PytestCompatibilityError("Pytest collection returned duplicate nodeids")
    config_path = raw.get("config_path")
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "runner": "pytest",
        "project_root": ".",
        "pytest_version": raw.get("pytest_version"),
        "config_path": (
            _relative_path(Path(config_path), root, label="Pytest config")
            if config_path
            else None
        ),
        "selectors": selectors,
        "plugin_autoload": "disabled",
        "ambient_pytest_env": "ignored",
        "explicit_plugins": raw.get("explicit_plugins", []),
        "source_fingerprint": _fingerprint(sources),
        "sources": sources,
        "tests": [
            {"nodeid": nodeid, "source": node_sources[nodeid]}
            for nodeid in nodeids
        ],
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_json(output, manifest)
    print(f"Collected {len(nodeids)} pytest tests: {output}")
    return 0


def run(args: argparse.Namespace) -> int:
    root = _project_root(args.project_root)
    manifest_path = Path(args.manifest).expanduser().resolve()
    manifest = _load_manifest(manifest_path)
    _validate_manifest_sources(manifest, root)
    secrets = _secret_values(args.secret_env)
    output = _prepare_output(Path(args.output), force=args.force)
    junit = _prepare_output(Path(args.junit), force=args.force)
    protected_sources = [
        (root / str(source["path"])).resolve() for source in manifest["sources"]
    ]
    _reject_path_overlap(
        [output, junit],
        [manifest_path, *protected_sources],
    )

    known = [str(item["nodeid"]) for item in manifest["tests"]]
    selected = known if args.all_collected else list(args.nodeid)
    if not selected:
        raise PytestCompatibilityError("Select --nodeid or --all-collected")
    unknown = [nodeid for nodeid in selected if nodeid not in known]
    if unknown:
        raise PytestCompatibilityError(f"Unknown nodeid: {', '.join(unknown)}")
    if len(selected) != len(set(selected)):
        raise PytestCompatibilityError("Duplicate nodeid selection")

    env = _subprocess_env()
    current_version = _pytest_version(args.python, env, args.timeout)
    if current_version != manifest.get("pytest_version"):
        raise PytestCompatibilityError(
            "Pytest version differs from collection manifest: "
            f"{manifest.get('pytest_version')} != {current_version}"
        )
    plugin_metadata = manifest.get("explicit_plugins")
    if not isinstance(plugin_metadata, list) or not all(
        isinstance(item, dict)
        and isinstance(item.get("name"), str)
        and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*", item["name"]) is not None
        and (item.get("version") is None or isinstance(item.get("version"), str))
        for item in plugin_metadata
    ):
        raise PytestCompatibilityError("Manifest explicit_plugins is invalid")
    plugins = [str(item["name"]) for item in plugin_metadata]
    if _plugin_metadata(args.python, plugins, env, args.timeout, root) != plugin_metadata:
        raise PytestCompatibilityError(
            "Explicit pytest plugin versions differ from collection manifest"
        )

    junit.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=junit.parent,
        prefix=f".{junit.name}.",
        suffix=".xml",
        delete=False,
    ) as temporary:
        temporary_junit = Path(temporary.name)
    temporary_junit.unlink(missing_ok=True)
    command = _pytest_command(args.python, plugins)
    command.extend([*selected, f"--junitxml={temporary_junit}"])
    try:
        completed = subprocess.run(
            command,
            cwd=root,
            env=env,
            text=True,
            capture_output=True,
            timeout=args.timeout,
        )
        stdout = _redact(completed.stdout, secrets)
        stderr = _redact(completed.stderr, secrets)
        if not temporary_junit.is_file():
            raise PytestCompatibilityError(
                f"Pytest did not produce JUnit XML (exit code {completed.returncode})"
            )
        tree, normalized = _normalize_junit(
            temporary_junit,
            exit_code=completed.returncode,
            secrets=secrets,
        )
        tree.write(temporary_junit, encoding="utf-8", xml_declaration=True)
        temporary_junit.replace(junit)
        payload = _normalized_result(
            normalized,
            manifest=manifest_path.name,
            nodeids=selected,
            pytest_version=current_version,
            stdout=stdout,
            stderr=stderr,
            output_limit=args.output_limit,
        )
        _write_json(output, payload)
    except subprocess.TimeoutExpired as exc:
        temporary_junit.unlink(missing_ok=True)
        stdout = _redact(exc.stdout or "", secrets) if isinstance(exc.stdout, str) else ""
        stderr = _redact(exc.stderr or "", secrets) if isinstance(exc.stderr, str) else ""
        payload = _normalized_result(
            {
                "status": "error",
                "exit_code": 124,
                "summary": {"total": 0, "passed": 0, "failed": 0, "errors": 0, "skipped": 0},
                "tests": [],
            },
            manifest=manifest_path.name,
            nodeids=selected,
            pytest_version=current_version,
            stdout=stdout,
            stderr=stderr + "\nPytest execution timed out",
            output_limit=args.output_limit,
        )
        _write_json(output, payload)
        print(f"Pytest timed out; result: {output}", file=sys.stderr)
        return 2
    except (OSError, PytestCompatibilityError):
        temporary_junit.unlink(missing_ok=True)
        raise

    if stdout:
        print(stdout, end="" if stdout.endswith("\n") else "\n")
    if stderr:
        print(stderr, file=sys.stderr, end="" if stderr.endswith("\n") else "\n")
    print(f"Pytest result: {output}")
    return 0 if completed.returncode == 0 else 1 if completed.returncode == 1 else 2


def normalize(args: argparse.Namespace) -> int:
    secrets = _secret_values(args.secret_env)
    output = _prepare_output(Path(args.output), force=args.force)
    junit = Path(args.junit).expanduser().resolve()
    protected = [junit]
    if args.stdout_file:
        protected.append(Path(args.stdout_file).expanduser().resolve())
    if args.stderr_file:
        protected.append(Path(args.stderr_file).expanduser().resolve())
    outputs = [output]
    sanitized = None
    if args.sanitized_junit:
        sanitized = _prepare_output(Path(args.sanitized_junit), force=args.force)
        outputs.append(sanitized)
    _reject_path_overlap(outputs, protected)
    tree, normalized = _normalize_junit(junit, exit_code=args.exit_code, secrets=secrets)
    if sanitized is not None:
        sanitized.parent.mkdir(parents=True, exist_ok=True)
        tree.write(sanitized, encoding="utf-8", xml_declaration=True)
    stdout = ""
    stderr = ""
    if args.stdout_file:
        stdout = _redact(Path(args.stdout_file).read_text(encoding="utf-8"), secrets)
    if args.stderr_file:
        stderr = _redact(Path(args.stderr_file).read_text(encoding="utf-8"), secrets)
    payload = _normalized_result(
        normalized,
        manifest=None,
        nodeids=[],
        pytest_version=None,
        stdout=stdout,
        stderr=stderr,
        output_limit=args.output_limit,
    )
    _write_json(output, payload)
    print(f"Normalized pytest result: {output}")
    return 0 if args.exit_code == 0 else 1 if args.exit_code == 1 else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect_parser = subparsers.add_parser(
        "collect", help="Collect an explicit pytest scope into a source-bound manifest"
    )
    collect_parser.add_argument("project_root")
    collect_parser.add_argument("--selector", action="append", required=True)
    collect_parser.add_argument("--output", required=True)
    collect_parser.add_argument("--python", default=sys.executable)
    collect_parser.add_argument("--plugin", action="append", default=[])
    collect_parser.add_argument("--secret-env", action="append", default=[])
    collect_parser.add_argument("--timeout", type=float, default=120)
    collect_parser.add_argument("--force", action="store_true")
    collect_parser.set_defaults(handler=collect)

    run_parser = subparsers.add_parser(
        "run", help="Run manifest nodeids and emit sanitized JUnit plus normalized JSON"
    )
    run_parser.add_argument("project_root")
    run_parser.add_argument("--manifest", required=True)
    selection = run_parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--nodeid", action="append")
    selection.add_argument("--all-collected", action="store_true")
    run_parser.add_argument("--output", required=True)
    run_parser.add_argument("--junit", required=True)
    run_parser.add_argument("--python", default=sys.executable)
    run_parser.add_argument("--secret-env", action="append", default=[])
    run_parser.add_argument("--timeout", type=float, default=300)
    run_parser.add_argument("--output-limit", type=int, default=65536)
    run_parser.add_argument("--force", action="store_true")
    run_parser.set_defaults(handler=run)

    normalize_parser = subparsers.add_parser(
        "normalize", help="Normalize an externally produced pytest JUnit result"
    )
    normalize_parser.add_argument("--junit", required=True)
    normalize_parser.add_argument("--exit-code", type=int, required=True)
    normalize_parser.add_argument("--output", required=True)
    normalize_parser.add_argument("--sanitized-junit")
    normalize_parser.add_argument("--stdout-file")
    normalize_parser.add_argument("--stderr-file")
    normalize_parser.add_argument("--secret-env", action="append", default=[])
    normalize_parser.add_argument("--output-limit", type=int, default=65536)
    normalize_parser.add_argument("--force", action="store_true")
    normalize_parser.set_defaults(handler=normalize)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    timeout = getattr(args, "timeout", 1)
    if not math.isfinite(timeout) or timeout <= 0:
        print("ERROR: --timeout must be positive", file=sys.stderr)
        return 2
    output_limit = getattr(args, "output_limit", 1)
    if type(output_limit) is not int or output_limit <= 0:
        print("ERROR: --output-limit must be positive", file=sys.stderr)
        return 2
    try:
        return args.handler(args)
    except (OSError, PytestCompatibilityError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
