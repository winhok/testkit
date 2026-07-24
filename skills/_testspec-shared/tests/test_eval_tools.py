from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
CONTEXT_SCRIPT = REPO_ROOT / "skills/_testspec-shared/scripts/validate_context_chain.py"
EVAL_SCRIPT = REPO_ROOT / "skills/_testspec-shared/scripts/validate_evals.py"


def load_context_module():
    spec = importlib.util.spec_from_file_location("validate_context_chain", CONTEXT_SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_eval_module():
    spec = importlib.util.spec_from_file_location("validate_evals", EVAL_SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def markdown_with_context(title: str, context: dict) -> str:
    return (
        f"# {title}\n\n"
        "<!-- testspec-context\n"
        f"{json.dumps(context, ensure_ascii=False)}\n"
        "-->\n"
    )


class TestContextChain(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_context_module()

    def test_accepts_complete_versioned_chain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            change = Path(tmp)
            revision = {
                "version": 2,
                "summary": "synthetic revision",
                "updated_by_skill": "testspec-update",
            }
            base = {
                "source_revision": revision,
                "blocking_open_questions": [],
                "dynamic_followups": [],
                "material_quality": "high",
                "stale_downstream_artifacts": [],
            }
            (change / "specs").mkdir()
            (change / "artifacts").mkdir()
            (change / "requirements.md").write_text(
                markdown_with_context("Requirements", {"source_skill": "testspec-update", **base}),
                encoding="utf-8",
            )
            (change / "requirements-analysis.md").write_text(
                markdown_with_context("Analysis", {"source_skill": "testspec-analysis", **base}),
                encoding="utf-8",
            )
            (change / "specs/testpoints.md").write_text(
                markdown_with_context("Points", {"source_skill": "testspec-points", **base}),
                encoding="utf-8",
            )
            (change / "artifacts/testcases.json").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "_context": {"source_skill": "testspec-generate", **base},
                        "testcases": [{"id": "SYN_001"}],
                    }
                ),
                encoding="utf-8",
            )
            (change / "review-report.md").write_text(
                markdown_with_context("Review", {"source_skill": "testspec-review", **base}),
                encoding="utf-8",
            )

            self.assertEqual(self.module.validate(change, "review", 2), [])

    def test_rejects_missing_revision_in_points(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            change = Path(tmp)
            revision = {
                "version": 2,
                "summary": "synthetic revision",
                "updated_by_skill": "testspec-update",
            }
            base = {
                "blocking_open_questions": [],
                "dynamic_followups": [],
                "material_quality": "high",
                "stale_downstream_artifacts": [],
            }
            (change / "specs").mkdir()
            (change / "requirements.md").write_text(
                markdown_with_context(
                    "Requirements",
                    {"source_skill": "testspec-update", "source_revision": revision, **base},
                ),
                encoding="utf-8",
            )
            (change / "requirements-analysis.md").write_text(
                markdown_with_context(
                    "Analysis",
                    {"source_skill": "testspec-analysis", "source_revision": revision, **base},
                ),
                encoding="utf-8",
            )
            (change / "specs/testpoints.md").write_text(
                markdown_with_context("Points", {"source_skill": "testspec-points", **base}),
                encoding="utf-8",
            )

            errors = self.module.validate(change, "points", 2)
            self.assertTrue(any("source_revision" in error for error in errors))


class TestEvalDefinitions(unittest.TestCase):
    def test_all_eval_files_are_synthetic_and_deterministic(self) -> None:
        result = subprocess.run(
            [sys.executable, str(EVAL_SCRIPT)],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_rejects_absolute_home_paths_in_eval_content(self) -> None:
        module = load_eval_module()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "evals.json"
            path.write_text(json.dumps({
                "skill_name": "synthetic",
                "fixture_policy": {
                    "origin": "synthetic",
                    "contains_proprietary_data": False,
                },
                "evals": [{
                    "id": 1,
                    "prompt": "Inspect the fixture.",
                    "files": [{
                        "path": "fixtures/input.txt",
                        "content": "/Users/sample/private-source.txt",
                    }],
                    "assertions": [
                        {"text": "a", "check": "qualitative"},
                        {"text": "b", "check": "qualitative"},
                        {"text": "c", "check": "programmatic", "script": "echo PASS"},
                    ],
                }],
            }), encoding="utf-8")

            errors = module.validate_eval_file(path)
            self.assertTrue(any("absolute user-home path" in error for error in errors))

    def test_rejects_private_identifiers_in_eval_content(self) -> None:
        module = load_eval_module()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "evals.json"
            path.write_text(json.dumps({
                "skill_name": "synthetic",
                "fixture_policy": {
                    "origin": "synthetic",
                    "contains_proprietary_data": False,
                },
                "evals": [{
                    "id": 1,
                    "prompt": "Inspect owner@corp.example and 10.1.2.3.",
                    "files": [{"path": "fixtures/input.txt", "content": "synthetic"}],
                    "assertions": [
                        {"text": "a", "check": "qualitative"},
                        {"text": "b", "check": "qualitative"},
                        {"text": "c", "check": "programmatic", "script": "echo PASS"},
                    ],
                }],
            }), encoding="utf-8")

            errors = module.validate_eval_file(path)
            self.assertTrue(any("email address" in error for error in errors))
            self.assertTrue(any("IPv4 address" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
