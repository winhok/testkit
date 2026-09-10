"""Synthetic cross-run linkage tests; no external application is executed."""
import copy
import json
import sys
import subprocess
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_test_run as fixtures
from test_run import ContractError, digest, load, record, write_new
from verify_defect import verify


class LineageTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.RunTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.root = self.f.root
        self.phases = {}
        for phase, status in [("source", "failed"), ("red", "failed"), ("green", "passed"), ("regression", "passed")]:
            self.f.scope["run_id"] = phase
            self.f.scope["targets"][0]["build"] = "old" if phase in {"source", "red"} else "new"
            directory = self.f.frozen(phase)
            record(self.f.attempt(directory, status, signature="synthetic-bug"), self.root, directory)
            self.phases[phase] = phase
        self.defect = {"schema_version": 1, "defect_id": "BUG-001", "expected": "confirmed",
                       "failure_signature": "synthetic-bug", "conditions": "conditions.json",
                       "phases": {k: v for k, v in self.phases.items() if k != "source"},
                       "lineage": {"source": {**self.ref("source"), "check_ids": ["check"]}}}

    def ref(self, name):
        path = self.root / name / "scope.json"
        return {"run_dir": name, "run_id": load(path)["run_id"], "scope_sha256": digest(path)}

    def reaccept(self, status="passed", extra=False):
        revision = {"version": 1}
        context = {"context_schema_version": 2, "source_revision": revision}
        (self.root / "requirements.md").write_text("REQ-001 synthetic\n<!-- testspec-context\n" + json.dumps(context) + "\n-->")
        write_new(self.root / "cases.json", {"_context": context, "testcases": [{"id": "case-1"}]})
        scope = copy.deepcopy(self.f.scope)
        scope.update(run_id="reaccept", mode="acceptance", source_revision=revision, scope_basis="synthetic full scope")
        scope["sources"] += [{"id": "requirements", "kind": "requirements", "path": "requirements.md"},
                             {"id": "cases", "kind": "cases", "path": "cases.json"}]
        scope["checks"][0]["requirement_refs"] = ["REQ-001"]
        if extra:
            scope["checks"].append({**copy.deepcopy(scope["checks"][0]), "id": "unfixed"})
        directory = self.f.frozen("reaccept", scope)
        record(self.f.attempt(directory, status), self.root, directory)
        self.defect["lineage"]["reacceptance"] = self.ref("reaccept")
        return scope["targets"]

    def test_source_only_does_not_claim_reacceptance(self):
        result = verify(self.root, self.defect)
        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["lineage"]["reacceptance_status"], "not-run")
        self.assertEqual(result["lineage"]["closed_check_ids"], [])

    def test_reacceptance_pass_closes_linked_checks(self):
        targets = self.reaccept()
        result = verify(self.root, self.defect, targets)
        self.assertEqual(result["lineage"]["closed_check_ids"], ["check"])
        self.assertEqual(result["lineage"]["reacceptance_status"], "passed")

    def test_other_missing_required_check_prevents_closure(self):
        targets = self.reaccept(extra=True)
        result = verify(self.root, self.defect, targets)
        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["lineage"]["reacceptance_status"], "blocked")
        self.assertEqual(result["lineage"]["closed_check_ids"], [])

    def test_failed_reacceptance_is_separate_from_defect_status(self):
        result = verify(self.root, self.defect, self.reaccept("failed"))
        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["lineage"]["reacceptance_status"], "failed")
        self.assertEqual(result["lineage"]["closed_check_ids"], [])

    def test_current_target_change_is_stale(self):
        targets = self.reaccept()
        targets[0]["build"] = "later"
        result = verify(self.root, self.defect, targets)
        self.assertEqual(result["lineage"]["reacceptance_status"], "stale")
        self.assertEqual(result["lineage"]["closed_check_ids"], [])

    def test_missing_current_targets_rejected(self):
        self.reaccept()
        with self.assertRaises(ContractError):
            verify(self.root, self.defect)

    def test_wrong_source_identity_hash_unknown_or_duplicate_checks_rejected(self):
        for patch in ({"run_id": "wrong"}, {"scope_sha256": "0" * 64}, {"check_ids": ["missing"]},
                      {"check_ids": ["check", "check"]}, {"run_dir": "../outside"}, {"check_ids": []}):
            defect = copy.deepcopy(self.defect)
            defect["lineage"]["source"].update(patch)
            with self.subTest(patch=patch), self.assertRaises(ContractError):
                verify(self.root, defect)

    def test_passing_source_cannot_be_claimed_as_failure(self):
        self.defect["lineage"]["source"] = {**self.ref("green"), "check_ids": ["check"]}
        with self.assertRaises(ContractError):
            verify(self.root, self.defect)

    def test_reusing_phase_as_reacceptance_rejected(self):
        self.defect["lineage"]["reacceptance"] = self.ref("green")
        with self.assertRaises(ContractError):
            verify(self.root, self.defect, self.f.scope["targets"])

    def test_failed_verification_cannot_close_passing_reacceptance(self):
        targets = self.reaccept()
        self.defect["failure_signature"] = "other-bug"
        result = verify(self.root, self.defect, targets)
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["lineage"]["closed_check_ids"], [])

    def test_source_required_checks_cannot_be_dropped(self):
        scope = copy.deepcopy(load(self.root / "source/scope.json"))
        scope["run_id"] = "source-extra"
        scope["checks"].append({**copy.deepcopy(scope["checks"][0]), "id": "other"})
        directory = self.f.frozen("source-extra", scope)
        record(self.f.attempt(directory, "failed", signature="synthetic-bug"), self.root, directory)
        self.defect["lineage"]["source"] = {**self.ref("source-extra"), "check_ids": ["check"]}
        targets = self.reaccept()
        with self.assertRaisesRegex(ContractError, "cannot drop"):
            verify(self.root, self.defect, targets)

    def test_reacceptance_changed_oracle_or_demoted_check_rejected(self):
        targets = self.reaccept(extra=True)
        path = self.root / "reaccept/scope.json"
        original = load(path)
        for patch in ({"oracle": "weaker"}, {"required": False}, {"case_id": "case-2"}):
            scope = copy.deepcopy(original)
            scope["checks"][0].update(patch)
            path.write_text(json.dumps(scope))
            # Keep fixture hashes consistent to test semantics rather than integrity.
            for attempt in (path.parent / "attempts").glob("*.json"):
                value = load(attempt)
                value["scope_sha256"] = digest(path)
                attempt.write_text(json.dumps(value))
            self.defect["lineage"]["reacceptance"] = self.ref("reaccept")
            with self.subTest(patch=patch), self.assertRaises(ContractError):
                verify(self.root, self.defect, targets)

    def test_cli_reacceptance_exit_code_and_no_overwrite(self):
        targets = self.reaccept(extra=True)
        write_new(self.root / "defect.json", self.defect)
        write_new(self.root / "targets.json", targets)
        script = Path(__file__).resolve().parents[2] / "defect-verification/scripts/verify_defect.py"
        command = [sys.executable, str(script), "--root", str(self.root), "--input", str(self.root / "defect.json"),
                   "--current-targets", str(self.root / "targets.json"), "--output", str(self.root / "result.json")]
        first = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(first.returncode, 1, first.stdout + first.stderr)
        self.assertEqual(json.loads(first.stdout)["lineage"]["reacceptance_status"], "blocked")
        original = (self.root / "result.json").read_bytes()
        second = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(second.returncode, 2)
        self.assertEqual((self.root / "result.json").read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
