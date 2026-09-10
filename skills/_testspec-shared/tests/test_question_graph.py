import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
SPEC = importlib.util.spec_from_file_location(
    "validate_question_graph", SCRIPT_DIR / "validate_question_graph.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def question(
    question_id: str,
    *,
    kind: str = "decision",
    status: str = "open",
    depends_on: list[str] | None = None,
    blocks_stages: list[str] | None = None,
) -> dict:
    resolution = None
    if status == "resolved":
        resolution = {
            "outcome": "accepted" if kind == "decision" else "verified",
            "value": "synthetic resolution",
            "source_ref": "requirements.md#synthetic",
        }
    return {
        "id": question_id,
        "kind": kind,
        "status": status,
        "question": f"Synthetic question {question_id}?",
        "depends_on": depends_on or [],
        "blocks_stages": blocks_stages or [],
        "recommendation": {"value": "Synthetic answer", "status": "proposed"},
        "resolution": resolution,
    }


class QuestionGraphTests(unittest.TestCase):
    def test_frontier_waits_for_resolved_dependencies(self):
        context = {
            "context_schema_version": 2,
            "questions": [
                question("Q-001", kind="fact", status="resolved"),
                question("Q-002", depends_on=["Q-001"]),
                question("Q-003", depends_on=["Q-002"]),
            ],
        }
        self.assertEqual(MODULE.validate_context(context), [])
        self.assertEqual(MODULE.frontier(context), ["Q-002"])

    def test_cycle_is_rejected(self):
        context = {
            "context_schema_version": 2,
            "questions": [
                question("Q-001", depends_on=["Q-002"]),
                question("Q-002", depends_on=["Q-001"]),
            ],
        }
        errors = MODULE.validate_context(context)
        self.assertTrue(any("cycle" in error for error in errors), errors)

    def test_hidden_blocker_blocks_target_stage(self):
        context = {
            "context_schema_version": 2,
            "questions": [
                question("Q-001", kind="fact"),
                question(
                    "Q-002",
                    depends_on=["Q-001"],
                    blocks_stages=["plan"],
                ),
            ],
        }
        errors = MODULE.validate_context(context, target_stage="plan")
        self.assertTrue(any("blocked by unresolved question Q-002" in item for item in errors))
        self.assertTrue(any("hidden blocker Q-002" in item for item in errors))

    def test_recommendation_cannot_be_accepted_inline(self):
        item = question("Q-001")
        item["recommendation"]["status"] = "accepted"
        errors = MODULE.validate_context(
            {"context_schema_version": 2, "questions": [item]}
        )
        self.assertTrue(any("must be 'proposed'" in error for error in errors), errors)

    def test_required_question_fields_cannot_be_omitted(self):
        item = question("Q-001")
        item.pop("recommendation")
        errors = MODULE.validate_context(
            {"context_schema_version": 2, "questions": [item]}
        )
        self.assertTrue(any("missing required fields: recommendation" in error for error in errors))


