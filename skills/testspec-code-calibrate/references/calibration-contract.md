# Code Calibration Contract

## Contents

- [Purpose](#purpose)
- [Top-level schema](#top-level-schema)
- [Code snapshot](#code-snapshot)
- [Finding schema](#finding-schema)
- [Classification matrix](#classification-matrix)
- [Product question registry](#product-question-registry)
- [Summary and status](#summary-and-status)
- [Privacy and integrity](#privacy-and-integrity)

## Purpose

`code-calibration.json` records implementation evidence without changing product intent. It is an evidence artifact, not a PRD, test point source, review approval, or publish input.

`code-calibration.md` is an optional snippet-free view rendered from the validated JSON. It does
not replace the JSON contract.

## Top-level schema

```json
{
  "schema_version": 1,
  "_context": {
    "source_skill": "testspec-code-calibrate",
    "canonical_source_policy": "prd-first",
    "mode": "comparison",
    "authority": "reference",
    "canonical_source_path": "requirements.md",
    "canonical_source_digest": "sha256:<64 lowercase hex>",
    "source_revision": {
      "version": 2,
      "summary": "synthetic preference revision",
      "updated_by_skill": "testspec-update"
    },
    "code_evidence": {
      "role": "reference",
      "repository_label": "synthetic-app",
      "ref": "main",
      "commit": "abcdef1",
      "scope": ["src/preferences"]
    },
    "canonical_mutation_performed": false,
    "status": "needs-product-confirmation"
  },
  "summary": {
    "total": 1,
    "aligned": 0,
    "conflict": 1,
    "code-only": 0,
    "prd-only": 0,
    "unknown": 0
  },
  "questions": [
    {
      "id": "Q-001",
      "question": "Should disabling the preference also stop future schedules?",
      "status": "open",
      "blocking": true,
      "finding_refs": ["CAL-001"]
    }
  ],
  "findings": [
    {
      "id": "CAL-001",
      "classification": "conflict",
      "requirement_refs": ["REQ-001", "AC-001"],
      "intended_behavior": "Disabling the digest stops future digest creation.",
      "observed_behavior": "The setting is saved but the scheduler remains enabled.",
      "reason": "",
      "evidence": [
        {
          "path": "src/preferences/digest.ts",
          "symbol": "saveDigestPreference",
          "lines": "42-68",
          "observation": "Persists the flag without changing the schedule."
        }
      ],
      "evidence_coverage": "end-to-end",
      "confidence": "high",
      "question_refs": ["Q-001"],
      "recommended_handoff": "product-confirmation"
    }
  ]
}
```

Recovery mode replaces canonical fields with:

```json
{
  "_context": {
    "mode": "recovery",
    "recovered_prd_draft": "artifacts/recovered-prd-draft.md",
    "recovered_prd_draft_digest": "sha256:<64 lowercase hex>",
    "status": "needs-product-confirmation"
  }
}
```

Recovery mode must not contain `source_revision`, `canonical_source_path`, or `canonical_source_digest`. Write the draft first, then record its SHA-256 in `recovered_prd_draft_digest`.

Change-diff mode keeps the comparison canonical fields and adds:

```json
{
  "_context": {
    "mode": "change-diff",
    "change_snapshot": {
      "path": "artifacts/change-snapshot.json",
      "digest": "sha256:<64 lowercase hex>",
      "snapshot_id": "20260101T010203123456Z-0123abcd"
    }
  },
  "change_trace": {
    "candidate_strategy": "keyword-hints-only",
    "data_quality_notes": [],
    "unmapped_changes": [
      {
        "path": "src/preferences/unrelated.ts",
        "reason": "No current REQ/AC candidate was found."
      }
    ]
  }
}
```

Change-diff requires `code_evidence.role=change-evidence`; `code_evidence.ref` stores the safe
snapshot head label, never the actual private ref. `code_evidence.commit`, repository label, and
scope must match the validated change snapshot.

## Code snapshot

`code_evidence` requires:

| Field | Rule |
|---|---|
| `role` | `reference`, `verification-baseline`, or `change-evidence` |
| `repository_label` | non-sensitive label; no path, URL, username, or organization name |
| `ref` | branch/tag/ref, or `unavailable` |
| `commit` | commit hash, or `unavailable` |
| `snapshot_reason` | required when ref or commit is `unavailable` |
| `scope` | non-empty repository-relative paths; no `..`; `.` only for explicit whole-repository authorization |

`authority` remains `reference` even when role is `verification-baseline`. The role controls how evidence is compared, not whether code becomes product truth.

## Finding schema

Use the complete finding shape shown in the top-level example.

In recovery mode, each finding also requires a unique `"draft_ref": "OBS-001"`. Other modes must
not contain `draft_ref`.

In change-diff mode, each finding requires:

- `change_trace_status`: `matched`, `partial`, `not-observed`, `deviation`, or `unknown`
- evidence `source`: `diff` or `snapshot`
- evidence `layer`: `entry`, `enforcement`, `state`, `feedback`, or `external`

`matched` / `deviation` require at least one `source=diff` item. `end-to-end` requires at least two
distinct layers. Supporting unchanged code may use `source=snapshot`.

## Classification matrix

| Classification | Requirement refs | Intended | Observed | Evidence | Coverage | Questions | Handoff |
|---|---:|---:|---:|---:|---:|---:|---|
| `aligned` | required | required | required | required | end-to-end / enforcement-layer | none | `none` / `testspec-analysis` |
| `conflict` | required | required | required | required | end-to-end / enforcement-layer | required | `product-confirmation` |
| `code-only` | empty | empty | required | required | end-to-end / enforcement-layer / partial | required | `product-confirmation` |
| `prd-only` | required | required | empty | searched scope evidence optional | scoped-search | none | `testspec-analysis` |
| `unknown` | optional | optional | optional | optional | any valid coverage | required | `product-confirmation` |

`unknown` requires a non-empty `reason`. `prd-only` means “not observed inside the authorized scope,” never “not implemented everywhere.”

`partial` covers isolated functions, one frontend/backend layer, unproven callers, comments, flags, or incomplete paths. It can never support `aligned` or `conflict`; use `unknown` until reachability or the canonical enforcement layer is established.

Recovery mode permits only `code-only` and `unknown`, because there is no canonical intent to support `aligned`, `conflict`, or `prd-only`.

Change-diff mapping is fixed:

| Change trace | Classification |
|---|---|
| `matched` | `aligned` or `code-only` |
| `deviation` | `conflict` |
| `partial` / `not-observed` / `unknown` | `unknown` |

Change-diff never emits `prd-only`; absence from a Diff is only `not-observed`, not proof of
absence from the authorized implementation.

Every calibration contains at least one finding. If no positive behavior is observed, record scoped `prd-only` or evidence-limited `unknown` instead of emitting an empty success artifact.

## Product question registry

`questions` is always present, including as `[]`. Every entry contains:

- stable unique `id` matching `Q-*`
- non-empty product-ready `question`
- `status: open`
- `blocking: true`
- one or more `finding_refs`

Finding `question_refs` and question `finding_refs` must link bidirectionally. Questions cannot be orphaned, and `aligned` / `prd-only` findings cannot register blocking questions.

## Summary and status

Summary counts must exactly match findings.

- any `conflict`, `code-only`, or `unknown` → `needs-product-confirmation`
- otherwise → `ready-for-analysis`
- recovery mode is always `needs-product-confirmation`

## Privacy and integrity

- Store repository-relative paths only.
- Do not store absolute paths, `file://` URLs, remote repository URLs, emails, IPs, tokens, or workspace identifiers.
- Do not persist actual private branch names, repository roots, raw Diff, changed-line text, or code snippets in change-diff artifacts.
- Persist safe branch-role labels such as `production`, `test`, and `requirement`; use commit hashes for immutable identity.
- `commit` is a Git hash or `unavailable`; `canonical_source_path` is exactly `requirements.md` or `proposal.md` and must match the file passed to the validator.
- `source_revision` contains a positive integer `version`, non-empty `summary`, and non-empty `updated_by_skill`, exactly matching a PRD-first canonical file.
- Comparison mode must record the pre-read canonical SHA-256 digest. The validator compares it with the canonical file after calibration.
- `canonical_mutation_performed` must be `false`.
- The artifact must not contain generated test cases or a passing review/publish gate.
- A recovery draft must contain its required sections, the exact code snapshot values, every finding's `OBS-*`, and every linked `Q-*`. Its digest must match the JSON artifact, and it must pass the same privacy scan.
