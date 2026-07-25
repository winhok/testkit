from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from run_workflows import (  # noqa: E402
    CliConfigurationError,
    load_datasets,
    parse_input_env,
    parse_inputs,
    validate_protected_targets,
    validate_report_targets,
    write_json_result,
)
from workflow_reports import write_allure_results, write_junit  # noqa: E402


class WorkflowCliSupportTests(unittest.TestCase):
    def test_inputs_and_secret_env_are_kept_separate(self):
        with patch.dict(os.environ, {"API_PASSWORD": "super-secret"}, clear=True):
            inputs = parse_inputs(["username=alice", "enabled=true", "limit=3"])
            env_inputs, secrets = parse_input_env(
                ["password=API_PASSWORD", "password=API_PASSWORD"]
            )

        self.assertEqual(
            inputs,
            {"username": "alice", "enabled": True, "limit": 3},
        )
        self.assertEqual(env_inputs, {"password": "super-secret"})
        self.assertEqual(secrets, ["super-secret"])

    def test_missing_secret_env_fails_during_configuration(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(CliConfigurationError, "MISSING_TOKEN"):
                parse_input_env(["token=MISSING_TOKEN"])

    def test_load_csv_and_json_datasets_with_limit(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            csv_path = root / "data.csv"
            csv_path.write_text("username,active\nalice,true\nbob,false\n", encoding="utf-8")
            json_path = root / "data.json"
            json_path.write_text(
                json.dumps([{"username": "carol"}, {"username": "dave"}]),
                encoding="utf-8",
            )

            csv_rows = load_datasets(csv_path, max_runs=1)
            json_rows = load_datasets(json_path, max_runs=2)

        self.assertEqual(csv_rows, [{"username": "alice", "active": True}])
        self.assertEqual(
            json_rows,
            [{"username": "carol"}, {"username": "dave"}],
        )

    def test_json_result_refuses_overwrite_without_force(self):
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "result.json"
            output.write_text("old", encoding="utf-8")
            with self.assertRaisesRegex(CliConfigurationError, "already exists"):
                write_json_result(output, {"status": "passed"}, force=False)
            write_json_result(output, {"status": "passed"}, force=True)
            self.assertEqual(json.loads(output.read_text())["status"], "passed")

    def test_existing_report_target_is_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            output = root / "result.json"
            junit = root / "junit.xml"
            output.write_text("existing", encoding="utf-8")
            with self.assertRaisesRegex(CliConfigurationError, "result.json"):
                validate_report_targets(
                    output=output,
                    junit=junit,
                    allure_results=None,
                    force=False,
                )

    def test_force_still_rejects_nonempty_allure_directory(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            allure = root / "allure"
            allure.mkdir()
            stale = allure / "old-attachment.txt"
            stale.write_text("keep", encoding="utf-8")

            with self.assertRaisesRegex(
                CliConfigurationError,
                "already exists",
            ):
                validate_report_targets(
                    output=root / "result.json",
                    junit=None,
                    allure_results=allure,
                    force=True,
                )

            self.assertEqual(stale.read_text(encoding="utf-8"), "keep")

    def test_force_cannot_overwrite_a_workflow_or_schema_input(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            workflow = root / "workflow.yaml"
            schema = root / "openapi.yaml"
            workflow.write_text("arazzo: 1.1.0\n", encoding="utf-8")
            schema.write_text("openapi: 3.1.0\n", encoding="utf-8")

            with self.assertRaisesRegex(
                CliConfigurationError,
                "must not overwrite",
            ):
                validate_protected_targets(
                    reports=[workflow],
                    protected=[workflow, schema],
                )


class WorkflowReporterTests(unittest.TestCase):
    RESULT = {
        "status": "failed",
        "summary": {"total": 2, "passed": 1, "failed": 1},
        "runs": [
            {
                "workflow_id": "ok",
                "status": "passed",
                "steps": [
                    {
                        "step_id": "health",
                        "phase": "steps",
                        "status": "passed",
                        "duration_ms": 2.5,
                    }
                ],
            },
            {
                "workflow_id": "bad",
                "status": "failed",
                "error": "business assertion failed",
                "steps": [
                    {
                        "step_id": "getUser",
                        "phase": "steps",
                        "status": "failed",
                        "duration_ms": 3,
                        "error": "business assertion failed",
                    }
                ],
            },
        ],
    }

    def test_junit_and_allure_reporters_preserve_failure(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            junit = root / "junit.xml"
            allure = root / "allure"
            write_junit(self.RESULT, junit, force=False)
            write_allure_results(self.RESULT, allure, force=False)

            suite = ET.parse(junit).getroot()
            allure_docs = [
                json.loads(path.read_text(encoding="utf-8"))
                for path in allure.glob("*-result.json")
            ]

        self.assertEqual(suite.attrib["tests"], "2")
        self.assertEqual(suite.attrib["failures"], "1")
        self.assertEqual(
            {item["name"]: item["status"] for item in allure_docs},
            {"ok": "passed", "bad": "failed"},
        )


if __name__ == "__main__":
    unittest.main()
