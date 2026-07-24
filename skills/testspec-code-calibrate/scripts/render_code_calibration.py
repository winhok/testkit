#!/usr/bin/env python3
"""Render a concise, snippet-free Markdown view of code-calibration JSON."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def cell(value: Any) -> str:
    return str(value or "—").replace("|", "\\|").replace("\n", " ")


def evidence_locator(items: Any) -> str:
    if not isinstance(items, list) or not items:
        return "—"
    locators: list[str] = []
    for item in items[:3]:
        if not isinstance(item, dict):
            continue
        source = f"[{item.get('source')}]" if item.get("source") else ""
        locators.append(
            f"{source}{item.get('path', '?')}:{item.get('symbol', '?')}:{item.get('lines', '?')}"
        )
    return "; ".join(locators) or "—"


def render(data: dict[str, Any]) -> str:
    context = data.get("_context") if isinstance(data.get("_context"), dict) else {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    findings = data.get("findings") if isinstance(data.get("findings"), list) else []
    questions = data.get("questions") if isinstance(data.get("questions"), list) else []
    lines = [
        "# TestSpec code calibration",
        "",
        f"- Mode: `{cell(context.get('mode'))}`",
        f"- Status: `{cell(context.get('status'))}`",
        f"- Canonical policy: `{cell(context.get('canonical_source_policy'))}`",
        f"- Findings: {cell(summary.get('total', len(findings)))}",
        "",
        "## Summary",
        "",
        "| aligned | conflict | code-only | prd-only | unknown |",
        "|---:|---:|---:|---:|---:|",
        "| {aligned} | {conflict} | {code_only} | {prd_only} | {unknown} |".format(
            aligned=summary.get("aligned", 0),
            conflict=summary.get("conflict", 0),
            code_only=summary.get("code-only", 0),
            prd_only=summary.get("prd-only", 0),
            unknown=summary.get("unknown", 0),
        ),
        "",
        "## Findings",
        "",
        "| ID | Classification | Change trace | Confidence | Requirement | Evidence locator |",
        "|---|---|---|---|---|---|",
    ]
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        refs = finding.get("requirement_refs")
        if not isinstance(refs, list):
            refs = []
        lines.append(
            "| {id} | {classification} | {trace} | {confidence} | {refs} | {evidence} |".format(
                id=cell(finding.get("id")),
                classification=cell(finding.get("classification")),
                trace=cell(finding.get("change_trace_status")),
                confidence=cell(finding.get("confidence")),
                refs=cell(", ".join(str(item) for item in refs)),
                evidence=cell(evidence_locator(finding.get("evidence"))),
            )
        )

    for finding in findings:
        if not isinstance(finding, dict):
            continue
        lines.extend(
            [
                "",
                f"### {cell(finding.get('id'))}",
                "",
                f"- Intended: {cell(finding.get('intended_behavior'))}",
                f"- Observed: {cell(finding.get('observed_behavior'))}",
                f"- Reason: {cell(finding.get('reason'))}",
                f"- Coverage: `{cell(finding.get('evidence_coverage'))}`",
            ]
        )

    lines.extend(["", "## Product questions", ""])
    if not questions:
        lines.append("- None.")
    else:
        for question in questions:
            if not isinstance(question, dict):
                continue
            lines.append(
                f"- `{cell(question.get('id'))}` {cell(question.get('question'))}"
            )

    change_trace = data.get("change_trace")
    if isinstance(change_trace, dict):
        notes = change_trace.get("data_quality_notes")
        unmapped = change_trace.get("unmapped_changes")
        lines.extend(["", "## Change-data quality", ""])
        if isinstance(notes, list) and notes:
            lines.extend(f"- {cell(note)}" for note in notes)
        else:
            lines.append("- No recorded data-quality warnings.")
        lines.extend(["", "## Unmapped changed paths", ""])
        if isinstance(unmapped, list) and unmapped:
            for item in unmapped:
                if not isinstance(item, dict):
                    continue
                lines.append(
                    f"- `{cell(item.get('path'))}`: {cell(item.get('reason'))}"
                )
        else:
            lines.append("- None.")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if args.output.exists() and not args.overwrite:
        parser.error("refusing to overwrite an existing Markdown report")
    data = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        parser.error("calibration input must be a JSON object")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(data), encoding="utf-8")
    print(json.dumps({"status": "ok", "output": args.output.name}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
