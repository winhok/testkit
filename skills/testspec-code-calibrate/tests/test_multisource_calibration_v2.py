from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path


SKILL = Path(__file__).resolve().parents[1]
VALIDATOR = SKILL / "scripts" / "validate_code_calibration.py"
RENDERER = SKILL / "scripts" / "render_code_calibration.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write_canonical(path: Path) -> dict:
    revision = {
        "version": 4,
        "summary": "synthetic shared flow",
        "updated_by_skill": "testspec-update",
    }
    path.write_text(
        "# Requirements\n\n- REQ-001 Complete the shared flow.\n\n"
        "<!-- testspec-context\n"
        + json.dumps(
            {"source_revision": revision, "canonical_source_policy": "prd-first"}
        )
        + "\n-->\n",
        encoding="utf-8",
    )
    return revision


def sources(role: str = "verification-baseline") -> list[dict]:
    return [
        {
            "id": "backend",
            "role": role,
            "repository_label": "synthetic-service",
            "ref": "main",
            "commit": "a" * 40,
            "scope": ["src/shared"],
        },
        {
            "id": "web",
            "role": role,
            "repository_label": "synthetic-web",
            "ref": "main",
            "commit": "b" * 40,
            "scope": ["src/shared"],
        },
        {
            "id": "mobile",
            "role": role,
            "repository_label": "synthetic-mobile",
            "ref": "main",
            "commit": "c" * 40,
            "scope": ["app/shared"],
        },
    ]


def summary(
    total: int, *, aligned: int = 0, code_only: int = 0, unknown: int = 0
) -> dict:
    return {
        "total": total,
        "aligned": aligned,
        "code-only": code_only,
        "conflict": 0,
        "prd-only": 0,
        "unknown": unknown,
    }


def comparison(canonical: Path, revision: dict) -> dict:
    findings = []
    for index, (source_id, path) in enumerate(
        (
            ("backend", "src/shared/entry.ts"),
            ("web", "src/shared/entry.ts"),
            ("mobile", "app/shared/Entry.kt"),
        ),
        1,
    ):
        findings.append(
            {
                "id": f"CAL-{index:03d}",
                "classification": "aligned",
                "requirement_refs": ["REQ-001"],
                "intended_behavior": "The shared flow completes.",
                "observed_behavior": f"The {source_id} surface completes the flow.",
                "reason": "",
                "evidence": [
                    {
                        "source_id": source_id,
                        "path": path,
                        "symbol": "completeFlow",
                        "lines": "10-20",
                        "observation": "Completes the visible flow.",
                    }
                ],
                "evidence_coverage": "enforcement-layer",
                "confidence": "high",
                "question_refs": [],
                "recommended_handoff": "testspec-analysis",
            }
        )
    return {
        "schema_version": 2,
        "_context": {
            "source_skill": "testspec-code-calibrate",
            "canonical_source_policy": "prd-first",
            "mode": "comparison",
            "authority": "reference",
            "canonical_source_path": "requirements.md",
            "canonical_source_digest": digest(canonical),
            "source_revision": revision,
            "code_evidence": {"sources": sources()},
            "canonical_mutation_performed": False,
            "status": "ready-for-analysis",
        },
        "summary": summary(3, aligned=3),
        "questions": [],
        "findings": findings,
    }


