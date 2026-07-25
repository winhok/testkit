#!/usr/bin/env python3
"""CI reporters for deterministic API workflow results."""
from __future__ import annotations

import json
import uuid
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class ReportWriteError(ValueError):
    """Raised when a report target is unsafe or invalid."""


def _claim_file(path: Path, *, force: bool) -> None:
    if path.exists() and not force:
        raise ReportWriteError(f"Report already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)


def write_junit(result: dict[str, Any], path: Path, *, force: bool) -> None:
    """Write one JUnit testcase per workflow/dataset run."""
    _claim_file(path, force=force)
    runs = result.get("runs", [])
    suite = ET.Element(
        "testsuite",
        {
            "name": "api-test-automation",
            "tests": str(len(runs)),
            "failures": str(sum(item.get("status") == "failed" for item in runs)),
            "errors": str(sum(item.get("status") == "error" for item in runs)),
            "time": f"{sum(_duration_seconds(item) for item in runs):.6f}",
        },
    )
    for run in runs:
        name = str(run.get("workflow_id", "unknown"))
        if "dataset_index" in run:
            name += f"[{run['dataset_index']}]"
        case = ET.SubElement(
            suite,
            "testcase",
            {
                "classname": "api.workflow",
                "name": name,
                "time": f"{_duration_seconds(run):.6f}",
            },
        )
        status = run.get("status")
        if status == "failed":
            node = ET.SubElement(case, "failure", {"message": str(run.get("error", "failed"))})
            node.text = _step_diagnostics(run)
        elif status == "error":
            node = ET.SubElement(case, "error", {"message": str(run.get("error", "error"))})
            node.text = _step_diagnostics(run)
        output = ET.SubElement(case, "system-out")
        output.text = _step_diagnostics(run)
    ET.indent(suite)
    ET.ElementTree(suite).write(path, encoding="utf-8", xml_declaration=True)


def write_allure_results(
    result: dict[str, Any],
    directory: Path,
    *,
    force: bool,
) -> None:
    """Write minimal Allure 2 result files without exposing response values."""
    if directory.exists() and any(directory.iterdir()):
        raise ReportWriteError(f"Allure results directory is not empty: {directory}")
    directory.mkdir(parents=True, exist_ok=True)
    now_ms = int(datetime.now(UTC).timestamp() * 1000)
    for run in result.get("runs", []):
        workflow_id = str(run.get("workflow_id", "unknown"))
        dataset_index = run.get("dataset_index")
        name = (
            f"{workflow_id}[{dataset_index}]"
            if dataset_index is not None
            else workflow_id
        )
        duration_ms = int(sum(float(step.get("duration_ms", 0)) for step in run.get("steps", [])))
        status = str(run.get("status", "broken"))
        allure_status = {"passed": "passed", "failed": "failed", "error": "broken"}.get(
            status, "broken"
        )
        uid = str(uuid.uuid4())
        payload = {
            "uuid": uid,
            "historyId": str(uuid.uuid5(uuid.NAMESPACE_URL, f"testkit:{name}")),
            "name": name,
            "fullName": f"api.workflow.{name}",
            "status": allure_status,
            "statusDetails": {"message": str(run.get("error", ""))},
            "stage": "finished",
            "start": now_ms,
            "stop": now_ms + duration_ms,
            "labels": [
                {"name": "suite", "value": "API automation workflows"},
                {"name": "framework", "value": "testkit-arazzo"},
            ],
            "steps": [
                {
                    "name": f"{step.get('phase', 'steps')}: {step.get('step_id', 'unknown')}",
                    "status": (
                        "passed" if step.get("status") == "passed" else "failed"
                    ),
                    "statusDetails": {"message": str(step.get("error", ""))},
                    "stage": "finished",
                    "start": now_ms,
                    "stop": now_ms + int(float(step.get("duration_ms", 0))),
                }
                for step in run.get("steps", [])
            ],
        }
        (directory / f"{uid}-result.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _duration_seconds(run: dict[str, Any]) -> float:
    return sum(float(step.get("duration_ms", 0)) for step in run.get("steps", [])) / 1000


def _step_diagnostics(run: dict[str, Any]) -> str:
    lines = []
    for step in run.get("steps", []):
        line = (
            f"{step.get('phase', 'steps')} {step.get('step_id', 'unknown')}: "
            f"{step.get('status', 'unknown')}"
        )
        if step.get("error"):
            line += f" - {step['error']}"
        lines.append(line)
    return "\n".join(lines)
