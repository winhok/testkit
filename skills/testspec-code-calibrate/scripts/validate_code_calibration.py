#!/usr/bin/env python3
"""Validate a TestSpec code-calibration artifact and its immutable source."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any


CLASSIFICATIONS = {"aligned", "conflict", "code-only", "prd-only", "unknown"}
CODE_ROLES = {"reference", "verification-baseline", "change-evidence"}
MODES = {"comparison", "recovery", "change-diff"}
CHANGE_TRACE_STATUSES = {
    "matched",
    "partial",
    "not-observed",
    "deviation",
    "unknown",
}
EVIDENCE_SOURCES = {"diff", "snapshot"}
EVIDENCE_LAYERS = {"entry", "enforcement", "state", "feedback", "external"}
CONFIDENCE_LEVELS = {"high", "medium", "low"}
EVIDENCE_COVERAGE_LEVELS = {
    "end-to-end",
    "enforcement-layer",
    "scoped-search",
    "partial",
}
QUESTION_REQUIRED = {"conflict", "code-only", "unknown"}
REQUIREMENT_REQUIRED = {"aligned", "conflict", "prd-only"}
OBSERVED_REQUIRED = {"aligned", "conflict", "code-only"}
INTENDED_REQUIRED = {"aligned", "conflict", "prd-only"}
EVIDENCE_REQUIRED = {"aligned", "conflict", "code-only"}
EXPECTED_HANDOFFS = {
    "aligned": {"none", "testspec-analysis"},
    "conflict": {"product-confirmation"},
    "code-only": {"product-confirmation"},
    "prd-only": {"testspec-analysis"},
    "unknown": {"product-confirmation"},
}
FINDING_ID_PATTERN = re.compile(r"^CAL-\d{3}$")
REQUIREMENT_PATTERN = re.compile(r"^(?:REQ|AC)-[A-Za-z0-9_-]+$")
QUESTION_PATTERN = re.compile(r"^Q-[A-Za-z0-9_-]+$")
DRAFT_REF_PATTERN = re.compile(r"^OBS-\d{3}$")
LINE_PATTERN = re.compile(r"^\d+(?:-\d+)?$")
LABEL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
COMMIT_PATTERN = re.compile(r"^(?:[0-9a-fA-F]{7,64}|unavailable)$")
ABSOLUTE_HOME_PATTERN = re.compile(r"(?:/Users/|/home/|[A-Za-z]:\\Users\\)")
LOCAL_ABSOLUTE_PATTERN = re.compile(
    r"(?:^|[\s\"'`(])(?:/(?:tmp|private|var|etc|opt|usr|root|workspace|mnt|Volumes)/|[A-Za-z]:\\)"
)
URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
EMAIL_PATTERN = re.compile(
    r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
    re.IGNORECASE,
)
IPV4_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
UUID_PATTERN = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-"
    r"[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)
PRIVATE_PATH_MARKERS = (".cursor/projects", "agent-transcripts")
SECRET_PATTERN = re.compile(
    r"\b(?:sk|ghp|github_pat|xox[baprs])[-_][A-Za-z0-9_-]{12,}\b"
)
CONTEXT_PATTERN = re.compile(
    r"<!--\s*testspec-context\s*(\{.*?\})\s*-->",
    re.DOTALL,
)


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path.name}: top level must be an object")
    return data


def sha256_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def validate_change_snapshot_data(data: dict[str, Any]) -> list[str]:
    script = Path(__file__).with_name("validate_change_snapshot.py")
    spec = importlib.util.spec_from_file_location(
        "testspec_validate_change_snapshot",
        script,
    )
    if spec is None or spec.loader is None:
        return ["cannot load change snapshot validator"]
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return list(module.validate(data))


def markdown_context(path: Path) -> dict[str, Any] | None:
    matches = CONTEXT_PATTERN.findall(path.read_text(encoding="utf-8"))
    if not matches:
        return None
    value = json.loads(matches[-1])
    return value if isinstance(value, dict) else None


def safe_relative_path(value: Any, *, allow_root: bool = False) -> bool:
    if not isinstance(value, str) or not value or value == "..":
        return False
    if value == ".":
        return allow_root
    if "\\" in value or "://" in value or value.startswith(("/", "~")):
        return False
    path = PurePosixPath(value)
    return (
        bool(path.parts)
        and not value.endswith("/")
        and not path.is_absolute()
        and ".." not in path.parts
    )


def path_within_scope(path: str, scopes: list[str]) -> bool:
    return any(
        scope == "."
        or path == scope
        or path.startswith(scope.rstrip("/") + "/")
        for scope in scopes
    )


def nonempty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def valid_line_span(value: Any) -> bool:
    if not isinstance(value, str) or not LINE_PATTERN.fullmatch(value):
        return False
    start, *rest = (int(part) for part in value.split("-"))
    end = rest[0] if rest else start
    return start >= 1 and end >= start


def reject_unknown_keys(
    value: dict[str, Any],
    allowed: set[str],
    prefix: str,
    errors: list[str],
) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        errors.append(f"{prefix} contains unsupported fields: {', '.join(unknown)}")


def privacy_errors(strings: Any, source: str) -> list[str]:
    errors: list[str] = []
    for value in strings:
        if (
            ABSOLUTE_HOME_PATTERN.search(value)
            or LOCAL_ABSOLUTE_PATTERN.search(value)
            or value.startswith("file://")
        ):
            errors.append(f"{source} contains a private absolute path")
        if URL_PATTERN.search(value):
            errors.append(f"{source} contains a remote URL")
        if EMAIL_PATTERN.search(value):
            errors.append(f"{source} contains an email address")
        if IPV4_PATTERN.search(value):
            errors.append(f"{source} contains an IPv4 address")
        if UUID_PATTERN.search(value):
            errors.append(f"{source} contains a UUID-like identifier")
        if any(marker in value for marker in PRIVATE_PATH_MARKERS):
            errors.append(f"{source} contains a private workspace identifier")
        if SECRET_PATTERN.search(value):
            errors.append(f"{source} contains a secret-like token")
    return list(dict.fromkeys(errors))


def validate(
    data: dict[str, Any],
    canonical_path: Path | None = None,
    draft_path: Path | None = None,
    snapshot_path: Path | None = None,
) -> list[str]:
    errors: list[str] = []
    reject_unknown_keys(
        data,
        {
            "schema_version",
            "_context",
            "summary",
            "questions",
            "findings",
            "change_trace",
        },
        "artifact",
        errors,
    )
    if data.get("schema_version") != 1:
        errors.append("schema_version must be 1")

    context = data.get("_context")
    if not isinstance(context, dict):
        return errors + ["_context must be an object"]
    reject_unknown_keys(
        context,
        {
            "source_skill",
            "canonical_source_policy",
            "mode",
            "authority",
            "canonical_source_path",
            "canonical_source_digest",
            "source_revision",
            "recovered_prd_draft",
            "recovered_prd_draft_digest",
            "code_evidence",
            "change_snapshot",
            "canonical_mutation_performed",
            "status",
        },
        "_context",
        errors,
    )
    required_context = {
        "source_skill": "testspec-code-calibrate",
        "canonical_source_policy": "prd-first",
        "authority": "reference",
        "canonical_mutation_performed": False,
    }
    for field, expected in required_context.items():
        if context.get(field) != expected:
            errors.append(f"_context.{field} must be {expected!r}")
    if "review_gate" in context:
        errors.append("_context must not contain review_gate")
    if "testcases" in data:
        errors.append("calibration artifact must not contain testcases")

    mode = context.get("mode")
    if not isinstance(mode, str) or mode not in MODES:
        errors.append("_context.mode must be comparison, recovery, or change-diff")

    code_evidence = context.get("code_evidence")
    scopes: list[str] = []
    code_role: str | None = None
    if not isinstance(code_evidence, dict):
        errors.append("_context.code_evidence must be an object")
    else:
        reject_unknown_keys(
            code_evidence,
            {
                "role",
                "repository_label",
                "ref",
                "commit",
                "snapshot_reason",
                "scope",
            },
            "_context.code_evidence",
            errors,
        )
        role = code_evidence.get("role")
        if not isinstance(role, str) or role not in CODE_ROLES:
            errors.append("_context.code_evidence.role is invalid")
        else:
            code_role = role
        label = code_evidence.get("repository_label")
        if not isinstance(label, str) or not LABEL_PATTERN.fullmatch(label):
            errors.append(
                "_context.code_evidence.repository_label must be a non-sensitive label"
            )
        ref = code_evidence.get("ref")
        commit = code_evidence.get("commit")
        if (
            not isinstance(ref, str)
            or not ref
            or "\n" in ref
            or "\r" in ref
            or "://" in ref
            or ABSOLUTE_HOME_PATTERN.search(ref)
        ):
            errors.append(
                "_context.code_evidence.ref must be a non-sensitive branch/tag/ref or unavailable"
            )
        if not isinstance(commit, str) or not COMMIT_PATTERN.fullmatch(commit):
            errors.append(
                "_context.code_evidence.commit must be a Git hash or unavailable"
            )
        if (
            (ref == "unavailable" or commit == "unavailable")
            and not nonempty_text(code_evidence.get("snapshot_reason"))
        ):
            errors.append(
                "_context.code_evidence.snapshot_reason is required for unavailable snapshot fields"
            )
        raw_scopes = code_evidence.get("scope")
        if not isinstance(raw_scopes, list) or not raw_scopes:
            errors.append("_context.code_evidence.scope must be a non-empty array")
        else:
            for scope in raw_scopes:
                if not safe_relative_path(scope, allow_root=True):
                    errors.append(f"unsafe code scope path: {scope!r}")
                else:
                    scopes.append(scope)
            if len(set(scopes)) != len(scopes):
                errors.append("_context.code_evidence.scope contains duplicates")
            if "." in scopes and len(scopes) > 1:
                errors.append(
                    "_context.code_evidence.scope must not combine root with narrower paths"
                )

    snapshot_data: dict[str, Any] | None = None
    changed_paths: set[str] = set()
    if mode == "comparison" or mode == "change-diff":
        if draft_path is not None:
            errors.append(f"{mode} mode must not use --draft")
        for forbidden in ("recovered_prd_draft",):
            if forbidden in context:
                errors.append(f"{mode} mode must not contain {forbidden}")
        if "recovered_prd_draft_digest" in context:
            errors.append(
                f"{mode} mode must not contain recovered_prd_draft_digest"
            )
        revision = context.get("source_revision")
        if (
            not isinstance(revision, dict)
            or type(revision.get("version")) is not int
            or revision["version"] < 1
            or not nonempty_text(revision.get("summary"))
            or not nonempty_text(revision.get("updated_by_skill"))
        ):
            errors.append(
                f"{mode} mode requires a complete versioned source_revision"
            )
        source_path = context.get("canonical_source_path")
        if (
            not isinstance(source_path, str)
            or source_path not in {"requirements.md", "proposal.md"}
        ):
            errors.append(
                f"{mode} mode canonical_source_path must be requirements.md or proposal.md"
            )
        digest = context.get("canonical_source_digest")
        if not isinstance(digest, str) or not SHA256_PATTERN.fullmatch(digest):
            errors.append(f"{mode} mode requires canonical_source_digest")
        if canonical_path is None:
            errors.append(f"{mode} mode requires --canonical")
        elif not canonical_path.is_file():
            errors.append("canonical file does not exist")
        else:
            if canonical_path.name != source_path:
                errors.append(
                    "canonical_source_path does not match the --canonical file"
                )
            if isinstance(digest, str) and digest != sha256_digest(canonical_path):
                errors.append("canonical source digest changed during calibration")
            try:
                canonical_context = markdown_context(canonical_path)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                errors.append(f"cannot parse canonical context: {exc}")
            else:
                if canonical_context is None:
                    errors.append("canonical file lacks testspec-context")
                else:
                    if canonical_context.get("source_revision") != revision:
                        errors.append("source_revision does not match canonical file")
                    if canonical_context.get(
                        "canonical_source_policy",
                        "prd-first",
                    ) != "prd-first":
                        errors.append(
                            "canonical file policy must remain prd-first"
                        )
        if mode == "comparison":
            if "change_snapshot" in context:
                errors.append("comparison mode must not contain change_snapshot")
            if "change_trace" in data:
                errors.append("comparison mode must not contain change_trace")
            if snapshot_path is not None:
                errors.append("comparison mode must not use --snapshot")
        else:
            if code_role != "change-evidence":
                errors.append("change-diff mode requires code_evidence.role=change-evidence")
            change_snapshot = context.get("change_snapshot")
            if not isinstance(change_snapshot, dict):
                errors.append("change-diff mode requires _context.change_snapshot")
                change_snapshot = {}
            else:
                reject_unknown_keys(
                    change_snapshot,
                    {"path", "digest", "snapshot_id"},
                    "_context.change_snapshot",
                    errors,
                )
            if change_snapshot.get("path") != "artifacts/change-snapshot.json":
                errors.append(
                    "change-diff snapshot path must be artifacts/change-snapshot.json"
                )
            snapshot_digest = change_snapshot.get("digest")
            if (
                not isinstance(snapshot_digest, str)
                or not SHA256_PATTERN.fullmatch(snapshot_digest)
            ):
                errors.append("change-diff snapshot digest must be sha256")
            if not nonempty_text(change_snapshot.get("snapshot_id")):
                errors.append("change-diff snapshot_id is required")
            if snapshot_path is None:
                errors.append("change-diff mode requires --snapshot")
            elif not snapshot_path.is_file():
                errors.append("change snapshot does not exist")
            else:
                try:
                    snapshot_data = read_json(snapshot_path)
                except (OSError, ValueError, json.JSONDecodeError) as exc:
                    errors.append(f"cannot parse change snapshot: {exc}")
                else:
                    errors.extend(
                        f"change snapshot: {error}"
                        for error in validate_change_snapshot_data(snapshot_data)
                    )
                    if (
                        isinstance(snapshot_digest, str)
                        and snapshot_digest != sha256_digest(snapshot_path)
                    ):
                        errors.append("change snapshot digest does not match artifact")
                    if change_snapshot.get("snapshot_id") != snapshot_data.get("snapshot_id"):
                        errors.append("change snapshot_id does not match artifact")
                    snapshot_files = snapshot_data.get("files")
                    if isinstance(snapshot_files, list):
                        changed_paths = {
                            str(item.get("path"))
                            for item in snapshot_files
                            if isinstance(item, dict) and nonempty_text(item.get("path"))
                        }
                    comparison = snapshot_data.get("comparison")
                    if not isinstance(comparison, dict):
                        errors.append("change snapshot comparison must be an object")
                        comparison = {}
                    if isinstance(code_evidence, dict):
                        if (
                            code_evidence.get("repository_label")
                            != snapshot_data.get("repository_label")
                        ):
                            errors.append(
                                "code_evidence repository_label does not match change snapshot"
                            )
                        if code_evidence.get("scope") != snapshot_data.get("scope"):
                            errors.append("code_evidence scope does not match change snapshot")
                        if code_evidence.get("commit") != comparison.get("head_commit"):
                            errors.append("code_evidence commit does not match change snapshot")
                        if code_evidence.get("ref") != comparison.get("head_label"):
                            errors.append("code_evidence ref must use the safe snapshot head_label")
            change_trace = data.get("change_trace")
            if not isinstance(change_trace, dict):
                errors.append("change-diff mode requires change_trace")
            else:
                reject_unknown_keys(
                    change_trace,
                    {"candidate_strategy", "data_quality_notes", "unmapped_changes"},
                    "change_trace",
                    errors,
                )
                if change_trace.get("candidate_strategy") != "keyword-hints-only":
                    errors.append(
                        "change_trace.candidate_strategy must be keyword-hints-only"
                    )
                notes = change_trace.get("data_quality_notes")
                if not isinstance(notes, list) or any(
                    not nonempty_text(item) for item in notes
                ):
                    errors.append(
                        "change_trace.data_quality_notes must be an array of non-empty strings"
                    )
                unmapped = change_trace.get("unmapped_changes")
                if not isinstance(unmapped, list):
                    errors.append("change_trace.unmapped_changes must be an array")
                else:
                    seen_unmapped: set[str] = set()
                    for unmapped_index, item in enumerate(unmapped):
                        prefix = f"change_trace.unmapped_changes[{unmapped_index}]"
                        if not isinstance(item, dict):
                            errors.append(f"{prefix} must be an object")
                            continue
                        reject_unknown_keys(item, {"path", "reason"}, prefix, errors)
                        path = item.get("path")
                        if not safe_relative_path(path):
                            errors.append(f"{prefix}.path must be repository-relative")
                        elif path not in changed_paths:
                            errors.append(f"{prefix}.path is not present in the change snapshot")
                        elif path in seen_unmapped:
                            errors.append(f"{prefix}.path is duplicated")
                        else:
                            seen_unmapped.add(path)
                        if not nonempty_text(item.get("reason")):
                            errors.append(f"{prefix}.reason is required")
    elif mode == "recovery":
        if snapshot_path is not None:
            errors.append("recovery mode must not use --snapshot")
        if "change_snapshot" in context:
            errors.append("recovery mode must not contain change_snapshot")
        if "change_trace" in data:
            errors.append("recovery mode must not contain change_trace")
        if canonical_path is not None:
            errors.append("recovery mode must not use --canonical")
        for forbidden in (
            "source_revision",
            "canonical_source_path",
            "canonical_source_digest",
        ):
            if forbidden in context:
                errors.append(f"recovery mode must not contain {forbidden}")
        if context.get("recovered_prd_draft") != "artifacts/recovered-prd-draft.md":
            errors.append(
                "recovery mode requires recovered_prd_draft=artifacts/recovered-prd-draft.md"
            )
        draft_digest = context.get("recovered_prd_draft_digest")
        if not isinstance(draft_digest, str) or not SHA256_PATTERN.fullmatch(
            draft_digest
        ):
            errors.append("recovery mode requires recovered_prd_draft_digest")
        if draft_path is None:
            errors.append("recovery mode requires --draft")
        elif not draft_path.is_file():
            errors.append("recovery draft does not exist")
        else:
            draft_text = draft_path.read_text(encoding="utf-8")
            has_english_noncanonical_marker = (
                "Observed implementation draft" in draft_text
                and "not canonical" in draft_text
            )
            has_chinese_noncanonical_marker = (
                "可观察实现草稿" in draft_text
                and "不是 canonical" in draft_text
            )
            if not (
                has_english_noncanonical_marker
                or has_chinese_noncanonical_marker
            ):
                errors.append("recovery draft must be visibly marked not canonical")
            if (
                isinstance(draft_digest, str)
                and draft_digest != sha256_digest(draft_path)
            ):
                errors.append("recovery draft digest does not match artifact")
            if isinstance(code_evidence, dict):
                snapshot_scopes = code_evidence.get("scope")
                if not isinstance(snapshot_scopes, list):
                    snapshot_scopes = []
                snapshot_values = [
                    code_evidence.get("repository_label"),
                    code_evidence.get("ref"),
                    code_evidence.get("commit"),
                    *snapshot_scopes,
                ]
                for snapshot_value in snapshot_values:
                    if (
                        isinstance(snapshot_value, str)
                        and snapshot_value not in draft_text
                    ):
                        errors.append(
                            "recovery draft does not match code_evidence snapshot"
                        )
                        break
            errors.extend(privacy_errors([draft_text], "recovery draft"))

    questions = data.get("questions")
    question_by_id: dict[str, dict[str, Any]] = {}
    if not isinstance(questions, list):
        errors.append("questions must be an array")
        questions = []
    for question_index, question in enumerate(questions):
        question_prefix = f"questions[{question_index}]"
        if not isinstance(question, dict):
            errors.append(f"{question_prefix} must be an object")
            continue
        reject_unknown_keys(
            question,
            {"id", "question", "status", "blocking", "finding_refs"},
            question_prefix,
            errors,
        )
        question_id = question.get("id")
        if not isinstance(question_id, str) or not QUESTION_PATTERN.fullmatch(question_id):
            errors.append(f"{question_prefix}.id must match Q-*")
        elif question_id in question_by_id:
            errors.append(f"{question_prefix}.id is duplicated")
        else:
            question_by_id[question_id] = question
        if not nonempty_text(question.get("question")):
            errors.append(f"{question_prefix}.question must be non-empty")
        if question.get("status") != "open":
            errors.append(f"{question_prefix}.status must be open")
        if question.get("blocking") is not True:
            errors.append(f"{question_prefix}.blocking must be true")
        finding_refs = question.get("finding_refs")
        if not isinstance(finding_refs, list) or not finding_refs:
            errors.append(f"{question_prefix}.finding_refs must be a non-empty array")
        elif any(
            not isinstance(ref, str) or not FINDING_ID_PATTERN.fullmatch(ref)
            for ref in finding_refs
        ):
            errors.append(f"{question_prefix} has invalid finding refs")
        elif len(set(finding_refs)) != len(finding_refs):
            errors.append(f"{question_prefix}.finding_refs contains duplicates")

    findings = data.get("findings")
    if not isinstance(findings, list):
        return errors + ["findings must be an array"]
    if not findings:
        errors.append("findings must contain at least one calibration result")

    counts: Counter[str] = Counter()
    seen_ids: set[str] = set()
    finding_question_refs: dict[str, set[str]] = {}
    recovery_draft_refs: set[str] = set()
    for index, finding in enumerate(findings):
        prefix = f"findings[{index}]"
        if not isinstance(finding, dict):
            errors.append(f"{prefix} must be an object")
            continue
        reject_unknown_keys(
            finding,
            {
                "id",
                "classification",
                "draft_ref",
                "requirement_refs",
                "intended_behavior",
                "observed_behavior",
                "reason",
                "evidence",
                "evidence_coverage",
                "confidence",
                "question_refs",
                "recommended_handoff",
                "change_trace_status",
            },
            prefix,
            errors,
        )
        finding_id = finding.get("id")
        if not isinstance(finding_id, str) or not FINDING_ID_PATTERN.fullmatch(finding_id):
            errors.append(f"{prefix}.id must match CAL-NNN")
        elif finding_id in seen_ids:
            errors.append(f"{prefix}.id is duplicated")
        else:
            seen_ids.add(finding_id)

        classification = finding.get("classification")
        if (
            not isinstance(classification, str)
            or classification not in CLASSIFICATIONS
        ):
            errors.append(f"{prefix}.classification is invalid")
            continue
        counts[classification] += 1
        if mode == "recovery" and classification not in {"code-only", "unknown"}:
            errors.append(
                f"{prefix}: recovery mode permits only code-only or unknown"
            )
        change_trace_status = finding.get("change_trace_status")
        if mode == "change-diff":
            if (
                not isinstance(change_trace_status, str)
                or change_trace_status not in CHANGE_TRACE_STATUSES
            ):
                errors.append(f"{prefix}.change_trace_status is invalid")
            elif change_trace_status == "matched" and classification not in {
                "aligned",
                "code-only",
            }:
                errors.append(
                    f"{prefix}: matched requires aligned or code-only classification"
                )
            elif change_trace_status == "deviation" and classification != "conflict":
                errors.append(
                    f"{prefix}: deviation requires conflict classification"
                )
            elif (
                change_trace_status in {"partial", "not-observed", "unknown"}
                and classification != "unknown"
            ):
                errors.append(
                    f"{prefix}: {change_trace_status} requires unknown classification"
                )
            if classification == "prd-only":
                errors.append(
                    f"{prefix}: change-diff must not infer prd-only from diff absence"
                )
        elif "change_trace_status" in finding:
            errors.append(
                f"{prefix}.change_trace_status is only allowed in change-diff mode"
            )
        draft_ref = finding.get("draft_ref")
        if mode == "recovery":
            if not isinstance(draft_ref, str) or not DRAFT_REF_PATTERN.fullmatch(draft_ref):
                errors.append(f"{prefix}.draft_ref must match OBS-NNN in recovery mode")
            elif draft_ref in recovery_draft_refs:
                errors.append(f"{prefix}.draft_ref is duplicated")
            else:
                recovery_draft_refs.add(draft_ref)
        elif "draft_ref" in finding:
            errors.append(f"{prefix}.draft_ref is only allowed in recovery mode")

        requirement_refs = finding.get("requirement_refs")
        if not isinstance(requirement_refs, list):
            errors.append(f"{prefix}.requirement_refs must be an array")
            requirement_refs = []
        invalid_requirements = [
            str(ref)
            for ref in requirement_refs
            if not REQUIREMENT_PATTERN.fullmatch(str(ref))
        ]
        if invalid_requirements:
            errors.append(f"{prefix} has invalid requirement refs")
        if classification in REQUIREMENT_REQUIRED and not requirement_refs:
            errors.append(f"{prefix}: {classification} requires REQ/AC refs")
        if classification == "code-only" and requirement_refs:
            errors.append(f"{prefix}: code-only must not contain requirement refs")

        intended = finding.get("intended_behavior")
        observed = finding.get("observed_behavior")
        if classification in INTENDED_REQUIRED and not nonempty_text(intended):
            errors.append(f"{prefix}: {classification} requires intended_behavior")
        if classification in OBSERVED_REQUIRED and not nonempty_text(observed):
            errors.append(f"{prefix}: {classification} requires observed_behavior")
        if classification == "code-only" and nonempty_text(intended):
            errors.append(f"{prefix}: code-only must not contain intended_behavior")
        if classification == "prd-only" and nonempty_text(observed):
            errors.append(f"{prefix}: prd-only must not contain observed_behavior")
        if classification == "unknown" and not nonempty_text(finding.get("reason")):
            errors.append(f"{prefix}: unknown requires reason")

        evidence = finding.get("evidence")
        if not isinstance(evidence, list):
            errors.append(f"{prefix}.evidence must be an array")
            evidence = []
        if classification in EVIDENCE_REQUIRED and not evidence:
            errors.append(f"{prefix}: {classification} requires evidence")
        evidence_sources: set[str] = set()
        evidence_layers: set[str] = set()
        for evidence_index, item in enumerate(evidence):
            evidence_prefix = f"{prefix}.evidence[{evidence_index}]"
            if not isinstance(item, dict):
                errors.append(f"{evidence_prefix} must be an object")
                continue
            reject_unknown_keys(
                item,
                {"path", "symbol", "lines", "observation", "source", "layer"},
                evidence_prefix,
                errors,
            )
            evidence_path = item.get("path")
            if not safe_relative_path(evidence_path):
                errors.append(f"{evidence_prefix}.path must be repository-relative")
            elif scopes and not path_within_scope(evidence_path, scopes):
                errors.append(f"{evidence_prefix}.path is outside authorized scope")
            if not nonempty_text(item.get("symbol")):
                errors.append(f"{evidence_prefix}.symbol is required")
            lines = item.get("lines")
            if not valid_line_span(lines):
                errors.append(
                    f"{evidence_prefix}.lines must be a positive N or ascending N-N"
                )
            if not nonempty_text(item.get("observation")):
                errors.append(f"{evidence_prefix}.observation is required")
            source = item.get("source")
            layer = item.get("layer")
            if mode == "change-diff":
                if source not in EVIDENCE_SOURCES:
                    errors.append(f"{evidence_prefix}.source is invalid")
                else:
                    evidence_sources.add(source)
                    if source == "diff" and evidence_path not in changed_paths:
                        errors.append(
                            f"{evidence_prefix}.path is not present in the change snapshot"
                        )
                if layer not in EVIDENCE_LAYERS:
                    errors.append(f"{evidence_prefix}.layer is invalid")
                else:
                    evidence_layers.add(layer)
            else:
                if source is not None and source not in EVIDENCE_SOURCES:
                    errors.append(f"{evidence_prefix}.source is invalid")
                if layer is not None and layer not in EVIDENCE_LAYERS:
                    errors.append(f"{evidence_prefix}.layer is invalid")

        evidence_coverage = finding.get("evidence_coverage")
        if (
            not isinstance(evidence_coverage, str)
            or evidence_coverage not in EVIDENCE_COVERAGE_LEVELS
        ):
            errors.append(f"{prefix}.evidence_coverage is invalid")
        if (
            classification in {"aligned", "conflict"}
            and evidence_coverage not in {"end-to-end", "enforcement-layer"}
        ):
            errors.append(
                f"{prefix}: {classification} requires end-to-end or enforcement-layer coverage"
            )
        if classification == "prd-only" and evidence_coverage != "scoped-search":
            errors.append(f"{prefix}: prd-only requires scoped-search coverage")
        if mode == "change-diff":
            if change_trace_status in {"matched", "deviation"} and "diff" not in evidence_sources:
                errors.append(
                    f"{prefix}: {change_trace_status} requires at least one diff evidence item"
                )
            if (
                change_trace_status == "matched"
                and evidence_coverage not in {"end-to-end", "enforcement-layer"}
            ):
                errors.append(
                    f"{prefix}: matched requires end-to-end or enforcement-layer coverage"
                )
            if (
                evidence_coverage == "end-to-end"
                and len(evidence_layers) < 2
            ):
                errors.append(
                    f"{prefix}: end-to-end change evidence requires at least two layers"
                )

        confidence = finding.get("confidence")
        if not isinstance(confidence, str) or confidence not in CONFIDENCE_LEVELS:
            errors.append(f"{prefix}.confidence is invalid")
        if classification == "aligned" and confidence == "low":
            errors.append(f"{prefix}: aligned cannot use low confidence")
        if mode == "change-diff" and (
            change_trace_status in {"partial", "not-observed"}
            and confidence == "high"
        ):
            errors.append(
                f"{prefix}: {change_trace_status} cannot use high confidence"
            )

        question_refs = finding.get("question_refs")
        if not isinstance(question_refs, list):
            errors.append(f"{prefix}.question_refs must be an array")
            question_refs = []
        if any(not QUESTION_PATTERN.fullmatch(str(ref)) for ref in question_refs):
            errors.append(f"{prefix} has invalid question refs")
        elif len(set(question_refs)) != len(question_refs):
            errors.append(f"{prefix}.question_refs contains duplicates")
        if classification in QUESTION_REQUIRED and not question_refs:
            errors.append(f"{prefix}: {classification} requires Q-* refs")
        if classification not in QUESTION_REQUIRED and question_refs:
            errors.append(f"{prefix}: {classification} must not register blocking questions")
        if isinstance(finding_id, str):
            finding_question_refs[finding_id] = {
                str(ref) for ref in question_refs
            }
        for question_ref in question_refs:
            if not isinstance(question_ref, str):
                continue
            if question_ref not in question_by_id:
                errors.append(
                    f"{prefix}: question ref {question_ref!r} is not declared"
                )

        handoff = finding.get("recommended_handoff")
        if (
            not isinstance(handoff, str)
            or handoff not in EXPECTED_HANDOFFS[classification]
        ):
            errors.append(f"{prefix}.recommended_handoff is invalid for {classification}")

    for question_id, question in question_by_id.items():
        raw_finding_refs = question.get("finding_refs")
        if (
            not isinstance(raw_finding_refs, list)
            or any(not isinstance(ref, str) for ref in raw_finding_refs)
        ):
            continue
        for finding_ref in raw_finding_refs:
            if finding_ref not in seen_ids:
                errors.append(
                    f"question {question_id!r} references unknown finding {finding_ref!r}"
                )
            elif question_id not in finding_question_refs.get(finding_ref, set()):
                errors.append(
                    f"question {question_id!r} is not linked back from {finding_ref!r}"
                )
        linked_findings = {
            finding_id
            for finding_id, refs in finding_question_refs.items()
            if question_id in refs
        }
        if linked_findings != set(raw_finding_refs):
            errors.append(
                f"question {question_id!r} finding_refs do not match finding links"
            )

    summary = data.get("summary")
    expected_summary = {
        "total": len(findings),
        **{name: counts.get(name, 0) for name in sorted(CLASSIFICATIONS)},
    }
    if not isinstance(summary, dict):
        errors.append("summary must be an object")
    elif summary != expected_summary:
        errors.append("summary does not match findings")

    requires_confirmation = any(
        counts.get(name, 0) for name in QUESTION_REQUIRED
    )
    expected_status = (
        "needs-product-confirmation"
        if mode == "recovery" or requires_confirmation
        else "ready-for-analysis"
    )
    if context.get("status") != expected_status:
        errors.append(f"_context.status must be {expected_status}")

    if mode == "recovery" and draft_path is not None and draft_path.is_file():
        draft_text = draft_path.read_text(encoding="utf-8")
        required_sections = (
            ("## Snapshot", "## 快照"),
            ("## Observed behaviors", "## 可观察行为"),
            ("## Product confirmation required", "## 必需的产品确认"),
        )
        for section_aliases in required_sections:
            if not any(section in draft_text for section in section_aliases):
                errors.append(
                    "recovery draft is missing section: "
                    + " or ".join(section_aliases)
                )
        for draft_ref in recovery_draft_refs:
            if draft_ref not in draft_text:
                errors.append(f"recovery draft is missing {draft_ref}")
        for question_id in question_by_id:
            if question_id not in draft_text:
                errors.append(f"recovery draft is missing {question_id}")

    errors.extend(privacy_errors(iter_strings(data), "artifact"))
    return list(dict.fromkeys(errors))


def iter_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from iter_strings(key)
            yield from iter_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from iter_strings(item)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--canonical", type=Path)
    parser.add_argument("--draft", type=Path)
    parser.add_argument("--snapshot", type=Path)
    args = parser.parse_args()

    try:
        data = read_json(args.input)
        errors = validate(data, args.canonical, args.draft, args.snapshot)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors = [str(exc)]

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    if data["_context"]["mode"] == "recovery":
        print("PASS: recovery calibration artifact and draft are valid")
    elif data["_context"]["mode"] == "change-diff":
        print(
            "PASS: change-diff calibration, snapshot, and canonical source are valid"
        )
    else:
        print(
            "PASS: code calibration artifact is valid and canonical source is unchanged"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
