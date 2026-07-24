from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "skills/testspec-audit/scripts/audit_testlib.py"
REBUILD = REPO_ROOT / "skills/_testspec-shared/scripts/rebuild_testlib_index.py"


def write_feature(path: Path, cases: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "schema_version": 2,
        "module": "通知",
        "module_key": "NOTICE",
        "feature": "订阅",
        "feature_key": "SUB",
        "last_updated": "2026-07-24",
        "case_count": len(cases),
        "related_features": [],
        "cases": cases,
    }, ensure_ascii=False), encoding="utf-8")


def synthetic_case(case_id: str, title: str) -> dict:
    return {
        "id": case_id,
        "title": title,
        "priority": "P1",
        "type": "正向",
        "status": "active",
        "feature": "通知",
        "preconditions": "用户已登录",
        "steps": "1、开启邮件提醒",
        "expected_result": "1、状态显示为已开启",
        "tp_refs": ["TP_NOTICE_SUB_001"],
        "source_change": "synthetic-notification",
        "created_at": "2026-07-24",
        "updated_at": "2026-07-24",
        "origin": {"kind": "testspec-native"},
        "trust": {"status": "verified"},
    }


def rebuild(testlib: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(REBUILD),
            "--testlib",
            str(testlib),
            "--date",
            "2026-07-24",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode:
        raise AssertionError(result.stdout + result.stderr)


def snapshot(testlib: Path) -> dict[str, bytes]:
    return {
        path.relative_to(testlib).as_posix(): path.read_bytes()
        for path in sorted(testlib.rglob("*"))
        if path.is_file()
    }


class TestAuditTestlib(unittest.TestCase):
    def test_reports_duplicates_and_unverified_legacy_without_mutating(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            testlib = Path(tmp) / "testlib"
            first = synthetic_case("CASE-1", "通知_订阅_开启邮件提醒")
            second = synthetic_case("CASE-2", "通知 订阅 开启邮件提醒")
            second["origin"] = {"kind": "legacy-import"}
            second["trust"] = {"status": "unverified"}
            feature = testlib / "modules/notice/subscription.json"
            write_feature(feature, [first, second])
            rebuild(testlib)
            before = snapshot(testlib)

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--testlib", str(testlib)],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=30,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            types = {item["type"] for item in report["findings"]}
            self.assertEqual(report["health"], "needs-review")
            self.assertIn("DUPLICATE_TITLE", types)
            self.assertIn("DUPLICATE_BODY", types)
            self.assertIn("UNVERIFIED_LEGACY_ACTIVE", types)
            provenance_findings = [
                item
                for item in report["findings"]
                if item["type"] == "UNVERIFIED_LEGACY_ACTIVE"
            ]
            self.assertEqual(len(provenance_findings), 1)
            self.assertEqual(report["summary"]["lifecycle_candidates"], 2)
            self.assertGreater(
                report["summary"]["recommended_findings"],
                report["summary"]["lifecycle_candidates"],
            )
            self.assertFalse(report["mutation_performed"])
            self.assertEqual(report["structural_health"], "clean")
            self.assertEqual(snapshot(testlib), before)

    def test_clean_verified_library_reports_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            testlib = Path(tmp) / "testlib"
            write_feature(
                testlib / "modules/notice/subscription.json",
                [synthetic_case("CASE-1", "通知_订阅_开启邮件提醒")],
            )
            rebuild(testlib)

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--testlib", str(testlib)],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=30,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["health"], "clean")
            self.assertEqual(report["structural_health"], "clean")
            self.assertEqual(report["semantic_health"], "clean")
            self.assertEqual(report["summary"]["warnings"], 0)

    def test_common_title_separators_do_not_create_false_module_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            testlib = Path(tmp) / "testlib"
            write_feature(
                testlib / "modules/notice/subscription.json",
                [synthetic_case("CASE-1", "通知 订阅 开启邮件提醒")],
            )
            rebuild(testlib)

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--testlib", str(testlib)],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=30,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertNotIn(
                "FEATURE_MISMATCH",
                {item["type"] for item in report["findings"]},
            )

    def test_missing_index_and_config_are_structurally_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            testlib = Path(tmp) / "testlib"
            write_feature(
                testlib / "modules/notice/subscription.json",
                [synthetic_case("CASE-1", "通知_订阅_开启邮件提醒")],
            )

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--testlib", str(testlib)],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=30,
            )

            self.assertNotEqual(result.returncode, 0)
            report = json.loads(result.stdout)
            self.assertEqual(report["health"], "structurally-invalid")
            self.assertEqual(report["structural_health"], "invalid")
            issue_types = {item["type"] for item in report["structural"]["issues"]}
            self.assertIn("MISSING_INDEX", issue_types)
            self.assertIn("MISSING_CONFIG", issue_types)

    def test_cross_file_duplicate_id_is_counted_once_in_combined_findings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            testlib = Path(tmp) / "testlib"
            write_feature(
                testlib / "modules/notice/subscription.json",
                [synthetic_case("CASE-1", "通知_订阅_开启邮件提醒")],
            )
            second = synthetic_case("CASE-1", "通知_渠道_开启站内提醒")
            write_feature(testlib / "modules/notice/channel.json", [second])
            rebuild(testlib)

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--testlib", str(testlib)],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=30,
            )

            self.assertNotEqual(result.returncode, 0)
            report = json.loads(result.stdout)
            duplicate_findings = [
                item
                for item in report["findings"]
                if item["type"] == "DUPLICATE_CASE_ID"
            ]
            self.assertEqual(len(duplicate_findings), 1)
            self.assertEqual(duplicate_findings[0]["severity"], "error")

    def test_refuses_to_overwrite_existing_report_without_explicit_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            testlib = root / "testlib"
            report_path = root / "audit.json"
            write_feature(
                testlib / "modules/notice/subscription.json",
                [synthetic_case("CASE-1", "通知_订阅_开启邮件提醒")],
            )
            rebuild(testlib)

            first = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--testlib",
                    str(testlib),
                    "--output",
                    str(report_path),
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=30,
            )
            second = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--testlib",
                    str(testlib),
                    "--output",
                    str(report_path),
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=30,
            )

            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertNotEqual(second.returncode, 0)
            self.assertIn("refusing to overwrite", second.stderr)


if __name__ == "__main__":
    unittest.main()
