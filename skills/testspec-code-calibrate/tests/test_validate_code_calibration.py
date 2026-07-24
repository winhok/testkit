from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "validate_code_calibration.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("validate_code_calibration", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write_canonical(path: Path) -> dict:
    revision = {
        "version": 2,
        "summary": "synthetic notification preference",
        "updated_by_skill": "testspec-update",
    }
    path.write_text(
        "# Requirements\n\n"
        "- REQ-001 Users can disable digest notifications.\n\n"
        "<!-- testspec-context\n"
        + json.dumps({
            "source_skill": "testspec-update",
            "source_revision": revision,
            "canonical_source_policy": "prd-first",
        })
        + "\n-->\n",
        encoding="utf-8",
    )
    return revision


def evidence() -> list[dict]:
    return [{
        "path": "src/preferences/digest.ts",
        "symbol": "saveDigestPreference",
        "lines": "42-68",
        "observation": "Persists the disabled preference.",
    }]


def comparison_artifact(canonical: Path, revision: dict) -> dict:
    return {
        "schema_version": 1,
        "_context": {
            "source_skill": "testspec-code-calibrate",
            "canonical_source_policy": "prd-first",
            "mode": "comparison",
            "authority": "reference",
            "canonical_source_path": "requirements.md",
            "canonical_source_digest": digest(canonical),
            "source_revision": revision,
            "code_evidence": {
                "role": "reference",
                "repository_label": "synthetic-app",
                "ref": "main",
                "commit": "abcdef1",
                "scope": ["src/preferences"],
            },
            "canonical_mutation_performed": False,
            "status": "needs-product-confirmation",
        },
        "summary": {
            "total": 2,
            "aligned": 1,
            "code-only": 0,
            "conflict": 1,
            "prd-only": 0,
            "unknown": 0,
        },
        "questions": [{
            "id": "Q-001",
            "question": "Should disabling the preference also stop future schedules?",
            "status": "open",
            "blocking": True,
            "finding_refs": ["CAL-002"],
        }],
        "findings": [
            {
                "id": "CAL-001",
                "classification": "aligned",
                "requirement_refs": ["REQ-001"],
                "intended_behavior": "The preference can be disabled.",
                "observed_behavior": "The preference is persisted as disabled.",
                "reason": "",
                "evidence": evidence(),
                "evidence_coverage": "end-to-end",
                "confidence": "high",
                "question_refs": [],
                "recommended_handoff": "none",
            },
            {
                "id": "CAL-002",
                "classification": "conflict",
                "requirement_refs": ["AC-001"],
                "intended_behavior": "Future digests are not created.",
                "observed_behavior": "The scheduler remains enabled.",
                "reason": "",
                "evidence": [{
                    "path": "src/preferences/scheduler.ts",
                    "symbol": "scheduleDigest",
                    "lines": "12-25",
                    "observation": "Schedules a digest without reading the preference.",
                }],
                "evidence_coverage": "end-to-end",
                "confidence": "high",
                "question_refs": ["Q-001"],
                "recommended_handoff": "product-confirmation",
            },
        ],
    }