def snapshot(path: Path, source: dict, changed_path: str, stamp: str) -> dict:
    data = {
        "schema_version": 2,
        "source_id": source["id"],
        "snapshot_id": f"20260910T12000000000{stamp}Z-{stamp * 8}",
        "repository_label": source["repository_label"],
        "comparison": {
            "mode": "three-dot",
            "base_label": "production",
            "head_label": source["ref"],
            "base_commit": "d" * 40,
            "head_commit": source["commit"],
            "merge_base": "d" * 40,
            "include_worktree": False,
            "staged": False,
        },
        "scope": source["scope"],
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "worktree_dirty": False,
        "diff_digest": "sha256:" + stamp * 64,
        "stats": {
            "file_count": 1,
            "hunk_count": 1,
            "additions": 1,
            "deletions": 0,
            "binary_files": 0,
        },
        "warnings": [],
        "files": [
            {
                "path": changed_path,
                "status": "M",
                "additions": 1,
                "deletions": 0,
                "hunks": [
                    {"old_start": 1, "old_count": 0, "new_start": 1, "new_count": 1}
                ],
            }
        ],
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    return data


class TestMultisourceCalibrationV2(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = load_module(VALIDATOR, "calibration_v2_validator")

    def test_v1_migrates_and_validates_as_v2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            canonical = Path(tmp) / "requirements.md"
            revision = write_canonical(canonical)
            data = comparison(canonical, revision)
            data["schema_version"] = 1
            source = data["_context"]["code_evidence"]["sources"][0]
            source.pop("id")
            data["_context"]["code_evidence"] = source
            data["findings"] = [data["findings"][0]]
            data["findings"][0]["evidence"][0].pop("source_id")
            data["summary"] = summary(1, aligned=1)
            self.assertEqual(
                self.validator.validate(data, canonical_path=canonical), []
            )
            migrated = self.validator.migrate_v1_to_v2(data)
            self.assertEqual(migrated["schema_version"], 2)
            self.assertEqual(
                self.validator.validate(migrated, canonical_path=canonical), []
            )
            prd_only = deepcopy(data)
            finding = prd_only["findings"][0]
            finding.update(
                {
                    "classification": "prd-only",
                    "observed_behavior": "",
                    "evidence": [],
                    "evidence_coverage": "scoped-search",
                }
            )
            prd_only["summary"] = {
                "total": 1,
                "aligned": 0,
                "code-only": 0,
                "conflict": 0,
                "prd-only": 1,
                "unknown": 0,
            }
            self.assertEqual(
                self.validator.validate(prd_only, canonical_path=canonical), []
            )
            migrated_prd_only = self.validator.migrate_v1_to_v2(prd_only)
            self.assertEqual(
                migrated_prd_only["findings"][0]["searched_source_ids"],
                ["source-1"],
            )
            self.assertEqual(
                self.validator.validate(
                    migrated_prd_only, canonical_path=canonical
                ),
                [],
            )

    def test_backend_web_mobile_and_same_relative_paths_are_distinct(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            canonical = Path(tmp) / "requirements.md"
            revision = write_canonical(canonical)
            data = comparison(canonical, revision)
            self.assertEqual(
                self.validator.validate(data, canonical_path=canonical), []
            )
            rendered = load_module(RENDERER, "calibration_v2_renderer").render(data)
            self.assertIn("[backend] src/shared/entry.ts:completeFlow:10-20", rendered)
            self.assertIn("[web] src/shared/entry.ts:completeFlow:10-20", rendered)
            self.assertIn("[mobile] app/shared/Entry.kt:completeFlow:10-20", rendered)

    def test_rejects_duplicate_missing_unknown_and_cross_scope_source_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            canonical = Path(tmp) / "requirements.md"
            revision = write_canonical(canonical)
            base = comparison(canonical, revision)
            duplicate = deepcopy(base)
            duplicate["_context"]["code_evidence"]["sources"][1]["id"] = "backend"
            self.assertTrue(
                any(
                    "duplicated" in error
                    for error in self.validator.validate(
                        duplicate, canonical_path=canonical
                    )
                )
            )
            missing = deepcopy(base)
            missing["findings"][0]["evidence"][0].pop("source_id")
            self.assertTrue(
                any(
                    "source_id" in error
                    for error in self.validator.validate(
                        missing, canonical_path=canonical
                    )
                )
            )
            unknown = deepcopy(base)
            unknown["findings"][0]["evidence"][0]["source_id"] = "desktop"
            self.assertTrue(
                any(
                    "declared source" in error
                    for error in self.validator.validate(
                        unknown, canonical_path=canonical
                    )
                )
            )
            crossed = deepcopy(base)
            crossed["findings"][0]["evidence"][0]["source_id"] = "mobile"
            self.assertTrue(
                any(
                    "outside authorized scope" in error
                    for error in self.validator.validate(
                        crossed, canonical_path=canonical
                    )
                )
            )

            absence = deepcopy(base)
            finding = absence["findings"][0]
            finding.update(
                {
                    "classification": "prd-only",
                    "observed_behavior": "",
                    "evidence": [],
                    "evidence_coverage": "scoped-search",
                    "searched_source_ids": ["backend"],
                }
            )
            absence["findings"] = [finding]
            absence["summary"] = {
                "total": 1,
                "aligned": 0,
                "code-only": 0,
                "conflict": 0,
                "prd-only": 1,
                "unknown": 0,
            }
            self.assertTrue(
                any(
                    "search every declared source" in error
                    for error in self.validator.validate(
                        absence, canonical_path=canonical
                    )
                )
            )

    def test_recovery_requires_exact_snapshot_table_and_source_prefixed_obs(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft = root / "recovered-prd-draft.md"
            draft.write_text(
                "# Observed implementation draft — not canonical\n\n## Snapshots\n\n"
                "| Source ID | Role | Repository | Ref | Commit | Scope |\n|---|---|---|---|---|---|\n"
                "| backend | verification-baseline | synthetic-service | main | "
                + "a"
                * 40
                + " | src/shared |\n"
                "| web | verification-baseline | synthetic-web | main | "
                + "b"
                * 40
                + " | src/shared |\n\n"
                "## Observed behaviors\n\n| OBS-001 | CAL-001 | Visible behavior | [backend] src/shared/entry.ts:completeFlow:10-20 | Q-001 |\n\n"
                "## Product confirmation required\n\n- Q-001: Is this intended?\n",
                encoding="utf-8",
            )
            recovery_sources = sources()[:2]
            data = {
                "schema_version": 2,
                "_context": {
                    "source_skill": "testspec-code-calibrate",
                    "canonical_source_policy": "prd-first",
                    "mode": "recovery",
                    "authority": "reference",
                    "recovered_prd_draft": "artifacts/recovered-prd-draft.md",
                    "recovered_prd_draft_digest": digest(draft),
                    "code_evidence": {"sources": recovery_sources},
                    "canonical_mutation_performed": False,
                    "status": "needs-product-confirmation",
                },
                "summary": summary(1, code_only=1),
                "questions": [
                    {
                        "id": "Q-001",
                        "question": "Is this intended?",
                        "status": "open",
                        "blocking": True,
                        "finding_refs": ["CAL-001"],
                    }
                ],
                "findings": [
                    {
                        "id": "CAL-001",
                        "classification": "code-only",
                        "draft_ref": "OBS-001",
                        "requirement_refs": [],
                        "intended_behavior": "",
                        "observed_behavior": "Visible behavior.",
                        "reason": "",
                        "evidence": [
                            {
                                "source_id": "backend",
                                "path": "src/shared/entry.ts",
                                "symbol": "completeFlow",
                                "lines": "10-20",
                                "observation": "Visible behavior.",
                            }
                        ],
                        "evidence_coverage": "partial",
                        "confidence": "medium",
                        "question_refs": ["Q-001"],
                        "recommended_handoff": "product-confirmation",
                    }
                ],
            }
            self.assertEqual(self.validator.validate(data, draft_path=draft), [])
            draft.write_text(
                draft.read_text().replace("synthetic-web", "synthetic-ui"),
                encoding="utf-8",
            )
            data["_context"]["recovered_prd_draft_digest"] = digest(draft)
            errors = self.validator.validate(data, draft_path=draft)
            self.assertIn(
                "recovery draft snapshot table must exactly match JSON sources", errors
            )
            draft.write_text(
                draft.read_text().replace("[backend]", "[web]"), encoding="utf-8"
            )
            data["_context"]["recovered_prd_draft_digest"] = digest(draft)
            self.assertTrue(
                any(
                    "OBS-001 evidence" in error
                    for error in self.validator.validate(data, draft_path=draft)
                )
            )

    def test_change_snapshots_cannot_cross_commit_scope_digest_or_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            canonical = root / "requirements.md"
            revision = write_canonical(canonical)
            change_sources = sources("change-evidence")[:2]
            snapshot_paths = []
            bindings = []
            for source, changed_path, stamp in zip(
                change_sources,
                ("src/shared/entry.ts", "src/shared/entry.ts"),
                ("1", "2"),
            ):
                path = root / f"change-snapshot-{source['id']}.json"
                snap = snapshot(path, source, changed_path, stamp)
                snapshot_paths.append(path)
                bindings.append(
                    {
                        "source_id": source["id"],
                        "path": f"artifacts/{path.name}",
                        "digest": digest(path),
                        "snapshot_id": snap["snapshot_id"],
                    }
                )
            data = {
                "schema_version": 2,
                "_context": {
                    "source_skill": "testspec-code-calibrate",
                    "canonical_source_policy": "prd-first",
                    "mode": "change-diff",
                    "authority": "reference",
                    "canonical_source_path": "requirements.md",
                    "canonical_source_digest": digest(canonical),
                    "source_revision": revision,
                    "code_evidence": {"sources": change_sources},
                    "change_snapshots": bindings,
                    "canonical_mutation_performed": False,
                    "status": "ready-for-analysis",
                },
                "summary": summary(1, aligned=1),
                "questions": [],
                "findings": [
                    {
                        "id": "CAL-001",
                        "classification": "aligned",
                        "change_trace_status": "matched",
                        "requirement_refs": ["REQ-001"],
                        "intended_behavior": "The shared flow completes.",
                        "observed_behavior": "Both changed surfaces complete.",
                        "reason": "",
                        "evidence": [
                            {
                                "source_id": "backend",
                                "path": "src/shared/entry.ts",
                                "symbol": "completeFlow",
                                "lines": "1",
                                "observation": "Backend changed.",
                                "source": "diff",
                                "layer": "enforcement",
                            },
                            {
                                "source_id": "web",
                                "path": "src/shared/entry.ts",
                                "symbol": "completeFlow",
                                "lines": "1",
                                "observation": "Web changed.",
                                "source": "diff",
                                "layer": "entry",
                            },
                        ],
                        "evidence_coverage": "end-to-end",
                        "confidence": "high",
                        "question_refs": [],
                        "recommended_handoff": "testspec-analysis",
                    }
                ],
                "change_trace": {
                    "candidate_strategy": "keyword-hints-only",
                    "data_quality_notes": [],
                    "unmapped_changes": [],
                },
            }
            self.assertEqual(
                self.validator.validate(
                    data, canonical_path=canonical, snapshot_path=snapshot_paths
                ),
                [],
            )
            crossed = deepcopy(data)
            crossed["_context"]["change_snapshots"][0]["digest"] = bindings[1]["digest"]
            crossed["_context"]["code_evidence"]["sources"][0]["commit"] = (
                change_sources[1]["commit"]
            )
            crossed["_context"]["code_evidence"]["sources"][0]["scope"] = [
                "other/scope"
            ]
            errors = self.validator.validate(
                crossed, canonical_path=canonical, snapshot_path=snapshot_paths
            )
            self.assertTrue(any("digest does not match" in error for error in errors))
            self.assertTrue(any("commit does not match" in error for error in errors))
            self.assertTrue(any("scope does not match" in error for error in errors))

    def test_rejects_absolute_url_company_and_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            canonical = Path(tmp) / "requirements.md"
            revision = write_canonical(canonical)
            cases = (
                "/Users/sample/code.ts",
                "https://private.invalid/repo",
                "ExampleCorp",
                "ghp_abcdefghijklmnopqrst",
            )
            for leaked in cases:
                data = comparison(canonical, revision)
                data["questions"] = [
                    {
                        "id": "Q-001",
                        "question": leaked,
                        "status": "open",
                        "blocking": True,
                        "finding_refs": ["CAL-001"],
                    }
                ]
                data["findings"][0]["classification"] = "unknown"
                data["findings"][0]["reason"] = leaked
                data["findings"][0]["intended_behavior"] = ""
                data["findings"][0]["observed_behavior"] = ""
                data["findings"][0]["question_refs"] = ["Q-001"]
                data["findings"][0]["recommended_handoff"] = "product-confirmation"
                data["summary"] = summary(3, aligned=2, unknown=1)
                data["_context"]["status"] = "needs-product-confirmation"
                self.assertTrue(
                    any(
                        token in error
                        for error in self.validator.validate(
                            data, canonical_path=canonical
                        )
                        for token in (
                            "absolute path",
                            "remote URL",
                            "company identifier",
                            "secret-like token",
                        )
                    )
                )


if __name__ == "__main__":
    unittest.main()
