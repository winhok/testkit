from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from copy import deepcopy


REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL_ROOT = REPO_ROOT / "skills" / "testspec-code-calibrate"
COLLECTOR = SKILL_ROOT / "scripts" / "collect_change_snapshot.py"
SNAPSHOT_VALIDATOR = SKILL_ROOT / "scripts" / "validate_change_snapshot.py"
CALIBRATION_VALIDATOR = SKILL_ROOT / "scripts" / "validate_code_calibration.py"
RENDERER = SKILL_ROOT / "scripts" / "render_code_calibration.py"


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    return result.stdout.strip()


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def load_validator():
    spec = importlib.util.spec_from_file_location(
        "validate_code_calibration_change_diff",
        CALIBRATION_VALIDATOR,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestChangeDiffTools(unittest.TestCase):
    def create_branch_topology(self, root: Path) -> Path:
        repo = root / "synthetic-repo"
        repo.mkdir()
        git(repo, "init", "-b", "production")
        git(repo, "config", "user.name", "Synthetic Evaluator")
        git(repo, "config", "user.email", "evaluator@example.invalid")
        write(
            repo / "src/profile/ui.ts",
            "export const profileLabel = 'Display name'\n",
        )
        write(
            repo / "src/profile/service.ts",
            "export function saveProfile(name: string) { return { name } }\n",
        )
        write(repo / "src/profile/readme.txt", "synthetic fixture\n")
        git(repo, "add", ".")
        git(repo, "commit", "-m", "Create synthetic production baseline")

        git(repo, "switch", "-c", "test")
        write(
            repo / "src/profile/ui.ts",
            "export const profileLabel = 'Public name'\n"
            "export const successMessage = 'Saved'\n",
        )
        write(
            repo / "src/profile/service.ts",
            "export function saveProfile(name: string) {\n"
            "  if (!name.trim()) throw new Error('Required')\n"
            "  return { name: name.trim() }\n"
            "}\n",
        )
        git(repo, "add", ".")
        git(repo, "commit", "-m", "Add synthetic test behavior")

        git(repo, "switch", "-c", "requirement")
        write(
            repo / "src/profile/ui.ts",
            "export const profileLabel = 'Public name'\n"
            "export const successMessage = 'Profile saved'\n",
        )
        write(
            repo / "src/profile/audit.ts",
            "export function recordProfileChange() { return 'recorded' }\n",
        )
        git(repo, "add", ".")
        git(repo, "commit", "-m", "Add synthetic requirement behavior")
        return repo

    def collect(
        self,
        repo: Path,
        root: Path,
        base: str,
        head: str,
        base_label: str,
        head_label: str,
        filename: str,
    ) -> Path:
        output = root / filename
        result = subprocess.run(
            [
                sys.executable,
                str(COLLECTOR),
                "--repo-root",
                str(repo),
                "--repository-label",
                "synthetic-app",
                "--base-ref",
                base,
                "--head-ref",
                head,
                "--base-label",
                base_label,
                "--head-label",
                head_label,
                "--scope",
                "src/profile",
                "--output",
                str(output),
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        validation = subprocess.run(
            [sys.executable, str(SNAPSHOT_VALIDATOR), "--input", str(output)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(
            validation.returncode,
            0,
            validation.stdout + validation.stderr,
        )
        return output

    def test_synthetic_production_test_requirement_topology_is_safe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self.create_branch_topology(root)
            production_test = self.collect(
                repo,
                root,
                "production",
                "test",
                "production",
                "test",
                "production-test.json",
            )
            production_requirement = self.collect(
                repo,
                root,
                "production",
                "requirement",
                "production",
                "requirement",
                "production-requirement.json",
            )
            test_requirement = self.collect(
                repo,
                root,
                "test",
                "requirement",
                "test",
                "requirement",
                "test-requirement.json",
            )

            first = json.loads(production_test.read_text(encoding="utf-8"))
            second = json.loads(production_requirement.read_text(encoding="utf-8"))
            third = json.loads(test_requirement.read_text(encoding="utf-8"))
            self.assertEqual(first["stats"]["file_count"], 2)
            self.assertEqual(second["stats"]["file_count"], 3)
            self.assertEqual(third["stats"]["file_count"], 2)
            for snapshot in (production_test, production_requirement, test_requirement):
                text = snapshot.read_text(encoding="utf-8")
                self.assertNotIn(str(repo), text)
                self.assertNotIn("raw_diff", text)
                self.assertNotIn("Profile saved", text)
                self.assertNotIn("actual_ref", text)

    def test_change_diff_calibration_mapping_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self.create_branch_topology(root)
            snapshot = self.collect(
                repo,
                root,
                "test",
                "requirement",
                "test",
                "requirement",
                "change-snapshot.json",
            )
            snapshot_data = json.loads(snapshot.read_text(encoding="utf-8"))
            canonical = root / "requirements.md"
            revision = {
                "version": 3,
                "summary": "synthetic profile revision",
                "updated_by_skill": "testspec-update",
            }
            canonical.write_text(
                "# Requirements\n\n"
                "- REQ-001: Show a confirmation after saving a public name.\n"
                "- REQ-002: Allow undo after saving.\n\n"
                "<!-- testspec-context\n"
                + json.dumps(
                    {
                        "source_skill": "testspec-update",
                        "source_revision": revision,
                        "canonical_source_policy": "prd-first",
                    }
                )
                + "\n-->\n",
                encoding="utf-8",
            )
            artifact = {
                "schema_version": 1,
                "_context": {
                    "source_skill": "testspec-code-calibrate",
                    "canonical_source_policy": "prd-first",
                    "mode": "change-diff",
                    "authority": "reference",
                    "canonical_source_path": "requirements.md",
                    "canonical_source_digest": digest(canonical),
                    "source_revision": revision,
                    "code_evidence": {
                        "role": "change-evidence",
                        "repository_label": "synthetic-app",
                        "ref": "requirement",
                        "commit": snapshot_data["comparison"]["head_commit"],
                        "scope": ["src/profile"],
                    },
                    "change_snapshot": {
                        "path": "artifacts/change-snapshot.json",
                        "digest": digest(snapshot),
                        "snapshot_id": snapshot_data["snapshot_id"],
                    },
                    "canonical_mutation_performed": False,
                    "status": "needs-product-confirmation",
                },
                "summary": {
                    "total": 2,
                    "aligned": 1,
                    "code-only": 0,
                    "conflict": 0,
                    "prd-only": 0,
                    "unknown": 1,
                },
                "questions": [
                    {
                        "id": "Q-001",
                        "question": "Should saving also provide an undo action?",
                        "status": "open",
                        "blocking": True,
                        "finding_refs": ["CAL-002"],
                    }
                ],
                "findings": [
                    {
                        "id": "CAL-001",
                        "classification": "aligned",
                        "change_trace_status": "matched",
                        "requirement_refs": ["REQ-001"],
                        "intended_behavior": "Saving shows a confirmation.",
                        "observed_behavior": "The changed user entry displays a save confirmation.",
                        "reason": "",
                        "evidence": [
                            {
                                "path": "src/profile/ui.ts",
                                "symbol": "success-message",
                                "lines": "1-2",
                                "observation": "The changed entry exposes a save confirmation.",
                                "source": "diff",
                                "layer": "entry",
                            },
                            {
                                "path": "src/profile/service.ts",
                                "symbol": "saveProfile",
                                "lines": "1-4",
                                "observation": "The connected service persists the accepted name.",
                                "source": "snapshot",
                                "layer": "state",
                            },
                        ],
                        "evidence_coverage": "end-to-end",
                        "confidence": "high",
                        "question_refs": [],
                        "recommended_handoff": "testspec-analysis",
                    },
                    {
                        "id": "CAL-002",
                        "classification": "unknown",
                        "change_trace_status": "not-observed",
                        "requirement_refs": ["REQ-002"],
                        "intended_behavior": "Saving provides an undo action.",
                        "observed_behavior": "",
                        "reason": "No undo-related change was observed in this Diff.",
                        "evidence": [],
                        "evidence_coverage": "partial",
                        "confidence": "medium",
                        "question_refs": ["Q-001"],
                        "recommended_handoff": "product-confirmation",
                    },
                ],
                "change_trace": {
                    "candidate_strategy": "keyword-hints-only",
                    "data_quality_notes": [],
                    "unmapped_changes": [
                        {
                            "path": "src/profile/audit.ts",
                            "reason": "No current requirement candidate was found.",
                        }
                    ],
                },
            }
            validator = load_validator()
            self.assertEqual(
                validator.validate(
                    artifact,
                    canonical_path=canonical,
                    snapshot_path=snapshot,
                ),
                [],
            )
            invalid_absence = deepcopy(artifact)
            invalid_absence["findings"][1]["classification"] = "prd-only"
            errors = validator.validate(
                invalid_absence,
                canonical_path=canonical,
                snapshot_path=snapshot,
            )
            self.assertTrue(
                any("must not infer prd-only" in error for error in errors)
            )

            artifact_path = root / "code-calibration.json"
            report_path = root / "code-calibration.md"
            artifact_path.write_text(
                json.dumps(artifact, ensure_ascii=False),
                encoding="utf-8",
            )
            rendered = subprocess.run(
                [
                    sys.executable,
                    str(RENDERER),
                    "--input",
                    str(artifact_path),
                    "--output",
                    str(report_path),
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(rendered.returncode, 0, rendered.stdout + rendered.stderr)
            report = report_path.read_text(encoding="utf-8")
            self.assertIn("CAL-001", report)
            self.assertIn("not-observed", report)
            self.assertIn("The changed user entry displays", report)
            self.assertNotIn("export const successMessage", report)

    def test_change_snapshot_rejects_persisted_raw_diff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self.create_branch_topology(root)
            snapshot = self.collect(
                repo,
                root,
                "test",
                "requirement",
                "test",
                "requirement",
                "change-snapshot.json",
            )
            data = json.loads(snapshot.read_text(encoding="utf-8"))
            data["raw_diff"] = "+ private changed line"
            module_spec = importlib.util.spec_from_file_location(
                "validate_change_snapshot_for_test",
                SNAPSHOT_VALIDATOR,
            )
            assert module_spec and module_spec.loader
            module = importlib.util.module_from_spec(module_spec)
            module_spec.loader.exec_module(module)
            self.assertTrue(
                any("raw diff" in error for error in module.validate(data))
            )

    def test_change_snapshot_rejects_control_paths_and_invalid_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self.create_branch_topology(root)
            snapshot = self.collect(
                repo,
                root,
                "test",
                "requirement",
                "test",
                "requirement",
                "change-snapshot.json",
            )
            data = json.loads(snapshot.read_text(encoding="utf-8"))
            module_spec = importlib.util.spec_from_file_location(
                "validate_change_snapshot_for_shape_test",
                SNAPSHOT_VALIDATOR,
            )
            assert module_spec and module_spec.loader
            module = importlib.util.module_from_spec(module_spec)
            module_spec.loader.exec_module(module)

            invalid_path = deepcopy(data)
            invalid_path["files"][0]["path"] += "\nprivate"
            self.assertTrue(
                any("repository-relative" in error for error in module.validate(invalid_path))
            )

            invalid_status = deepcopy(data)
            invalid_status["files"][0]["status"] = "modified privately"
            self.assertTrue(
                any("name-status" in error for error in module.validate(invalid_status))
            )

    def test_snapshot_does_not_inspect_dirty_state_outside_authorized_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self.create_branch_topology(root)
            write(repo / "outside-scope.txt", "local private worktree state\n")
            snapshot = self.collect(
                repo,
                root,
                "test",
                "requirement",
                "test",
                "requirement",
                "change-snapshot.json",
            )
            data = json.loads(snapshot.read_text(encoding="utf-8"))
            self.assertFalse(data["worktree_dirty"])
            self.assertNotIn("worktree-dirty-but-excluded", data["warnings"])
            self.assertNotIn("outside-scope.txt", snapshot.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
