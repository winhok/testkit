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

    def test_unexpected_runner_exit_is_an_execution_error(self):
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
        self.assertEqual(code, 9)
        self.assertEqual(result["status"], "error")


if __name__ == "__main__":
    unittest.main()
