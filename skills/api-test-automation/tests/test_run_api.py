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

import run_api  # noqa: E402


class RunApiTests(unittest.TestCase):
    def _schema(self, root: Path) -> Path:
        schema = root / "openapi.yaml"
        schema.write_text("openapi: 3.1.0\npaths: {}\n", encoding="utf-8")
        return schema

    def test_missing_secret_fails_before_subprocess(self):
        with tempfile.TemporaryDirectory() as td:
            schema = self._schema(Path(td))
            with patch.dict(os.environ, {}, clear=True), patch(
                "run_api.shutil.which", return_value="/bin/schemathesis"
            ), patch("run_api.subprocess.run") as run:
                code = run_api.main(
                    [
                        str(schema),
                        "--url",
                        "https://api.example.invalid",
                        "--header-env",
                        "Authorization=API_TOKEN",
                    ]
                )
        self.assertEqual(code, 2)
        run.assert_not_called()

    def test_full_mode_requires_explicit_non_production_confirmation(self):
        with tempfile.TemporaryDirectory() as td:
            schema = self._schema(Path(td))
            with patch(
                "run_api.shutil.which", return_value="/bin/schemathesis"
            ), patch("run_api.subprocess.run") as run:
                code = run_api.main(
                    [
                        str(schema),
                        "--url",
                        "https://api.example.invalid",
                        "--mode",
                        "full",
                    ]
                )
        self.assertEqual(code, 2)
        run.assert_not_called()

    def test_existing_result_is_not_overwritten_without_force(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            schema = self._schema(root)
            output = root / "run-result.json"
            output.write_text("keep-me\n", encoding="utf-8")
            with patch(
                "run_api.shutil.which", return_value="/bin/schemathesis"
            ), patch("run_api.subprocess.run") as run:
                code = run_api.main(
                    [
                        str(schema),
                        "--url",
                        "https://api.example.invalid",
                        "--output",
                        str(output),
                    ]
                )
            preserved = output.read_text(encoding="utf-8")
        self.assertEqual(code, 2)
        self.assertEqual(preserved, "keep-me\n")
        run.assert_not_called()

    def test_passthrough_cannot_override_managed_safety_options(self):
        with tempfile.TemporaryDirectory() as td:
            schema = self._schema(Path(td))
            with patch(
                "run_api.shutil.which", return_value="/bin/schemathesis"
            ), patch("run_api.subprocess.run") as run:
                code = run_api.main(
                    [
                        str(schema),
                        "--url",
                        "https://api.example.invalid",
                        "--",
                        "--phases=stateful",
                    ]
                )
        self.assertEqual(code, 2)
        run.assert_not_called()

    def test_attached_header_passthrough_cannot_bypass_secret_redaction(self):
        with tempfile.TemporaryDirectory() as td:
            schema = self._schema(Path(td))
            with patch(
                "run_api.shutil.which", return_value="/bin/schemathesis"
            ), patch("run_api.subprocess.run") as run:
                code = run_api.main(
                    [
                        str(schema),
                        "--url",
                        "https://api.example.invalid",
                        "--",
                        "-HAuthorization:plain-secret",
                    ]
                )
        self.assertEqual(code, 2)
        run.assert_not_called()

    def test_basic_auth_passthrough_cannot_put_credentials_in_result_command(self):
        with tempfile.TemporaryDirectory() as td:
            schema = self._schema(Path(td))
            with patch(
                "run_api.shutil.which", return_value="/bin/schemathesis"
            ), patch("run_api.subprocess.run") as run:
                code = run_api.main(
                    [
                        str(schema),
                        "--url",
                        "https://api.example.invalid",
                        "--",
                        "--auth=user:plain-secret",
                    ]
                )
        self.assertEqual(code, 2)
        run.assert_not_called()

    def test_secret_is_redacted_from_result(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            schema = self._schema(root)
            output = root / "run-result.json"
            completed = Mock(
                returncode=1,
                stdout="request token-secret failed\n",
                stderr="Authorization: token-secret\n",
            )
            with patch.dict(os.environ, {"API_TOKEN": "token-secret"}), patch(
                "run_api.shutil.which", return_value="/bin/schemathesis"
            ), patch("run_api.subprocess.run", return_value=completed):
                code = run_api.main(
                    [
                        str(schema),
                        "--url",
                        "https://api.example.invalid",
                        "--header-env",
                        "Authorization=API_TOKEN",
                        "--output",
                        str(output),
                    ]
                )
            result_text = output.read_text(encoding="utf-8")
        self.assertEqual(code, 1)
        self.assertNotIn("token-secret", result_text)
        self.assertIn("[REDACTED]", result_text)
        self.assertEqual(json.loads(result_text)["status"], "failed")
        command = json.loads(result_text)["command"]
        self.assertIn("--include-method", command)
        self.assertNotIn("POST", command)

    def test_short_secret_does_not_corrupt_normalized_report_text(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            schema = self._schema(root)
            output = root / "run-result.json"
            completed = Mock(
                returncode=0,
                stdout="status: passed\nAuthorization: t\n",
                stderr="",
            )
            with patch.dict(os.environ, {"API_TOKEN": "t"}), patch(
                "run_api.shutil.which", return_value="/bin/schemathesis"
            ), patch("run_api.subprocess.run", return_value=completed):
                code = run_api.main(
                    [
                        str(schema),
                        "--url",
                        "https://api.example.invalid",
                        "--header-env",
                        "Authorization=API_TOKEN",
                        "--output",
                        str(output),
                    ]
                )
            result = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(code, 0)
        self.assertIn("status: passed", result["stdout"])
        self.assertIn("Authorization: [REDACTED]", result["stdout"])
        self.assertIn("https://api.example.invalid", result["command"])
        self.assertIn("[REDACTED]", result["command"])

    def test_additional_secret_env_redacts_bare_templated_header_value(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            schema = self._schema(root)
            output = root / "run-result.json"
            completed = Mock(
                returncode=1,
                stdout="echoed token-secret\nAuthorization: Bearer token-secret\n",
                stderr="",
            )
            with patch.dict(
                os.environ,
                {
                    "API_HEADER": "Bearer token-secret",
                    "API_RAW_TOKEN": "token-secret",
                },
            ), patch(
                "run_api.shutil.which", return_value="/bin/schemathesis"
            ), patch("run_api.subprocess.run", return_value=completed):
                code = run_api.main(
                    [
                        str(schema),
                        "--url",
                        "https://api.example.invalid",
                        "--header-env",
                        "Authorization=API_HEADER",
                        "--secret-env",
                        "API_RAW_TOKEN",
                        "--output",
                        str(output),
                    ]
                )
            result_text = output.read_text(encoding="utf-8")

        self.assertEqual(code, 1)
        self.assertNotIn("token-secret", result_text)

    def test_smoke_unsafe_methods_require_explicit_target_confirmation(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            schema = self._schema(root)
            output = root / "run-result.json"
            completed = Mock(returncode=0, stdout="", stderr="")
            with patch(
                "run_api.shutil.which", return_value="/bin/schemathesis"
            ), patch("run_api.subprocess.run", return_value=completed) as run:
                code = run_api.main(
                    [
                        str(schema),
                        "--url",
                        "https://api.example.invalid",
                        "--allow-mutating-target",
                        "--output",
                        str(output),
                    ]
                )
            command = run.call_args.args[0]
        self.assertEqual(code, 0)
        self.assertNotIn("--include-method", command)

    def test_passthrough_cannot_expand_safe_method_filter(self):
        with tempfile.TemporaryDirectory() as td:
            schema = self._schema(Path(td))
            with patch(
                "run_api.shutil.which", return_value="/bin/schemathesis"
            ), patch("run_api.subprocess.run") as run:
                code = run_api.main(
                    [
                        str(schema),
                        "--url",
                        "https://api.example.invalid",
                        "--",
                        "--include-method",
                        "POST",
                    ]
                )
        self.assertEqual(code, 2)
        run.assert_not_called()

    def test_passthrough_cannot_write_runner_reports_over_the_schema(self):
        with tempfile.TemporaryDirectory() as td:
            schema = self._schema(Path(td))
            with patch(
                "run_api.shutil.which", return_value="/bin/schemathesis"
            ), patch("run_api.subprocess.run") as run:
                code = run_api.main(
                    [
                        str(schema),
                        "--url",
                        "https://api.example.invalid",
                        "--",
                        "--report",
                        "junit",
                        "--report-junit-path",
                        str(schema),
                    ]
                )
        self.assertEqual(code, 2)
        run.assert_not_called()

    def test_unexpected_runner_exit_is_normalized_to_configuration_exit_two(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            schema = self._schema(root)
            output = root / "run-result.json"
            completed = Mock(returncode=9, stdout="", stderr="terminated\n")
            with patch(
                "run_api.shutil.which", return_value="/bin/schemathesis"
            ), patch("run_api.subprocess.run", return_value=completed):
                code = run_api.main(
                    [
                        str(schema),
                        "--url",
                        "https://api.example.invalid",
                        "--output",
                        str(output),
                    ]
                )
            result = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "error")

    def test_nonempty_allure_target_is_rejected_before_subprocess(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            schema = self._schema(root)
            allure = root / "allure"
            allure.mkdir()
            (allure / "existing.json").write_text("keep", encoding="utf-8")
            with patch(
                "run_api.shutil.which", return_value="/bin/schemathesis"
            ), patch("run_api.subprocess.run") as run:
                code = run_api.main(
                    [
                        str(schema),
                        "--url",
                        "https://api.example.invalid",
                        "--allure-results",
                        str(allure),
                    ]
                )
        self.assertEqual(code, 2)
        run.assert_not_called()

    def test_force_still_rejects_nonempty_allure_target(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            schema = self._schema(root)
            allure = root / "allure"
            allure.mkdir()
            stale = allure / "old-result.json"
            stale.write_text("keep", encoding="utf-8")
            with patch(
                "run_api.shutil.which", return_value="/bin/schemathesis"
            ), patch("run_api.subprocess.run") as run:
                code = run_api.main(
                    [
                        str(schema),
                        "--url",
                        "https://api.example.invalid",
                        "--allure-results",
                        str(allure),
                        "--force",
                    ]
                )

            preserved = stale.read_text(encoding="utf-8")

        self.assertEqual(code, 2)
        self.assertEqual(preserved, "keep")
        run.assert_not_called()

    def test_falls_back_to_current_python_environment_runner(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            schema = self._schema(root)
            output = root / "run-result.json"
            fake_python = root / "bin" / "python"
            fake_python.parent.mkdir()
            fake_python.write_text("", encoding="utf-8")
            fake_runner = fake_python.parent / "schemathesis"
            fake_runner.write_text("#!/bin/sh\n", encoding="utf-8")
            fake_runner.chmod(0o755)
            completed = Mock(returncode=0, stdout="", stderr="")
            with patch("run_api.shutil.which", return_value=None), patch(
                "run_api.sys.executable", str(fake_python)
            ), patch("run_api.subprocess.run", return_value=completed) as run:
                code = run_api.main(
                    [
                        str(schema),
                        "--url",
                        "https://api.example.invalid",
                        "--allow-mutating-target",
                        "--output",
                        str(output),
                    ]
                )
        self.assertEqual(code, 0)
        self.assertEqual(
            Path(run.call_args.args[0][0]).resolve(),
            fake_runner.resolve(),
        )


if __name__ == "__main__":
    unittest.main()
