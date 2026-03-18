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
            analysis_modes = repo / "skills" / "testspec-shared" / "analysis-modes.md"
            content = analysis_modes.read_text(encoding="utf-8")
            analysis_modes.write_text(content.replace("## logic\n", "## logic-removed\n", 1), encoding="utf-8")

            result = self._run_temp_validator(repo)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("analysis-modes 缺少模式：logic", result.stderr)

    def test_missing_shared_reference_fails_validation(self):
        with tempfile.TemporaryDirectory() as td:
            repo = self._create_minimal_repo(Path(td))
            target = repo / "skills" / "testspec-shared" / "test-type-strategies.md"
            target.unlink()

            result = self._run_temp_validator(repo)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("缺少文件", result.stderr)

    def test_missing_compatibility_clause_fails_validation(self):
        with tempfile.TemporaryDirectory() as td:
            repo = self._create_minimal_repo(Path(td))
            output_contracts = repo / "skills" / "testspec-shared" / "output-contracts.md"
            content = output_contracts.read_text(encoding="utf-8")
            output_contracts.write_text(content.replace("不得擅自改动历史 schema", "允许调整 schema", 1), encoding="utf-8")

            result = self._run_temp_validator(repo)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("历史 schema 兼容性", result.stderr)

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
            "skills/testspec-analysis/SKILL.md",
            "skills/testspec-generate/SKILL.md",
            "skills/testspec-shared/analysis-modes.md",
            "skills/testspec-shared/output-contracts.md",
            "skills/testspec-shared/test-type-strategies.md",
            "skills/testspec-shared/scripts/validate_skill_contracts.py",
        ]
        for rel in paths_to_copy:
            src = REPO_ROOT / rel
            dst = repo / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        return repo


if __name__ == "__main__":
    unittest.main()
