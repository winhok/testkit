from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import run_automation  # noqa: E402


class RunAutomationTests(unittest.TestCase):
    def test_workflow_output_seeds_schema_header_without_persisting_secret(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            workflow = root / "workflow.yaml"
            schema = root / "openapi.yaml"
            workflow.write_text("arazzo: 1.1.0\n", encoding="utf-8")
            schema.write_text("openapi: 3.1.0\npaths: {}\n", encoding="utf-8")
            workflow_result = root / "workflow-result.json"
            schema_result = root / "schema-result.json"
            combined_result = root / "automation-result.json"
            runner = Mock()
            runner.declared_output_names.return_value = {"token"}

            def run_side_effect(**kwargs):
                kwargs["output_sink"]["token"] = "token-secret"
                return {
                    "status": "passed",
                    "summary": {"total": 1, "passed": 1, "failed": 0},
                    "runs": [],
                }

            runner.run.side_effect = run_side_effect
            seen: dict[str, object] = {}

            def fake_schema_main(argv):
                seen["argv"] = argv
                env_name = argv[argv.index("--header-env") + 1].split("=", 1)[1]
                raw_env_name = argv[argv.index("--secret-env") + 1]
                seen["secret"] = os.environ[env_name]
                seen["raw_secret"] = os.environ[raw_env_name]
                Path(argv[argv.index("--output") + 1]).write_text(
                    json.dumps({"status": "passed"}),
                    encoding="utf-8",
                )
                return 0

            with patch("run_automation.run_api._runner_executable", return_value="/bin/schemathesis"), patch(
                "run_automation.WorkflowRunner", return_value=runner
            ), patch(
                "run_automation.run_api.main", side_effect=fake_schema_main
            ), patch.dict(os.environ, {}, clear=True):
                code = run_automation.main(
                    [
                        str(workflow),
                        "--schema",
                        str(schema),
                        "--url",
                        "https://api.example.invalid",
                        "--preflight-workflow",
                        "login",
                        "--schema-header-from-output",
                        "Authorization=token",
                        "--header-template",
                        "Authorization=Bearer {value}",
                        "--workflow-output",
                        str(workflow_result),
                        "--schema-output",
                        str(schema_result),
                        "--output",
                        str(combined_result),
                    ]
                )
                leaked_env = [
                    name
                    for name, value in os.environ.items()
                    if value in {"Bearer token-secret", "token-secret"}
                ]
                workflow_text = workflow_result.read_text(encoding="utf-8")

        self.assertEqual(code, 0)
        self.assertEqual(seen["secret"], "Bearer token-secret")
        self.assertEqual(seen["raw_secret"], "token-secret")
        self.assertEqual(leaked_env, [])
        self.assertNotIn("token-secret", workflow_text)

    def test_missing_requested_output_stops_before_schema_run(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            workflow = root / "workflow.yaml"
            schema = root / "openapi.yaml"
            workflow.write_text("arazzo: 1.1.0\n", encoding="utf-8")
            schema.write_text("openapi: 3.1.0\npaths: {}\n", encoding="utf-8")
            runner = Mock()
            runner.declared_output_names.return_value = set()
            runner.run.return_value = {
                "status": "passed",
                "summary": {"total": 1, "passed": 1, "failed": 0},
                "runs": [],
            }
            with patch("run_automation.run_api._runner_executable", return_value="/bin/schemathesis"), patch(
                "run_automation.WorkflowRunner", return_value=runner
            ), patch(
                "run_automation.run_api.main"
            ) as schema_main:
                code = run_automation.main(
                    [
                        str(workflow),
                        "--schema",
                        str(schema),
                        "--url",
                        "https://api.example.invalid",
                        "--preflight-workflow",
                        "login",
                        "--schema-header-from-output",
                        "Authorization=missing",
                        "--workflow-output",
                        str(root / "workflow.json"),
                        "--schema-output",
                        str(root / "schema.json"),
                        "--output",
                        str(root / "automation.json"),
                    ]
                )
        self.assertEqual(code, 2)
        runner.run.assert_not_called()
        schema_main.assert_not_called()

    def test_force_cannot_overwrite_workflow_input_with_report(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            workflow = root / "workflow.yaml"
            schema = root / "openapi.yaml"
            workflow.write_text("arazzo: 1.1.0\n", encoding="utf-8")
            schema.write_text("openapi: 3.1.0\npaths: {}\n", encoding="utf-8")

            with patch(
                "run_automation.run_api._runner_executable",
                return_value="/bin/schemathesis",
            ), patch("run_automation.WorkflowRunner") as runner_type, patch(
                "run_automation.run_api.main"
            ) as schema_main:
                code = run_automation.main(
                    [
                        str(workflow),
                        "--schema",
                        str(schema),
                        "--url",
                        "https://api.example.invalid",
                        "--preflight-workflow",
                        "login",
                        "--workflow-output",
                        str(workflow),
                        "--schema-output",
                        str(root / "schema-result.json"),
                        "--output",
                        str(root / "automation-result.json"),
                        "--force",
                    ]
                )

        self.assertEqual(code, 2)
        runner_type.assert_not_called()
        schema_main.assert_not_called()

    def test_nonempty_allure_directory_is_rejected_before_preflight_even_with_force(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            workflow = root / "workflow.yaml"
            schema = root / "openapi.yaml"
            allure = root / "allure"
            workflow.write_text("arazzo: 1.1.0\n", encoding="utf-8")
            schema.write_text("openapi: 3.1.0\npaths: {}\n", encoding="utf-8")
            allure.mkdir()
            (allure / "old-result.json").write_text("keep", encoding="utf-8")

            with patch(
                "run_automation.run_api._runner_executable",
                return_value="/bin/schemathesis",
            ), patch("run_automation.WorkflowRunner") as runner_type, patch(
                "run_automation.run_api.main"
            ) as schema_main:
                code = run_automation.main(
                    [
                        str(workflow),
                        "--schema",
                        str(schema),
                        "--url",
                        "https://api.example.invalid",
                        "--preflight-workflow",
                        "login",
                        "--allure-results",
                        str(allure),
                        "--force",
                    ]
                )

        self.assertEqual(code, 2)
        runner_type.assert_not_called()
        schema_main.assert_not_called()


if __name__ == "__main__":
    unittest.main()
