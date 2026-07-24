from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "skills/testspec-import/scripts/import_legacy_cases.py"
VALIDATOR = REPO_ROOT / "skills/testspec-import/scripts/validate_reconciliation.py"


class TestLegacyImport(unittest.TestCase):
    def test_csv_import_is_quarantined_and_does_not_leak_input_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "confidential-source.csv"
            output = root / "staging.json"
            with source.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["编号", "用例标题", "操作步骤", "测试预期内容", "模块"],
                )
                writer.writeheader()
                writer.writerow({
                    "编号": "OLD-1",
                    "用例标题": "通知_订阅_开启邮件提醒",
                    "操作步骤": "1、开启邮件提醒",
                    "测试预期内容": "1、状态显示为已开启",
                    "模块": "通知",
                })

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--input",
                    str(source),
                    "--output",
                    str(output),
                    "--source-label",
                    "legacy-source",
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=30,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            text = output.read_text(encoding="utf-8")
            data = json.loads(text)
            reconciliation = json.loads(
                (root / "reconciliation.json").read_text(encoding="utf-8")
            )
            self.assertNotIn(str(source), text)
            self.assertNotIn(source.name, text)
            self.assertEqual(data["_context"]["publish_eligibility"], "blocked")
            self.assertEqual(data["testcases"][0]["origin"]["kind"], "legacy-import")
            self.assertEqual(data["testcases"][0]["trust"]["status"], "unverified")
            self.assertEqual(data["testcases"][0]["origin"]["source_row"], 2)
            self.assertEqual(data["testcases"][0]["tp_refs"], [])
            self.assertEqual(reconciliation["summary"]["unresolved"], 1)
            self.assertEqual(reconciliation["records"][0]["legacy_case_id"], "OLD-1")

    def test_json_import_reports_duplicate_candidates_without_auto_merging(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "legacy.json"
            output = root / "staging.json"
            source.write_text(
                json.dumps({
                    "cases": [
                        {
                            "id": "OLD-1",
                            "title": "导出_文件_生成文本文件",
                            "steps": "1、选择文本格式",
                            "expected_result": "1、生成文件",
                        },
                        {
                            "id": "OLD-2",
                            "title": "导出 文件 生成文本文件",
                            "steps": "1、选择文本格式",
                            "expected_result": "1、生成文件",
                        },
                    ]
                }, ensure_ascii=False),
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--input", str(source), "--output", str(output)],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=30,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(output.read_text(encoding="utf-8"))
            warning_types = {item["type"] for item in data["warnings"]}
            self.assertEqual(len(data["testcases"]), 2)
            self.assertIn("duplicate_title_candidate", warning_types)
            self.assertIn("duplicate_body_candidate", warning_types)
            self.assertTrue(all(case["reconciliation"]["status"] == "unresolved" for case in data["testcases"]))

    def test_duplicate_source_ids_get_unique_staging_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "legacy.json"
            output = root / "staging.json"
            source.write_text(
                json.dumps([
                    {
                        "id": "OLD-1",
                        "title": "通知_订阅_开启提醒",
                        "steps": "1、开启提醒",
                        "expected_result": "1、状态显示为开启",
                    },
                    {
                        "id": "OLD-1",
                        "title": "通知_订阅_关闭提醒",
                        "steps": "1、关闭提醒",
                        "expected_result": "1、状态显示为关闭",
                    },
                ], ensure_ascii=False),
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--input", str(source), "--output", str(output)],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=30,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(output.read_text(encoding="utf-8"))
            cases = data["testcases"]
            self.assertEqual([case["id"] for case in cases], ["OLD-1", "OLD-1__DUP_2"])
            self.assertEqual(cases[1]["origin"]["source_case_id"], "OLD-1")
            self.assertIn(
                "duplicate_source_id_candidate",
                {item["type"] for item in data["warnings"]},
            )
            reconciliation = json.loads(
                (root / "reconciliation.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                [record["legacy_case_id"] for record in reconciliation["records"]],
                ["OLD-1", "OLD-1__DUP_2"],
            )

    def test_xlsx_import_maps_common_headers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "legacy.xlsx"
            output = root / "staging.json"
            workbook = Workbook()
            sheet = workbook.active
            sheet.append(["用例标题", "预置条件", "操作步骤", "测试预期内容", "级别"])
            sheet.append([
                "账户_偏好_关闭每周摘要",
                "用户已登录",
                "1、关闭每周摘要",
                "1、状态显示为关闭",
                "P1",
            ])
            workbook.save(source)

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--input", str(source), "--output", str(output)],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=30,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            case = json.loads(output.read_text(encoding="utf-8"))["testcases"][0]
            self.assertEqual(case["title"], "账户_偏好_关闭每周摘要")
            self.assertEqual(case["priority"], "P1")
            self.assertEqual(case["preconditions"], "用户已登录")

    def test_refuses_to_overwrite_staging_without_explicit_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "legacy.json"
            output = root / "legacy-cases.json"
            source.write_text(
                json.dumps([{
                    "id": "OLD-1",
                    "title": "通知_订阅_开启提醒",
                    "steps": "1、开启提醒",
                    "expected_result": "1、状态显示为开启",
                }], ensure_ascii=False),
                encoding="utf-8",
            )

            first = subprocess.run(
                [sys.executable, str(SCRIPT), "--input", str(source), "--output", str(output)],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=30,
            )
            second = subprocess.run(
                [sys.executable, str(SCRIPT), "--input", str(source), "--output", str(output)],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=30,
            )

            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertNotEqual(second.returncode, 0)
            self.assertIn("refusing to overwrite", second.stderr)

    def test_reconciliation_validator_enforces_current_evidence_and_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "legacy.json"
            output = root / "legacy-cases.json"
            reconciliation_path = root / "reconciliation.json"
            source.write_text(
                json.dumps([{
                    "id": "OLD-1",
                    "title": "通知_订阅_开启提醒",
                    "steps": "1、开启提醒",
                    "expected_result": "1、状态显示为开启",
                }], ensure_ascii=False),
                encoding="utf-8",
            )
            imported = subprocess.run(
                [sys.executable, str(SCRIPT), "--input", str(source), "--output", str(output)],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(imported.returncode, 0, imported.stderr)

            pending = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATOR),
                    "--imported",
                    str(output),
                    "--reconciliation",
                    str(reconciliation_path),
                    "--ready-for-generate",
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertNotEqual(pending.returncode, 0)
            self.assertIn("unresolved record blocks generation", pending.stdout)

            reconciliation = json.loads(reconciliation_path.read_text(encoding="utf-8"))
            reconciliation["records"][0]["status"] = "keep"
            reconciliation["records"][0]["requirement_refs"] = ["REQ-001", "AC-001"]
            reconciliation["summary"]["keep"] = 1
            reconciliation["summary"]["unresolved"] = 0
            reconciliation["_context"]["status"] = "ready-for-generate"
            reconciliation_path.write_text(
                json.dumps(reconciliation, ensure_ascii=False),
                encoding="utf-8",
            )
            ready = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATOR),
                    "--imported",
                    str(output),
                    "--reconciliation",
                    str(reconciliation_path),
                    "--ready-for-generate",
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(ready.returncode, 0, ready.stdout + ready.stderr)


if __name__ == "__main__":
    unittest.main()
