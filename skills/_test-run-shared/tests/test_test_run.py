import copy
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "defect-verification" / "scripts"))
from test_run import ContractError, digest, evaluate, freeze, load, migrate, outcome, record, write_new
from verify_defect import verify


def now():
    return datetime.now(timezone.utc).isoformat()


class RunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        write_new(self.root / "check.json", {"expected": "confirmed"})
        write_new(self.root / "conditions.json", {"role": "synthetic-customer", "state": "empty"})
        self.scope = {
            "run_id": "synthetic-run", "mode": "local",
            "sources": [{"id": "source", "kind": "local-check", "path": "check.json"},
                        {"id": "conditions", "kind": "dataset", "path": "conditions.json"}],
            "targets": [{"id": "web", "platform": "web", "build": "build-1", "environment": "test"}],
            "capabilities": [{"id": "browser", "target_id": "web", "availability": "available", "authorization": "granted", "actions": ["read"], "scope": "synthetic page", "basis": "synthetic tool", "checked_at": now()}],
            "checks": [{"id": "check", "case_id": "case-1", "source_id": "source", "requirement_refs": [], "oracle": "confirmed", "target_id": "web", "required": True, "effect": "read", "cleanup": "not-required", "depends_on": [], "capability_ids": ["browser"], "binding": {"runner": "observation", "selector": "/assertion"}}],
        }
        self.counter = 0

    def frozen(self, name="run", scope=None):
        draft = self.root / (name + "-draft.json")
        write_new(draft, scope or self.scope)
        directory = self.root / name
        freeze(draft, self.root, directory)
        return directory

    def attempt(self, directory, status="passed", check_id="check", cleanup="not-required", signature=None):
        self.counter += 1
        label = "attempt-" + str(self.counter)
        start = now()
        item = {"status": status, "actual": "synthetic value", "basis": "synthetic assertion", "method": "tool"}
        if signature:
            item["defect_signature"] = signature
        write_new(self.root / (label + "-raw.json"), {"assertion": item})
        end = now()
        scope = load(directory / "scope.json")
        draft = {"id": label, "check_id": check_id, "target": scope["targets"][0], "started_at": start,
                 "finished_at": end, "status": status, "cleanup_status": cleanup, "cleanup_basis": "synthetic cleanup observation",
                 "reason": "synthetic reason", "evidence": [{"path": label + "-raw.json", "collector": "synthetic", "collected_at": end}]}
        path = self.root / (label + "-draft.json")
        write_new(path, draft)
        return path

    def result(self, directory):
        return evaluate(self.root, directory, load(directory / "scope.json")["targets"])

    def test_pass_with_actual_evidence(self):
        directory = self.frozen()
        record(self.attempt(directory), self.root, directory)
        self.assertEqual(self.result(directory)["acceptance_status"], "passed")

    def test_missing_required_check_blocks(self):
        directory = self.frozen()
        self.assertEqual(self.result(directory)["acceptance_status"], "blocked")

    def test_partial_scope_not_shrunk_to_results(self):
        self.scope["checks"].append({**copy.deepcopy(self.scope["checks"][0]), "id": "other"})
        directory = self.frozen()
        record(self.attempt(directory), self.root, directory)
        result = self.result(directory)
        self.assertEqual(result["acceptance_status"], "blocked")
        self.assertEqual(len(result["checks"]), 2)

    def test_failed_then_passed_remains_inconclusive(self):
        directory = self.frozen()
        record(self.attempt(directory, "failed"), self.root, directory)
        record(self.attempt(directory), self.root, directory)
        self.assertEqual(self.result(directory)["acceptance_status"], "inconclusive")

    def test_evidence_tamper_rejected(self):
        directory = self.frozen()
        record(self.attempt(directory), self.root, directory)
        (self.root / "attempt-1-raw.json").write_text("{}")
        with self.assertRaises(ContractError):
            self.result(directory)

    def test_source_change_marks_stale_and_blocks_record(self):
        directory = self.frozen()
        record(self.attempt(directory), self.root, directory)
        (self.root / "check.json").write_text("{}")
        self.assertEqual(self.result(directory)["acceptance_status"], "stale")
        with self.assertRaises(ContractError):
            record(self.attempt(directory), self.root, directory)

    def test_target_change_marks_stale(self):
        directory = self.frozen()
        targets = copy.deepcopy(self.scope["targets"])
        targets[0]["build"] = "build-2"
        self.assertEqual(evaluate(self.root, directory, targets)["acceptance_status"], "stale")

    def test_wrong_attempt_target_rejected(self):
        directory = self.frozen()
        path = self.attempt(directory)
        draft = load(path)
        draft["target"]["build"] = "build-2"
        path.write_text(json.dumps(draft))
        with self.assertRaises(ContractError):
            record(path, self.root, directory)

    def test_unknown_permission_cannot_pass(self):
        self.scope["capabilities"][0]["authorization"] = "unknown"
        directory = self.frozen()
        with self.assertRaises(ContractError):
            record(self.attempt(directory), self.root, directory)
        record(self.attempt(directory, "blocked"), self.root, directory)
        self.assertEqual(self.result(directory)["acceptance_status"], "blocked")

    def test_read_capability_cannot_authorize_write(self):
        self.scope["checks"][0]["effect"] = "write"
        with self.assertRaises(ContractError):
            self.frozen()

    def test_cleanup_failure_prevents_pass(self):
        self.scope["checks"][0]["cleanup"] = "required"
        directory = self.frozen()
        record(self.attempt(directory, cleanup="failed"), self.root, directory)
        self.assertEqual(self.result(directory)["acceptance_status"], "inconclusive")

    def test_no_evidence_cannot_pass(self):
        directory = self.frozen()
        path = self.attempt(directory)
        value = load(path)
        value["evidence"] = []
        path.write_text(json.dumps(value))
        with self.assertRaises(ContractError):
            record(path, self.root, directory)

    def test_old_execution_cannot_be_backfilled(self):
        directory = self.frozen()
        path = self.attempt(directory)
        value = load(path)
        value["started_at"] = "2000-01-01T00:00:00Z"
        path.write_text(json.dumps(value))
        with self.assertRaises(ContractError):
            record(path, self.root, directory)

    def test_duplicate_checks_and_cycles_rejected(self):
        self.scope["checks"].append(copy.deepcopy(self.scope["checks"][0]))
        with self.assertRaises(ContractError):
            self.frozen("duplicate")
        self.scope["checks"].pop()
        self.scope["checks"][0]["depends_on"] = ["check"]
        with self.assertRaises(ContractError):
            self.frozen("cycle")

    def test_dependency_must_pass_before_dependent(self):
        self.scope["checks"].append({**copy.deepcopy(self.scope["checks"][0]), "id": "next", "depends_on": ["check"]})
        directory = self.frozen()
        record(self.attempt(directory, check_id="next"), self.root, directory)
        record(self.attempt(directory), self.root, directory)
        self.assertEqual(self.result(directory)["checks"]["next"]["status"], "inconclusive")

    def test_scope_and_attempt_are_non_overwriting(self):
        directory = self.frozen()
        path = self.attempt(directory)
        record(path, self.root, directory)
        with self.assertRaises(FileExistsError):
            record(path, self.root, directory)
        with self.assertRaises(ContractError):
            freeze(self.root / "run-draft.json", self.root, directory)

    def test_path_escape_rejected(self):
        self.scope["sources"][0]["path"] = "../other.json"
        with self.assertRaises(ContractError):
            self.frozen()

    def test_symlink_escape_rejected(self):
        with tempfile.TemporaryDirectory() as outside:
            external = Path(outside) / "file.json"
            write_new(external, {})
            (self.root / "link.json").symlink_to(external)
            self.scope["sources"][0]["path"] = "link.json"
            with self.assertRaises(ContractError):
                self.frozen()

    def test_status_cannot_be_reinterpreted(self):
        directory = self.frozen()
        path = self.attempt(directory, "failed")
        draft = load(path)
        draft["status"] = "passed"
        path.write_text(json.dumps(draft))
        with self.assertRaises(ContractError):
            record(path, self.root, directory)

    def test_arazzo_exact_dataset_and_cleanup(self):
        raw = {"schema_version": 1, "runner": "testkit-arazzo", "status": "passed", "runs": [{"workflow_id": "login", "dataset_index": 0, "status": "passed", "steps": [{"status": "passed"}]}]}
        binding = {"runner": "testkit-arazzo", "selector": "login", "dataset_index": 0}
        self.assertEqual(outcome(raw, binding), "passed")
        raw["runs"][0]["steps"][0]["status"] = "failed"
        with self.assertRaises(ContractError):
            outcome(raw, binding)
        binding["dataset_index"] = 1
        with self.assertRaises(ContractError):
            outcome(raw, binding)

    def test_schemathesis_only_suite_and_consistent_exit(self):
        raw = {"schema_version": 1, "runner": "schemathesis", "status": "passed", "returncode": 0}
        self.assertEqual(outcome(raw, {"runner": "schemathesis", "selector": "suite"}), "passed")
        with self.assertRaises(ContractError):
            outcome(raw, {"runner": "schemathesis", "selector": "business-case"})
        raw["returncode"] = 1
        with self.assertRaises(ContractError):
            outcome(raw, {"runner": "schemathesis", "selector": "suite"})

    def test_pytest_skip_is_not_complete_pass(self):
        raw = {"schema_version": 1, "runner": "pytest", "status": "passed", "exit_code": 0, "selected_nodeids": ["test_a.py::test_a"], "summary": {"total": 1, "skipped": 1}}
        with self.assertRaises(ContractError):
            outcome(raw, {"runner": "pytest", "selector": "suite", "nodeids": raw["selected_nodeids"]})

    def test_migration_keeps_original_and_cannot_be_repeated(self):
        source, output = self.root / "old.json", self.root / "new.json"
        write_new(source, {"schema_version": 1, "runner": "schemathesis", "status": "passed", "returncode": 0})
        before = digest(source)
        preview = migrate(source)
        self.assertFalse(output.exists())
        result = migrate(source, output)
        self.assertEqual(preview, result)
        self.assertEqual(digest(source), before)
        self.assertFalse(result["acceptance_eligible"])
        with self.assertRaises(ContractError):
            migrate(output)
        with self.assertRaises(FileExistsError):
            migrate(source, output)

    def test_defect_verified_requires_target_signature(self):
        phases = {}
        for phase, status in [("red", "failed"), ("green", "passed"), ("regression", "passed")]:
            self.scope["targets"][0]["build"] = "old" if phase == "red" else "new"
            directory = self.frozen(phase)
            record(self.attempt(directory, status, signature="synthetic-bug"), self.root, directory)
            phases[phase] = phase
        defect = {"schema_version": 1, "defect_id": "BUG-001", "expected": "confirmed", "failure_signature": "synthetic-bug", "conditions": "conditions.json", "phases": phases}
        self.assertEqual(verify(self.root, defect)["status"], "verified")
        defect["failure_signature"] = "another-bug"
        self.assertEqual(verify(self.root, defect)["status"], "incomplete")
        del defect["phases"]["red"]
        self.assertEqual(verify(self.root, defect)["status"], "incomplete")

    def test_formal_acceptance_checks_revision_and_case_identity(self):
        revision = {"version": 2, "summary": "synthetic", "updated_by_skill": "testspec-update"}
        context = {"context_schema_version": 2, "source_revision": revision}
        (self.root / "requirements.md").write_text("# Synthetic\nREQ-001: confirmed\n<!-- testspec-context\n" + json.dumps(context) + "\n-->")
        write_new(self.root / "cases.json", {"schema_version": 2, "_context": context, "testcases": [{"id": "case-1"}]})
        self.scope.update(mode="acceptance", source_revision=revision, scope_basis="synthetic confirmed scope")
        self.scope["sources"].extend([{"id": "requirements", "kind": "requirements", "path": "requirements.md"}, {"id": "cases", "kind": "cases", "path": "cases.json"}])
        self.scope["checks"][0]["requirement_refs"] = ["REQ-001"]
        directory = self.frozen()
        record(self.attempt(directory), self.root, directory)
        self.assertEqual(self.result(directory)["acceptance_status"], "passed")
        self.scope["checks"][0]["case_id"] = "missing"
        with self.assertRaises(ContractError):
            self.frozen("bad-case")
        self.scope["checks"][0]["case_id"] = "case-1"
        self.scope["source_revision"] = {**revision, "version": 3}
        with self.assertRaises(ContractError):
            self.frozen("bad-revision")

    def test_duplicate_json_keys_rejected(self):
        path = self.root / "duplicate.json"
        path.write_text('{"status":"failed","status":"passed"}')
        with self.assertRaises(ContractError):
            load(path)

    def test_migrated_record_cannot_be_registered_as_attempt(self):
        directory = self.frozen()
        source = self.root / "old.json"
        output = self.root / "migrated.json"
        write_new(source, {"schema_version": 1, "runner": "schemathesis", "status": "passed", "returncode": 0})
        migrate(source, output)
        with self.assertRaises(ContractError):
            record(output, self.root, directory)


if __name__ == "__main__":
    unittest.main()
