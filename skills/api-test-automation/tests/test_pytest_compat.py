from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import pytest_compat  # noqa: E402


class PytestCompatibilityTests(unittest.TestCase):
    def _project(self, root: Path) -> Path:
        project = root / "project"
        tests = project / "tests"
        tests.mkdir(parents=True)
        (tests / "test_sample.py").write_text(
            "import os\n\n"
            "def test_ok():\n"
            "    assert 2 + 2 == 4\n\n"
            "def test_secret_failure():\n"
            "    assert False, os.environ['SYNTHETIC_TEST_SECRET']\n",
            encoding="utf-8",
        )
        return project

    def _collect(self, root: Path, project: Path) -> Path:
        manifest = root / "pytest-source-manifest.json"
        code = pytest_compat.main(
            [
                "collect",
                str(project),
                "--selector",
                "tests/test_sample.py",
                "--output",
                str(manifest),
                "--python",
                sys.executable,
            ]
        )
        self.assertEqual(code, 0)
        return manifest

    def test_collect_records_exact_nodeids_and_relative_source_fingerprint(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = self._project(root)
            manifest_path = self._collect(root, project)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(manifest["runner"], "pytest")
        self.assertEqual(manifest["project_root"], ".")
        self.assertEqual(manifest["plugin_autoload"], "disabled")
        self.assertEqual(manifest["ambient_pytest_env"], "ignored")
        self.assertEqual(manifest["explicit_plugins"], [])
        self.assertEqual(len(manifest["tests"]), 2)
        self.assertEqual(
            {item["source"] for item in manifest["tests"]},
            {"tests/test_sample.py"},
        )
        self.assertTrue(
            all(not Path(item["path"]).is_absolute() for item in manifest["sources"])
        )

    def test_collection_ignores_ambient_pytest_control_variables(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = self._project(root)
            with patch.dict(
                os.environ,
                {
                    "PYTEST_ADDOPTS": "--ignore=tests",
                    "PYTEST_PLUGINS": "plugin_that_must_not_load",
                },
            ):
                manifest_path = self._collect(root, project)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(len(manifest["tests"]), 2)

    def test_explicit_plugin_version_is_recorded_and_rechecked(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = self._project(root)
            plugin = project / "synthetic_plugin.py"
            plugin.write_text("__version__ = '1.2.3'\n", encoding="utf-8")
            manifest_path = root / "manifest.json"
            collect_code = pytest_compat.main(
                [
                    "collect",
                    str(project),
                    "--selector",
                    "tests/test_sample.py",
                    "--plugin",
                    "synthetic_plugin",
                    "--output",
                    str(manifest_path),
                    "--python",
                    sys.executable,
                ]
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            plugin.write_text("__version__ = '2.0.0'\n", encoding="utf-8")
            run_code = pytest_compat.main(
                [
                    "run",
                    str(project),
                    "--manifest",
                    str(manifest_path),
                    "--all-collected",
                    "--output",
                    str(root / "result.json"),
                    "--junit",
                    str(root / "result.xml"),
                    "--python",
                    sys.executable,
                ]
            )

        self.assertEqual(collect_code, 0)
        self.assertEqual(
            manifest["explicit_plugins"],
            [{"name": "synthetic_plugin", "version": "1.2.3"}],
        )
        self.assertEqual(run_code, 2)

    def test_run_uses_manifest_nodeid_and_redacts_json_and_junit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = self._project(root)
            manifest = self._collect(root, project)
            output = root / "pytest-run-result.json"
            junit = root / "pytest-junit.xml"
            with patch.dict(
                os.environ,
                {"SYNTHETIC_TEST_SECRET": "synthetic-secret-value"},
            ):
                code = pytest_compat.main(
                    [
                        "run",
                        str(project),
                        "--manifest",
                        str(manifest),
                        "--nodeid",
                        "tests/test_sample.py::test_secret_failure",
                        "--output",
                        str(output),
                        "--junit",
                        str(junit),
                        "--secret-env",
                        "SYNTHETIC_TEST_SECRET",
                        "--python",
                        sys.executable,
                    ]
                )
            result_text = output.read_text(encoding="utf-8")
            junit_text = junit.read_text(encoding="utf-8")
            result = json.loads(result_text)

        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["exit_code"], 1)
        self.assertEqual(result["summary"]["failed"], 1)
        self.assertNotIn("synthetic-secret-value", result_text)
        self.assertNotIn("synthetic-secret-value", junit_text)
        self.assertIn("[REDACTED]", result_text)
        self.assertIn("[REDACTED]", junit_text)

    def test_source_change_makes_manifest_stale_before_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = self._project(root)
            manifest = self._collect(root, project)
            (project / "tests" / "test_sample.py").write_text(
                "def test_changed():\n    assert True\n",
                encoding="utf-8",
            )
            code = pytest_compat.main(
                [
                    "run",
                    str(project),
                    "--manifest",
                    str(manifest),
                    "--all-collected",
                    "--output",
                    str(root / "result.json"),
                    "--junit",
                    str(root / "result.xml"),
                    "--python",
                    sys.executable,
                ]
            )

        self.assertEqual(code, 2)

    def test_new_conftest_makes_manifest_stale_before_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = self._project(root)
            manifest = self._collect(root, project)
            (project / "conftest.py").write_text("SYNTHETIC = True\n", encoding="utf-8")
            code = pytest_compat.main(
                [
                    "run",
                    str(project),
                    "--manifest",
                    str(manifest),
                    "--all-collected",
                    "--output",
                    str(root / "result.json"),
                    "--junit",
                    str(root / "result.xml"),
                    "--python",
                    sys.executable,
                ]
            )

        self.assertEqual(code, 2)

    def test_force_cannot_overwrite_a_manifest_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = self._project(root)
            manifest = self._collect(root, project)
            source = project / "tests" / "test_sample.py"
            original = source.read_text(encoding="utf-8")
            code = pytest_compat.main(
                [
                    "run",
                    str(project),
                    "--manifest",
                    str(manifest),
                    "--all-collected",
                    "--output",
                    str(source),
                    "--junit",
                    str(root / "result.xml"),
                    "--force",
                    "--python",
                    sys.executable,
                ]
            )
            preserved = source.read_text(encoding="utf-8")

        self.assertEqual(code, 2)
        self.assertEqual(preserved, original)

    def test_unknown_nodeid_is_rejected_without_creating_results(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = self._project(root)
            manifest = self._collect(root, project)
            output = root / "result.json"
            junit = root / "result.xml"
            code = pytest_compat.main(
                [
                    "run",
                    str(project),
                    "--manifest",
                    str(manifest),
                    "--nodeid",
                    "tests/test_sample.py::test_missing",
                    "--output",
                    str(output),
                    "--junit",
                    str(junit),
                    "--python",
                    sys.executable,
                ]
            )

        self.assertEqual(code, 2)
        self.assertFalse(output.exists())
        self.assertFalse(junit.exists())

    def test_normalize_rejects_malformed_junit_without_overwriting_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            junit = root / "broken.xml"
            output = root / "result.json"
            junit.write_text("<testsuite>", encoding="utf-8")
            code = pytest_compat.main(
                [
                    "normalize",
                    "--junit",
                    str(junit),
                    "--exit-code",
                    "1",
                    "--output",
                    str(output),
                ]
            )

        self.assertEqual(code, 2)
        self.assertFalse(output.exists())

    def test_normalize_outputs_must_not_overlap_inputs_or_each_other(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            junit = root / "input.xml"
            junit.write_text(
                "<?xml version='1.0'?><testsuite><testcase name='ok'/></testsuite>",
                encoding="utf-8",
            )
            original = junit.read_text(encoding="utf-8")
            code = pytest_compat.main(
                [
                    "normalize",
                    "--junit",
                    str(junit),
                    "--exit-code",
                    "0",
                    "--output",
                    str(junit),
                    "--force",
                ]
            )
            preserved = junit.read_text(encoding="utf-8")

        self.assertEqual(code, 2)
        self.assertEqual(preserved, original)


if __name__ == "__main__":
    unittest.main()
