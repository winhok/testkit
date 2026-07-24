from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/detect_conflicts.py"


def load_module():
    spec = importlib.util.spec_from_file_location("detect_conflicts", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestDetectConflicts(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()

    def test_same_id_is_update_and_different_id_same_title_is_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            incoming = root / "incoming.json"
            feature = root / "testlib/modules/auth/cred.json"
            feature.parent.mkdir(parents=True)
            incoming.write_text(
                json.dumps(
                    {
                        "testcases": [
                            {
                                "id": "SYN_001",
                                "title": "登录_凭据_正确密码登录",
                                "feature": "登录",
                            },
                            {
                                "id": "SYN_099",
                                "title": "登录 - 凭据 - 正确密码登录",
                                "feature": "登录",
                            },
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            feature.write_text(
                json.dumps(
                    {
                        "cases": [
                            {
                                "id": "SYN_001",
                                "title": "登录_凭据_正确密码登录",
                                "feature": "登录",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = self.module.detect(incoming, root / "testlib")
            self.assertEqual(len(report["same_id_updates"]), 1)
            self.assertEqual(report["conflict_count"], 1)
            self.assertEqual(report["conflicts"][0]["kind"], "different_id_same_title")

    def test_same_scenario_key_is_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            incoming = root / "incoming.json"
            feature = root / "testlib/modules/import/basic.json"
            feature.parent.mkdir(parents=True)
            incoming.write_text(
                json.dumps(
                    {
                        "testcases": [
                            {
                                "id": "SYN_NEW",
                                "title": "导入_文件_导入文本",
                                "feature": "导入",
                                "scenario_key": "IMPORT|FILE|TEXT_SUCCESS",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            feature.write_text(
                json.dumps(
                    {
                        "cases": [
                            {
                                "id": "SYN_OLD",
                                "title": "文件_文本_成功导入",
                                "feature": "导入",
                                "scenario_key": "IMPORT|FILE|TEXT_SUCCESS",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = self.module.detect(incoming, root / "testlib")
            self.assertEqual(report["conflict_count"], 1)
            self.assertEqual(
                report["conflicts"][0]["kind"],
                "different_id_same_scenario_key",
            )


if __name__ == "__main__":
    unittest.main()
