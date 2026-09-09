#!/usr/bin/env python3
"""Pytest subprocess plugin used to emit a machine-readable collection inventory."""
from __future__ import annotations

import json
import importlib
import importlib.metadata
import os
from pathlib import Path

import pytest


OUTPUT_ENV = "TESTKIT_PYTEST_COLLECTION_OUTPUT"
PLUGINS_ENV = "TESTKIT_PYTEST_EXPLICIT_PLUGINS"


def plugin_metadata(names: list[str]) -> list[dict[str, str | None]]:
    """Resolve explicit plugin module versions inside the selected Python environment."""
    package_map = importlib.metadata.packages_distributions()
    result: list[dict[str, str | None]] = []
    for name in names:
        module = importlib.import_module(name)
        version = getattr(module, "__version__", None)
        if not isinstance(version, str) or not version:
            distributions = sorted(package_map.get(name.split(".", 1)[0], []))
            versions = []
            for distribution in distributions:
                try:
                    versions.append(importlib.metadata.version(distribution))
                except importlib.metadata.PackageNotFoundError:
                    continue
            version = ",".join(sorted(set(versions))) or None
        result.append({"name": name, "version": version})
    return result


def pytest_collection_finish(session: pytest.Session) -> None:
    """Write collection metadata for the parent TestKit process."""
    output = os.environ.get(OUTPUT_ENV)
    if not output:
        raise pytest.UsageError(f"{OUTPUT_ENV} is required")

    items = []
    for item in session.items:
        item_path = Path(str(item.path)).resolve()
        items.append({"nodeid": item.nodeid, "path": str(item_path)})

    try:
        explicit_plugins = json.loads(os.environ.get(PLUGINS_ENV, "[]"))
    except json.JSONDecodeError as exc:
        raise pytest.UsageError(f"{PLUGINS_ENV} must be JSON") from exc
    if not isinstance(explicit_plugins, list) or not all(
        isinstance(name, str) for name in explicit_plugins
    ):
        raise pytest.UsageError(f"{PLUGINS_ENV} must be a string array")

    payload = {
        "pytest_version": pytest.__version__,
        "rootdir": str(session.config.rootpath.resolve()),
        "config_path": (
            str(session.config.inipath.resolve())
            if session.config.inipath is not None
            else None
        ),
        "explicit_plugins": plugin_metadata(explicit_plugins),
        "items": items,
    }
    Path(output).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
