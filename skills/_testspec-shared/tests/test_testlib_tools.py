import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
REBUILD_SCRIPT = REPO_ROOT / "skills" / "_testspec-shared" / "scripts" / "rebuild_testlib_index.py"
VALIDATE_SCRIPT = REPO_ROOT / "skills" / "_testspec-shared" / "scripts" / "validate_testlib.py"


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _feature_doc(module: str, module_key: str, feature: str, feature_key: str, cases: list[dict], **extra) -> dict:
    doc = {
        "schema_version": 2,
        "module": module,
        "module_key": module_key,
        "feature": feature,
        "feature_key": feature_key,
        "last_updated": "2026-04-20",
        "case_count": len(cases),
        "related_features": [],
        "cases": cases,
    }
    doc.update(extra)
    return doc


def _case(case_id: str, title: str, priority: str = "P1", status: str = "active") -> dict:
    return {
        "id": case_id,
        "title": title,
        "priority": priority,
        "type": "冒烟",
        "status": status,
        "feature": title.split("_")[0],
        "steps": "1、打开页面\n2、点击确认",
        "expected_result": "1、页面显示成功状态",
        "tp_refs": ["TP_LOGIN_CRED_001"],
        "source_change": "login",
        "created_at": "2026-04-20",
        "updated_at": "2026-04-20",
    }


class TestTestlibTools(unittest.TestCase):
    def test_rebuild_writes_index_and_stats_from_feature_files(self):
        with tempfile.TemporaryDirectory() as td:
            testlib = Path(td) / "testlib"
            _write_json(
                testlib / "modules" / "login" / "cred.json",
                _feature_doc(
                    "登录",
                    "LOGIN",
                    "凭据验证",
                    "CRED",
                    [
                        _case("case-1", "登录_凭据验证_成功登录", "P1", "active"),
                        _case("case-2", "登录_凭据验证_密码错误", "P2", "deprecated"),
                    ],
                    related_features=[{"path": "register/basic", "relation": "前置依赖"}],
                ),
            )

            result = subprocess.run(
                [sys.executable, str(REBUILD_SCRIPT), "--testlib", str(testlib), "--date", "2026-04-24"],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=30,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            index = json.loads((testlib / "index.json").read_text(encoding="utf-8"))
            config = json.loads((testlib / ".testlib.json").read_text(encoding="utf-8"))

            self.assertEqual(index["last_updated"], "2026-04-24")
            self.assertEqual(index["modules"][0]["dir"], "login")
            self.assertEqual(index["modules"][0]["features"][0]["file"], "login/cred.json")
            self.assertEqual(index["modules"][0]["features"][0]["case_count"], 2)
            self.assertEqual(index["modules"][0]["features"][0]["by_priority"], {"P1": 1, "P2": 1})
            self.assertEqual(index["modules"][0]["features"][0]["by_status"], {"active": 1, "deprecated": 1})
            self.assertEqual(index["modules"][0]["features"][0]["related_features"], ["register/basic"])
            self.assertEqual(config["stats"]["total_modules"], 1)
            self.assertEqual(config["stats"]["total_features"], 1)
            self.assertEqual(config["stats"]["total_cases"], 2)

    def test_validate_passes_for_rebuilt_testlib(self):
        with tempfile.TemporaryDirectory() as td:
            testlib = Path(td) / "testlib"
            _write_json(
                testlib / "modules" / "login" / "cred.json",
                _feature_doc(
                    "登录",
                    "LOGIN",
                    "凭据验证",
                    "CRED",
                    [_case("case-1", "登录_凭据验证_成功登录")],
                ),
            )
            rebuild_result = subprocess.run(
                [sys.executable, str(REBUILD_SCRIPT), "--testlib", str(testlib), "--date", "2026-04-24"],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(rebuild_result.returncode, 0, rebuild_result.stdout + rebuild_result.stderr)

            result = subprocess.run(
                [sys.executable, str(VALIDATE_SCRIPT), "--testlib", str(testlib)],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=30,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["status"], "pass")
            self.assertEqual(report["summary"]["errors"], 0)

    def test_validate_reports_duplicate_ids_broken_refs_and_stale_summaries(self):
        with tempfile.TemporaryDirectory() as td:
            testlib = Path(td) / "testlib"
            duplicate = _case("dup-case", "登录_凭据验证_成功登录")
            _write_json(
                testlib / "modules" / "login" / "cred.json",
                _feature_doc(
                    "登录",
                    "LOGIN",
                    "凭据验证",
                    "CRED",
                    [duplicate],
                    case_count=2,
                    related_features=[{"path": "missing/feature", "relation": "业务关联"}],
                ),
            )
            _write_json(
                testlib / "modules" / "login" / "phone.json",
                _feature_doc("登录", "LOGIN", "手机号登录", "PHONE", [duplicate]),
            )
            _write_json(testlib / "index.json", {"schema_version": 1, "last_updated": "2026-04-01", "modules": []})
            _write_json(
                testlib / ".testlib.json",
                {
                    "schema_version": 1,
                    "created_at": "2026-04-01",
                    "last_updated": "2026-04-01",
                    "stats": {"total_modules": 0, "total_features": 0, "total_cases": 0},
                },
            )

            result = subprocess.run(
                [sys.executable, str(VALIDATE_SCRIPT), "--testlib", str(testlib)],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=30,
            )

            self.assertEqual(result.returncode, 1)
            report = json.loads(result.stdout)
            issue_types = {issue["type"] for issue in report["issues"]}
            self.assertIn("CASE_COUNT_MISMATCH", issue_types)
            self.assertIn("DUPLICATE_CASE_ID", issue_types)
            self.assertIn("BROKEN_RELATED_FEATURE", issue_types)
            self.assertIn("INDEX_OUT_OF_DATE", issue_types)
            self.assertIn("STATS_OUT_OF_DATE", issue_types)


if __name__ == "__main__":
    unittest.main()