class TestCodeCalibrationValidator(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()

    def test_valid_comparison_preserves_canonical_revision_and_digest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            canonical = Path(tmp) / "requirements.md"
            revision = write_canonical(canonical)
            data = comparison_artifact(canonical, revision)
            self.assertEqual(self.module.validate(data, canonical_path=canonical), [])

    def test_valid_recovery_requires_visible_noncanonical_draft(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            draft = Path(tmp) / "recovered-prd-draft.md"
            draft.write_text(
                "# Observed implementation draft — not canonical\n\n"
                "## Snapshot\n\nsynthetic-app main abcdef1 src/preferences\n\n"
                "## Observed behaviors\n\n"
                "- OBS-001: Users can disable digest notifications. Q-001\n\n"
                "## Product confirmation required\n\n"
                "- Q-001: Is this intended?\n",
                encoding="utf-8",
            )
            data = {
                "schema_version": 1,
                "_context": {
                    "source_skill": "testspec-code-calibrate",
                    "canonical_source_policy": "prd-first",
                    "mode": "recovery",
                    "authority": "reference",
                    "recovered_prd_draft": "artifacts/recovered-prd-draft.md",
                    "recovered_prd_draft_digest": digest(draft),
                    "code_evidence": {
                        "role": "reference",
                        "repository_label": "synthetic-app",
                        "ref": "main",
                        "commit": "abcdef1",
                        "scope": ["src/preferences"],
                    },
                    "canonical_mutation_performed": False,
                    "status": "needs-product-confirmation",
                },
                "summary": {
                    "total": 1,
                    "aligned": 0,
                    "code-only": 1,
                    "conflict": 0,
                    "prd-only": 0,
                    "unknown": 0,
                },
                "questions": [{
                    "id": "Q-001",
                    "question": "Should this observed behavior become a requirement?",
                    "status": "open",
                    "blocking": True,
                    "finding_refs": ["CAL-001"],
                }],
                "findings": [{
                    "id": "CAL-001",
                    "classification": "code-only",
                    "draft_ref": "OBS-001",
                    "requirement_refs": [],
                    "intended_behavior": "",
                    "observed_behavior": "Users can disable digest notifications.",
                    "reason": "",
                    "evidence": evidence(),
                    "evidence_coverage": "partial",
                    "confidence": "high",
                    "question_refs": ["Q-001"],
                    "recommended_handoff": "product-confirmation",
                }],
            }
            self.assertEqual(self.module.validate(data, draft_path=draft), [])

    def test_rejects_absolute_or_out_of_scope_evidence_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            canonical = Path(tmp) / "requirements.md"
            revision = write_canonical(canonical)
            data = comparison_artifact(canonical, revision)
            data["findings"][0]["evidence"][0]["path"] = "/Users/sample/private.ts"
            errors = self.module.validate(data, canonical_path=canonical)
            self.assertTrue(any("repository-relative" in item for item in errors))
            self.assertTrue(any("private absolute path" in item for item in errors))

            data = comparison_artifact(canonical, revision)
            data["findings"][0]["evidence"][0]["path"] = "src/admin/secret.ts"
            errors = self.module.validate(data, canonical_path=canonical)
            self.assertTrue(any("outside authorized scope" in item for item in errors))

    def test_rejects_conflict_without_question_and_summary_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            canonical = Path(tmp) / "requirements.md"
            revision = write_canonical(canonical)
            data = comparison_artifact(canonical, revision)
            data["findings"][1]["question_refs"] = []
            data["summary"]["conflict"] = 0
            errors = self.module.validate(data, canonical_path=canonical)
            self.assertTrue(any("requires Q-* refs" in item for item in errors))
            self.assertIn("summary does not match findings", errors)

    def test_rejects_canonical_mutation_or_revision_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            canonical = Path(tmp) / "requirements.md"
            revision = write_canonical(canonical)
            data = comparison_artifact(canonical, revision)
            canonical.write_text(
                canonical.read_text(encoding="utf-8") + "\nmutated\n",
                encoding="utf-8",
            )
            errors = self.module.validate(data, canonical_path=canonical)
            self.assertIn(
                "canonical source digest changed during calibration",
                errors,
            )

            canonical = Path(tmp) / "requirements-2.md"
            revision = write_canonical(canonical)
            data = comparison_artifact(canonical, revision)
            data["_context"]["canonical_mutation_performed"] = True
            data["_context"]["source_revision"] = {"version": 99}
            errors = self.module.validate(data, canonical_path=canonical)
            self.assertTrue(any("canonical_mutation_performed" in item for item in errors))
            self.assertIn("source_revision does not match canonical file", errors)

    def test_recovery_rejects_comparison_classification_and_revision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            draft = Path(tmp) / "recovered-prd-draft.md"
            draft.write_text(
                "# Observed implementation draft — not canonical\n\n"
                "## Snapshot\n\nSynthetic snapshot.\n\n"
                "## Observed behaviors\n\nOBS-001 Q-001\n\n"
                "## Product confirmation required\n\nQ-001\n",
                encoding="utf-8",
            )
            canonical = Path(tmp) / "requirements.md"
            revision = write_canonical(canonical)
            data = comparison_artifact(canonical, revision)
            data["_context"].update({
                "mode": "recovery",
                "recovered_prd_draft": "artifacts/recovered-prd-draft.md",
                "recovered_prd_draft_digest": digest(draft),
                "status": "needs-product-confirmation",
            })
            errors = self.module.validate(data, draft_path=draft)
            self.assertTrue(any("must not contain source_revision" in item for item in errors))
            self.assertTrue(any("permits only code-only or unknown" in item for item in errors))

    def test_rejects_low_confidence_alignment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            canonical = Path(tmp) / "requirements.md"
            revision = write_canonical(canonical)
            data = comparison_artifact(canonical, revision)
            data["findings"][0]["confidence"] = "low"
            errors = self.module.validate(data, canonical_path=canonical)
            self.assertTrue(any("aligned cannot use low confidence" in item for item in errors))

    def test_rejects_undeclared_or_one_way_question_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            canonical = Path(tmp) / "requirements.md"
            revision = write_canonical(canonical)
            data = comparison_artifact(canonical, revision)
            data["questions"] = []
            errors = self.module.validate(data, canonical_path=canonical)
            self.assertTrue(any("is not declared" in item for item in errors))

            data = comparison_artifact(canonical, revision)
            data["questions"][0]["finding_refs"] = ["CAL-001"]
            errors = self.module.validate(data, canonical_path=canonical)
            self.assertTrue(any("not linked back" in item for item in errors))
            self.assertTrue(any("do not match finding links" in item for item in errors))

    def test_rejects_private_metadata_and_invalid_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            canonical = Path(tmp) / "requirements.md"
            revision = write_canonical(canonical)
            data = comparison_artifact(canonical, revision)
            data["_context"]["code_evidence"]["commit"] = "not-a-hash"
            data["questions"][0]["question"] = (
                "Ask owner@corp.example about https://private.example/item "
                "from 10.1.2.3 in .cursor/projects/private and /tmp/private."
            )
            errors = self.module.validate(data, canonical_path=canonical)
            self.assertTrue(any("Git hash" in item for item in errors))
            self.assertIn("artifact contains a remote URL", errors)
            self.assertIn("artifact contains an email address", errors)
            self.assertIn("artifact contains an IPv4 address", errors)
            self.assertIn("artifact contains a private workspace identifier", errors)

            data = comparison_artifact(canonical, revision)
            data["access_token"] = "ghp_abcdefghijklmnopqrst"
            errors = self.module.validate(data, canonical_path=canonical)
            self.assertTrue(any("unsupported fields" in item for item in errors))
            self.assertIn("artifact contains a secret-like token", errors)

    def test_rejects_mismatched_canonical_filename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            canonical = Path(tmp) / "requirements.md"
            revision = write_canonical(canonical)
            data = comparison_artifact(canonical, revision)
            data["_context"]["canonical_source_path"] = "proposal.md"
            errors = self.module.validate(data, canonical_path=canonical)
            self.assertIn(
                "canonical_source_path does not match the --canonical file",
                errors,
            )

    def test_recovery_draft_must_map_findings_and_questions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            draft = Path(tmp) / "recovered-prd-draft.md"
            draft.write_text(
                "# Observed implementation draft — not canonical\n",
                encoding="utf-8",
            )
            canonical = Path(tmp) / "requirements.md"
            revision = write_canonical(canonical)
            data = comparison_artifact(canonical, revision)
            data["_context"] = {
                "source_skill": "testspec-code-calibrate",
                "canonical_source_policy": "prd-first",
                "mode": "recovery",
                "authority": "reference",
                "recovered_prd_draft": "artifacts/recovered-prd-draft.md",
                "recovered_prd_draft_digest": digest(draft),
                "code_evidence": data["_context"]["code_evidence"],
                "canonical_mutation_performed": False,
                "status": "needs-product-confirmation",
            }
            finding = data["findings"][1]
            finding["classification"] = "code-only"
            finding["requirement_refs"] = []
            finding["intended_behavior"] = ""
            finding["draft_ref"] = "OBS-001"
            data["findings"] = [finding]
            data["questions"][0]["finding_refs"] = ["CAL-002"]
            data["summary"] = {
                "total": 1,
                "aligned": 0,
                "conflict": 0,
                "code-only": 1,
                "prd-only": 0,
                "unknown": 0,
            }
            errors = self.module.validate(data, draft_path=draft)
            self.assertTrue(any("missing section" in item for item in errors))
            self.assertIn("recovery draft is missing OBS-001", errors)
            self.assertIn("recovery draft is missing Q-001", errors)

            draft.write_text(
                "# Observed implementation draft — not canonical\n\n"
                "## Snapshot\n\n/Users/sample/private\n\n"
                "## Observed behaviors\n\nOBS-001\n\n"
                "## Product confirmation required\n\nQ-001\n",
                encoding="utf-8",
            )
            errors = self.module.validate(data, draft_path=draft)
            self.assertIn(
                "recovery draft contains a private absolute path",
                errors,
            )
            self.assertIn(
                "recovery draft digest does not match artifact",
                errors,
            )

    def test_rejects_non_string_scope_invalid_revision_and_line_span(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            canonical = Path(tmp) / "requirements.md"
            revision = write_canonical(canonical)
            data = comparison_artifact(canonical, revision)
            data["_context"]["code_evidence"]["scope"] = [123]
            data["_context"]["source_revision"] = {
                **revision,
                "version": True,
            }
            data["findings"][0]["evidence"][0]["lines"] = "68-42"
            errors = self.module.validate(data, canonical_path=canonical)
            self.assertTrue(any("unsafe code scope path" in item for item in errors))
            self.assertIn(
                "comparison mode requires a complete versioned source_revision",
                errors,
            )
            self.assertTrue(any("ascending N-N" in item for item in errors))

    def test_malformed_nested_types_report_errors_instead_of_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            canonical = Path(tmp) / "requirements.md"
            revision = write_canonical(canonical)
            data = comparison_artifact(canonical, revision)
            data["_context"]["mode"] = []
            data["_context"]["code_evidence"]["role"] = []
            data["questions"][0]["finding_refs"] = [{}]
            data["findings"][0]["classification"] = []
            errors = self.module.validate(data, canonical_path=canonical)
            self.assertTrue(any("_context.mode" in item for item in errors))
            self.assertTrue(any("role is invalid" in item for item in errors))
            self.assertTrue(any("invalid finding refs" in item for item in errors))
            self.assertTrue(any("classification is invalid" in item for item in errors))

    def test_allows_explicit_repository_root_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            canonical = Path(tmp) / "requirements.md"
            revision = write_canonical(canonical)
            data = comparison_artifact(canonical, revision)
            data["_context"]["code_evidence"]["scope"] = ["."]
            self.assertEqual(
                self.module.validate(data, canonical_path=canonical),
                [],
            )

    def test_rejects_empty_or_semantically_inconsistent_findings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            canonical = Path(tmp) / "requirements.md"
            revision = write_canonical(canonical)
            data = comparison_artifact(canonical, revision)
            data["findings"] = []
            data["questions"] = []
            data["summary"] = {
                "total": 0,
                "aligned": 0,
                "conflict": 0,
                "code-only": 0,
                "prd-only": 0,
                "unknown": 0,
            }
            errors = self.module.validate(data, canonical_path=canonical)
            self.assertIn(
                "findings must contain at least one calibration result",
                errors,
            )

            data = comparison_artifact(canonical, revision)
            finding = data["findings"][1]
            finding["classification"] = "code-only"
            finding["intended_behavior"] = "Contradictory intent."
            data["summary"]["conflict"] = 0
            data["summary"]["code-only"] = 1
            errors = self.module.validate(data, canonical_path=canonical)
            self.assertTrue(any("must not contain requirement refs" in item for item in errors))
            self.assertTrue(any("must not contain intended_behavior" in item for item in errors))

            data = comparison_artifact(canonical, revision)
            finding = data["findings"][1]
            finding["classification"] = "prd-only"
            finding["evidence_coverage"] = "scoped-search"
            finding["recommended_handoff"] = "testspec-analysis"
            finding["question_refs"] = []
            data["questions"] = []
            data["summary"]["conflict"] = 0
            data["summary"]["prd-only"] = 1
            data["_context"]["status"] = "ready-for-analysis"
            errors = self.module.validate(data, canonical_path=canonical)
            self.assertTrue(any("must not contain observed_behavior" in item for item in errors))

    def test_rejects_mode_incompatible_cli_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            canonical = Path(tmp) / "requirements.md"
            revision = write_canonical(canonical)
            draft = Path(tmp) / "draft.md"
            draft.write_text("not canonical", encoding="utf-8")
            data = comparison_artifact(canonical, revision)
            errors = self.module.validate(
                data,
                canonical_path=canonical,
                draft_path=draft,
            )
            self.assertIn("comparison mode must not use --draft", errors)

    def test_partial_evidence_cannot_claim_alignment_or_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            canonical = Path(tmp) / "requirements.md"
            revision = write_canonical(canonical)
            data = comparison_artifact(canonical, revision)
            data["findings"][0]["evidence_coverage"] = "partial"
            data["findings"][1]["evidence_coverage"] = "partial"
            errors = self.module.validate(data, canonical_path=canonical)
            self.assertTrue(
                any("aligned requires end-to-end" in item for item in errors)
            )
            self.assertTrue(
                any("conflict requires end-to-end" in item for item in errors)
            )


if __name__ == "__main__":
    unittest.main()
