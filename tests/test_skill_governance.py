from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SkillRepositoryValidationTests(unittest.TestCase):
    def test_repository_skill_governance_is_complete(self):
        module = _load(
            "validate_skill_repository",
            ROOT / "scripts" / "validate_skill_repository.py",
        )
        self.assertEqual(module.validate(), [])


class EvalComparisonTests(unittest.TestCase):
    def setUp(self):
        self.module = _load(
            "compare_eval_runs",
            ROOT / "scripts" / "compare_eval_runs.py",
        )

    @staticmethod
    def _run(passed: list[bool]) -> dict:
        return {
            "schema_version": 1,
            "eval_set_sha256": "a" * 64,
            "cases": [
                {
                    "id": "synthetic:1",
                    "assertions": [
                        {"id": f"A{index}", "passed": value}
                        for index, value in enumerate(passed, start=1)
                    ],
                }
            ],
        }

    def test_comparison_accepts_improvement_with_skill_lift(self):
        result = self.module.compare(
            self._run([True, False, False]),
            self._run([True, True, True]),
            self._run([False, False, False]),
        )
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["improvements"], ["synthetic:1/A2", "synthetic:1/A3"])

    def test_comparison_rejects_regression_and_weak_control(self):
        result = self.module.compare(
            self._run([True, True, True]),
            self._run([True, False, True]),
            self._run([True, True, True]),
        )
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["regressions"], ["synthetic:1/A2"])
        self.assertEqual(result["weak_cases"], ["synthetic:1"])
        self.assertEqual(result["no_lift_cases"], ["synthetic:1"])

    def test_comparison_requires_same_prompt_and_assertion_set(self):
        candidate = self._run([True])
        candidate["eval_set_sha256"] = "b" * 64
        with self.assertRaises(self.module.EvalComparisonError):
            self.module.compare(self._run([True]), candidate)


if __name__ == "__main__":
    unittest.main()
