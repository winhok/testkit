from __future__ import annotations

import os
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SKILL_ROOT.parents[1]


class SkillContractTests(unittest.TestCase):
    def test_only_one_public_api_automation_skill_remains(self):
        public_entries = sorted(
            path.parent.name
            for path in (REPO_ROOT / "skills").glob("api-test-automation*/SKILL.md")
        )
        self.assertEqual(public_entries, ["api-test-automation"])

    def test_referenced_resources_exist_and_scripts_are_executable(self):
        for relative in (
            "references/source-formats.md",
            "references/execution.md",
            "references/contracts.md",
            "references/community-practices.md",
            "scripts/import_api.py",
            "scripts/run_api.py",
            "scripts/run_workflows.py",
            "scripts/run_automation.py",
            "scripts/migrate_legacy_cases.py",
            "scripts/workflow_engine.py",
            "scripts/workflow_reports.py",
            "scripts/legacy_case_adapter.py",
            "scripts/source_adapters.py",
            "scripts/code_source_adapter.py",
            "agents/openai.yaml",
            "evals/evals.json",
            "evals/live-evals.json",
            "evals/run_live_eval.py",
        ):
            path = SKILL_ROOT / relative
            self.assertTrue(path.is_file(), f"missing skill resource: {path}")
        for name in (
            "import_api.py",
            "run_api.py",
            "run_workflows.py",
            "run_automation.py",
            "migrate_legacy_cases.py",
            "source_adapters.py",
            "code_source_adapter.py",
        ):
            self.assertTrue(
                os.access(SKILL_ROOT / "scripts" / name, os.X_OK),
                f"script is not executable: {name}",
            )
        self.assertTrue(
            os.access(SKILL_ROOT / "evals" / "run_live_eval.py", os.X_OK),
            "live eval runner is not executable",
        )


if __name__ == "__main__":
    unittest.main()
