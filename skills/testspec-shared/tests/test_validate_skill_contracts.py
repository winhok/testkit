import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "skills" / "testspec-shared" / "scripts" / "validate_skill_contracts.py"


def _venv_python() -> str:
    return sys.executable


class TestValidateSkillContracts(unittest.TestCase):
    def test_current_repo_contracts_are_valid(self):
        result = subprocess.run(
            [_venv_python(), str(SCRIPT_PATH)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("OK: skill contracts validated", result.stdout)

    def test_missing_analysis_mode_fails_validation(self):
        with tempfile.TemporaryDirectory() as td:
            repo = self._create_minimal_repo(Path(td))
            analysis_modes = repo / "skills" / "testspec-shared" / "references" / "analysis-modes.md"
            content = analysis_modes.read_text(encoding="utf-8")
            analysis_modes.write_text(content.replace("## logic\n", "## logic-removed\n", 1), encoding="utf-8")

            result = self._run_temp_validator(repo)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("analysis-modes 缺少模式：logic", result.stderr)

    def test_missing_shared_reference_fails_validation(self):
        with tempfile.TemporaryDirectory() as td:
            repo = self._create_minimal_repo(Path(td))
            target = repo / "skills" / "testspec-shared" / "references" / "test-type-strategies.md"
            target.unlink()

            result = self._run_temp_validator(repo)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("缺少文件", result.stderr)

    def test_missing_compatibility_clause_fails_validation(self):
        with tempfile.TemporaryDirectory() as td:
            repo = self._create_minimal_repo(Path(td))
            output_contracts = repo / "skills" / "testspec-shared" / "references" / "output-contracts.md"
            content = output_contracts.read_text(encoding="utf-8")
            output_contracts.write_text(content.replace("不得擅自改动历史 schema", "允许调整 schema", 1), encoding="utf-8")

            result = self._run_temp_validator(repo)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("历史 schema 兼容性", result.stderr)

    def test_bare_shared_reference_fails_validation(self):
        with tempfile.TemporaryDirectory() as td:
            repo = self._create_minimal_repo(Path(td))
            review_skill = repo / "skills" / "testspec-review" / "SKILL.md"
            content = review_skill.read_text(encoding="utf-8")
            review_skill.write_text(
                content.replace("`../testspec-shared/references/context-protocol.md`", "`context-protocol.md`", 1),
                encoding="utf-8",
            )

            result = self._run_temp_validator(repo)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("裸 shared 引用", result.stderr)

    def test_missing_review_template_depth_fields_fail_validation(self):
        with tempfile.TemporaryDirectory() as td:
            repo = self._create_minimal_repo(Path(td))
            template = repo / "skills" / "testspec-review" / "review-report-template.md"
            content = template.read_text(encoding="utf-8")
            template.write_text(content.replace("**深度触发原因**", "**触发原因**", 1), encoding="utf-8")

            result = self._run_temp_validator(repo)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("review-report-template 缺少深度触发原因字段", result.stderr)

    def test_missing_review_dimension_methodology_fails_validation(self):
        with tempfile.TemporaryDirectory() as td:
            repo = self._create_minimal_repo(Path(td))
            dimensions = repo / "skills" / "testspec-review" / "references" / "review-dimensions.md"
            content = dimensions.read_text(encoding="utf-8")
            dimensions.write_text(content.replace("### Oracle 审查维度\n", "### Oracle 说明\n", 1), encoding="utf-8")

            result = self._run_temp_validator(repo)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("review-dimensions 缺少 H7 Oracle 审查维度", result.stderr)

    def _run_temp_validator(self, repo: Path) -> subprocess.CompletedProcess[str]:
        script = repo / "skills" / "testspec-shared" / "scripts" / "validate_skill_contracts.py"
        return subprocess.run(
            [_venv_python(), str(script)],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def _create_minimal_repo(self, repo: Path) -> Path:
        paths_to_copy = [
            "skills/testspec-new/SKILL.md",
            "skills/testspec-analysis/SKILL.md",
            "skills/testspec-points/SKILL.md",
            "skills/testspec-generate/SKILL.md",
            "skills/testspec-review/SKILL.md",
            "skills/testspec-review/review-report-template.md",
            "skills/testspec-review/references/review-dimensions.md",
            "skills/testspec-publish/SKILL.md",
            "skills/testspec-shared/references/common.md",
            "skills/testspec-shared/references/thinking-protocol.md",
            "skills/testspec-shared/references/reflection-protocol.md",
            "skills/testspec-shared/references/context-protocol.md",
            "skills/testspec-shared/references/analysis-modes.md",
            "skills/testspec-shared/references/output-contracts.md",
            "skills/testspec-shared/references/naming-contract.md",
            "skills/testspec-shared/references/testlib-contracts.md",
            "skills/testspec-shared/references/test-type-strategies.md",
            "skills/testspec-shared/references/artifact-templates.md",
            "skills/testspec-shared/evals/evals.json",
            "skills/testspec-shared/scripts/validate_skill_contracts.py",
            "skills/testspec-shared/scripts/validate_testlib.py",
            "skills/testspec-shared/scripts/rebuild_testlib_index.py",
            "skills/testspec-shared/tests/test_testlib_tools.py",
        ]
        for rel in paths_to_copy:
            src = REPO_ROOT / rel
            dst = repo / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        return repo


if __name__ == "__main__":
    unittest.main()