class MigrationTests(unittest.TestCase):
    def test_migration_removes_compatibility_arrays_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            change_dir = Path(temporary)
            context = {
                "source_skill": "testspec-update",
                "source_revision": {"version": 3},
                "questions": [
                    {
                        "id": "Q-001",
                        "status": "resolved",
                        "blocking": False,
                        "question": "Which synthetic boundary applies?",
                        "source": "product-answer",
                        "resolution": "Use the actual boundary.",
                    }
                ],
                "blocking_open_questions": ["Who can approve synthetic exports?"],
                "dynamic_followups": ["Verify the synthetic runtime configuration."],
                "material_quality": "high",
                "stale_downstream_artifacts": [],
            }
            requirements = change_dir / "requirements.md"
            requirements.write_text(
                "# Requirements\n\n<!-- testspec-context\n"
                + json.dumps(context, ensure_ascii=False)
                + "\n-->\n",
                encoding="utf-8",
            )
            question_map = change_dir / "question-map.json"
            question_map.write_text(
                json.dumps(
                    {
                        "Q-001": {"kind": "decision"},
                    }
                ),
                encoding="utf-8",
            )
            script = SCRIPT_DIR / "migrate_change_context.py"
            blocked = subprocess.run(
                [sys.executable, str(script), "--change-dir", str(change_dir), "--write"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(blocked.returncode, 0)
            self.assertIn("classification review required", blocked.stdout)
            first = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--change-dir",
                    str(change_dir),
                    "--question-map",
                    str(question_map),
                    "--write",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            migrated = MODULE.load_context(requirements)
            self.assertEqual(migrated["context_schema_version"], 2)
            self.assertNotIn("blocking_open_questions", migrated)
            self.assertNotIn("dynamic_followups", migrated)
            self.assertEqual(len(migrated["questions"]), 1)
            self.assertEqual(migrated["strategy_requirement"]["status"], "skipped")
            self.assertEqual(MODULE.validate_context(migrated), [])
            self.assertEqual(requirements.stat().st_mode & 0o777, 0o644)

            second = subprocess.run(
                [sys.executable, str(script), "--change-dir", str(change_dir), "--write"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertIn("already uses", second.stdout)

    def test_json_migration_preserves_testcase_payload_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            change_dir = Path(temporary)
            artifacts = change_dir / "artifacts"
            artifacts.mkdir()
            context = {
                "source_skill": "testspec-update",
                "source_revision": {"version": 1},
                "questions": [],
                "blocking_open_questions": [],
                "dynamic_followups": [],
                "material_quality": "high",
                "stale_downstream_artifacts": [],
            }
            requirements = change_dir / "requirements.md"
            requirements.write_text(
                "# Requirements\n\n<!-- testspec-context\n"
                + json.dumps(context)
                + "\n-->\n",
                encoding="utf-8",
            )
            sentinel = '[{"id":"SYN-1", "steps":"keep   spacing"}]'
            cases = artifacts / "testcases.json"
            cases.write_text(
                '{\n  "schema_version": 2,\n  "_context": '
                + json.dumps(context)
                + ',\n  "testcases": '
                + sentinel
                + "\n}\n",
                encoding="utf-8",
            )
            script = SCRIPT_DIR / "migrate_change_context.py"
            result = subprocess.run(
                [sys.executable, str(script), "--change-dir", str(change_dir), "--write"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('"testcases": ' + sentinel, cases.read_text(encoding="utf-8"))

    def test_canonical_registry_wins_over_compatibility_wording(self):
        warnings: list[str] = []
        migration_spec = importlib.util.spec_from_file_location(
            "migrate_change_context", SCRIPT_DIR / "migrate_change_context.py"
        )
        migration = importlib.util.module_from_spec(migration_spec)
        assert migration_spec.loader is not None
        sys.path.insert(0, str(SCRIPT_DIR))
        migration_spec.loader.exec_module(migration)
        migrated = migration._legacy_questions(
            [
                {
                    "questions": [
                        {
                            "id": "Q-001",
                            "status": "open",
                            "blocking": False,
                            "question": "Verify the synthetic runtime.",
                            "resolution": "",
                        }
                    ],
                    "dynamic_followups": ["Check runtime availability."],
                },
                {"dynamic_followups": ["Inspect runtime reachability."]},
            ],
            {"Q-001": {"kind": "fact"}},
            warnings,
        )
        self.assertEqual([item["id"] for item in migrated], ["Q-001"])
        self.assertEqual(warnings, [])

    def test_compatibility_arrays_seed_registry_when_questions_are_absent(self):
        migration_spec = importlib.util.spec_from_file_location(
            "migrate_change_context_arrays", SCRIPT_DIR / "migrate_change_context.py"
        )
        migration = importlib.util.module_from_spec(migration_spec)
        assert migration_spec.loader is not None
        sys.path.insert(0, str(SCRIPT_DIR))
        migration_spec.loader.exec_module(migration)
        migrated = migration._legacy_questions(
            [
                {
                    "blocking_open_questions": ["Choose the synthetic policy."],
                    "dynamic_followups": ["Verify the synthetic runtime."],
                }
            ],
            {
                "Q-001": {"kind": "decision"},
                "Q-002": {"kind": "fact"},
            },
        )
        self.assertEqual([item["kind"] for item in migrated], ["decision", "fact"])


if __name__ == "__main__":
    unittest.main()
