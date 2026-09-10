"""Validate optional review repair receipts; no artifact mutation or issue closure."""
from __future__ import annotations

import hashlib
from pathlib import Path


CHANGE_FIELDS = {
    "analysis": "changed_requirement_refs",
    "points": "changed_tp_ids",
    "generate": "changed_case_ids",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def strings(value):
    return (isinstance(value, list) and bool(value)
            and all(isinstance(item, str) and item.strip() for item in value)
            and len(value) == len(set(value)))


def validate_feedback(review):
    """Check structured feedback without interpreting prose or accepting waivers."""
    seen = {}
    for stage in CHANGE_FIELDS:
        findings = review.get("feedback_for_" + stage, [])
        require(isinstance(findings, list), "feedback must be an array")
        for finding in findings:
            require(isinstance(finding, dict), "structured review feedback required")
            issue_id = finding.get("issue_id")
            require(isinstance(issue_id, str) and issue_id.strip(), "finding issue_id required")
            require(issue_id not in seen, "duplicate issue_id across feedback routes")
            seen[issue_id] = finding
            require(finding.get("target_stage") == stage, "finding feedback route mismatch")
            require(finding.get("status") in ("open", "resolved", "accepted"), "invalid finding status")
            require(finding.get("severity") in ("S1", "S2", "S3"), "finding severity required")
            require(strings(finding.get("scope")), "finding scope required")
            require(isinstance(finding.get("action"), str) and finding["action"].strip(), "finding action required")
            if finding["status"] != "open":
                require(isinstance(finding.get("resolution"), str) and finding["resolution"].strip(), "closed finding requires resolution evidence or acceptance decision")
    return seen


def validate_receipts(change_dir, context, stage, load_context):
    """Legacy generate receipts remain readable; new upstream repairs are strict."""
    if "review_repairs" not in context:
        return []
    errors = []
    try:
        receipts = context["review_repairs"]
        require(stage in CHANGE_FIELDS, "review_repairs belong only to the repairing stage")
        require(isinstance(receipts, list) and bool(receipts), "review_repairs must be nonempty")
        seen = set()
        for receipt in receipts:
            require(isinstance(receipt, dict), "repair receipt must be an object")
            issue_id = receipt.get("issue_id")
            require(isinstance(issue_id, str) and bool(issue_id.strip()), "repair issue_id required")
            # Existing generate-only records predate snapshot binding.
            if stage == "generate" and "source_review" not in receipt:
                require(strings(receipt.get("changed_case_ids")), "changed_case_ids required")
                continue
            require(receipt.get("target_stage") == stage, "repair target_stage mismatch")
            require(strings(receipt.get(CHANGE_FIELDS[stage])), f"{CHANGE_FIELDS[stage]} required")
            require(isinstance(receipt.get("summary"), str) and receipt["summary"].strip(), "repair summary required")
            reference = receipt.get("source_review")
            require(isinstance(reference, dict), "source_review required")
            name = reference.get("path")
            require(isinstance(name, str) and not Path(name).is_absolute(), "relative review snapshot path required")
            snapshot = (change_dir / name).resolve()
            archive = (change_dir / "artifacts" / "reviews").resolve()
            require(archive.is_relative_to(change_dir.resolve()) and snapshot.is_relative_to(archive), "review snapshot must be inside artifacts/reviews")
            require(snapshot.is_file(), "review snapshot missing")
            require(snapshot.suffix == ".md", "review snapshot must be Markdown")
            require(sha256(snapshot) == reference.get("sha256"), "review snapshot hash mismatch")
            key = (reference["sha256"], issue_id)
            require(key not in seen, "duplicate repair receipt")
            seen.add(key)
            review = load_context(snapshot)
            require(type(review.get("context_schema_version")) is int and review["context_schema_version"] == 2,
                    "review snapshot requires context schema v2")
            require(review.get("source_skill") == "testspec-review", "snapshot is not a review")
            require(review.get("source_revision") == context.get("source_revision"), "repair review revision mismatch")
            validate_feedback(review)
            findings = review.get("feedback_for_" + stage)
            require(isinstance(findings, list), "structured review feedback required")
            matches = [item for item in findings if isinstance(item, dict) and item.get("issue_id") == issue_id]
            require(len(matches) == 1, "repair issue missing or duplicated in assigned feedback")
            finding = matches[0]
            require(finding.get("status") == "open" and finding.get("target_stage") == stage, "only assigned open findings can be repaired")
            scope = finding.get("scope")
            changed = receipt[CHANGE_FIELDS[stage]]
            require(any(item.startswith("GLOBAL:") for item in scope) or set(changed) <= set(scope), "repair changes outside assigned scope")
    except (OSError, ValueError, TypeError, KeyError) as exc:
        errors.append(f"{stage}: {exc}")
    return errors
