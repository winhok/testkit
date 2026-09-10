"""Synthetic same-revision repair and downstream invalidation regressions."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from review_repairs import sha256
from validate_context_chain import STAGES, load_context, validate


class RepairTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.base = {"context_schema_version": 2, "source_revision": {"version": 1},
                     "questions": [], "strategy_requirement": {"status": "skipped", "reasons": ["synthetic"]},
                     "material_quality": "high", "stale_downstream_artifacts": []}
        self.write("requirements.md", {**self.base, "source_skill": "testspec-update"})
        for stage, (path, skill) in STAGES.items():
            self.write(path, {**self.base, "source_skill": skill})

    def write(self, name, context, body="# Synthetic\n"):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"_context": context, "testcases": []}) if path.suffix == ".json"
                        else body + "<!-- testspec-context\n" + json.dumps(context) + "\n-->\n")
        return path

    def repair(self, stage="points", **finding_overrides):
        field = "changed_tp_ids" if stage == "points" else "changed_requirement_refs"
        entity = "TP_AUTH_LOGIN_001" if stage == "points" else "REQ-001"
        finding = {"issue_id": "RV-S1-001", "status": "open", "target_stage": stage,
                   "severity": "S1", "scope": [entity], "action": "Correct synthetic coverage"}
        finding.update(finding_overrides)
        review = {**self.base, "source_skill": "testspec-review", "feedback_for_" + stage: [finding]}
        snapshot = self.write("artifacts/reviews/prior.md", review)
        path, skill = STAGES[stage]
        context = load_context(self.root / path)
        context["review_repairs"] = [{"issue_id": "RV-S1-001", "target_stage": stage,
                                      "source_review": {"path": "artifacts/reviews/prior.md", "sha256": sha256(snapshot)},
                                      field: [entity], "summary": "Correct synthetic coverage"}]
        upstream = "requirements.md" if stage == "analysis" else "requirements-analysis.md"
        context["upstream_sha256"] = sha256(self.root / upstream)
        self.write(path, context)

    def bind(self, stage, upstream):
        path = STAGES[stage][0]
        context = load_context(self.root / path)
        context["upstream_sha256"] = sha256(self.root / upstream)
        if stage == "review":
            prior = load_context(self.root / "artifacts/reviews/prior.md")
            for route in ("analysis", "points", "generate"):
                context["feedback_for_" + route] = prior.get("feedback_for_" + route, [])
                for finding in context["feedback_for_" + route]:
                    finding.update(status="resolved", resolution="synthetic changed artifact verified")
            context["review_gate"] = {"status": "pass", "s1_unresolved_count": 0, "s1_issue_ids": []}
        self.write(path, context)

    def test_old_chain_remains_compatible_and_skipped_plan_is_ignored(self):
        self.write("strategy.md", {"source_revision": {"version": 0}})
        self.assertEqual(validate(self.root, "review", None), [])

    def test_points_repair_blocks_same_revision_cases_until_rebuilt(self):
        self.repair()
        self.assertEqual(validate(self.root, "points", None), [])
        self.assertTrue(any("generate: upstream_sha256" in e for e in validate(self.root, "generate", None)))
        self.bind("generate", "specs/testpoints.md")
        self.assertEqual(validate(self.root, "generate", None), [])
        self.assertTrue(validate(self.root, "review", None))
        self.bind("review", "artifacts/testcases.json")
        self.assertEqual(validate(self.root, "review", None), [])
        path = self.root / "specs/testpoints.md"
        path.write_text(path.read_text().replace("# Synthetic", "# Repaired again"))
        self.assertTrue(validate(self.root, "review", None))

    def test_analysis_repair_requires_points_binding(self):
        self.repair("analysis")
        self.assertEqual(validate(self.root, "analysis", None), [])
        self.assertTrue(validate(self.root, "points", None))
        self.bind("points", "requirements-analysis.md")
        self.assertEqual(validate(self.root, "points", None), [])

    def test_required_strategy_is_in_repair_chain(self):
        for name in ["requirements.md", *(v[0] for v in STAGES.values())]:
            context = load_context(self.root / name)
            context["strategy_requirement"] = {"status": "required", "reasons": ["synthetic"]}
            self.write(name, context)
        self.repair("analysis")
        self.assertTrue(any("plan: upstream_sha256" in e for e in validate(self.root, "points", None)))
        self.bind("plan", "requirements-analysis.md")
        self.bind("points", "strategy.md")
        self.assertEqual(validate(self.root, "points", None), [])

    def test_closed_or_wrong_stage_finding_rejected(self):
        for changes in ({"status": "resolved"}, {"status": "accepted"}, {"target_stage": "generate"}, {"scope": ["TP_OTHER"]}):
            with self.subTest(changes=changes):
                self.repair(**changes)
                self.assertTrue(validate(self.root, "points", None))

    def test_snapshot_tamper_and_escape_rejected(self):
        self.repair()
        snapshot = self.root / "artifacts/reviews/prior.md"
        snapshot.write_text(snapshot.read_text() + "tampered")
        self.assertTrue(validate(self.root, "points", None))
        self.repair()
        context = load_context(self.root / STAGES["points"][0])
        context["review_repairs"][0]["source_review"]["path"] = "../../outside.md"
        self.write(STAGES["points"][0], context)
        self.assertTrue(validate(self.root, "points", None))

    def test_duplicate_empty_and_stale_receipts_rejected(self):
        self.repair()
        context = load_context(self.root / STAGES["points"][0])
        for receipts in ([], [context["review_repairs"][0]] * 2, [None]):
            self.write(STAGES["points"][0], {**context, "review_repairs": receipts})
            self.assertTrue(validate(self.root, "points", None))
        context["source_revision"] = {"version": 2}
        self.write(STAGES["points"][0], context)
        self.assertTrue(validate(self.root, "points", None))

    def test_global_new_entity_allowed(self):
        self.repair(scope=["GLOBAL:missing-auth-coverage"])
        self.assertEqual(validate(self.root, "points", None), [])

    def test_review_cannot_drop_issue_or_claim_pass_with_open_s1(self):
        self.repair()
        self.bind("generate", "specs/testpoints.md")
        self.bind("review", "artifacts/testcases.json")
        path = STAGES["review"][0]
        context = load_context(self.root / path)
        finding = context["feedback_for_points"][0]
        context["feedback_for_points"] = []
        self.write(path, context)
        self.assertTrue(any("retained" in e for e in validate(self.root, "review", None)))
        finding["status"] = "open"
        context["feedback_for_points"] = [finding]
        self.write(path, context)
        self.assertTrue(any("review_gate" in e for e in validate(self.root, "review", None)))
        context["review_gate"] = {"status": "blocked", "s1_unresolved_count": 1, "s1_issue_ids": ["RV-S1-001"]}
        self.write(path, context)
        self.assertEqual(validate(self.root, "review", None), [])

    def test_legacy_generate_receipt_remains_readable(self):
        path = STAGES["generate"][0]
        context = load_context(self.root / path)
        context["review_repairs"] = [{"issue_id": "RV-S1-001", "changed_case_ids": ["CASE-001"], "summary": "legacy repair"}]
        self.write(path, context)
        self.assertEqual(validate(self.root, "review", None), [])

    def test_old_review_schema_cannot_authorize_new_repair(self):
        self.repair()
        snapshot = self.root / "artifacts/reviews/prior.md"
        review = load_context(snapshot)
        review["context_schema_version"] = 1
        self.write("artifacts/reviews/prior.md", review)
        path = STAGES["points"][0]
        context = load_context(self.root / path)
        context["review_repairs"][0]["source_review"]["sha256"] = sha256(snapshot)
        self.write(path, context)
        self.assertTrue(any("schema v2" in e for e in validate(self.root, "points", None)))


if __name__ == "__main__":
    unittest.main()
