---
name: testspec-code-calibrate
description: 对明确授权的代码范围做 PRD-first TestSpec 校准：比较实现快照与当前 PRD、从遗留代码恢复非 canonical 行为草稿，或对生产/测试/需求分支的 Git Diff 做变更追踪。用户明确执行 testspec-code-calibrate、要求「用代码校准 PRD」「对比需求和实现」「从代码恢复行为草稿」「检查生产和测试分支差异」「看需求分支改了什么」「对照 REQ/AC 与 Diff」时使用；普通 PRD 新建、更新、分析或导入请求不触发。
---

# TestSpec Code Calibrate

IRON LAW: Never convert observed code behavior into a canonical requirement or test oracle, and never modify `requirements.md`, without explicit product resolution through `testspec-update`.

```text
TestSpec Code Calibration Progress:

- [ ] Step 1: Confirm explicit authorization, code role, and scope ⛔ BLOCKING
- [ ] Step 2: Locate the TestSpec change and choose comparison/recovery/change-diff mode ⚠️ REQUIRED
- [ ] Step 3: Freeze canonical revision and code snapshot
- [ ] Step 4: Extract observable implementation evidence
- [ ] Step 5: Classify findings and register stable questions
- [ ] Step 6: Write and deterministically validate calibration artifacts ⛔ BLOCKING
- [ ] Step 7: Verify canonical files were unchanged and hand off
```

## Boundaries

1. Run only after explicit invocation or an explicit request to inspect code. Missing code access never blocks the normal TestSpec workflow.
2. Read only the authorized repository, ref, and relative scope. Do not expand to the entire workspace implicitly.
3. Keep `canonical_source_policy=prd-first`; code authority is always `reference`.
4. Record only observable behavior as `observed`; label unsupported interpretation `inferred` or `unknown`.
5. Never write implementation behavior directly into `requirements.md`, `proposal.md`, test points, cases, or TestLib.
6. Store only a non-sensitive repository label and repository-relative paths. Never store an absolute path, username, remote URL, token, or private workspace identifier.
7. In change-diff mode, persist safe branch-role labels and commit hashes, never actual private branch names, raw Diff, changed lines, or code snippets.

Load `../_testspec-shared/references/source-provenance.md` before choosing `code_evidence.role` or resolving an authority conflict.

## Modes

### Comparison

Use when the current change has versioned `requirements.md` or `proposal.md`.

Output:

- `<change>/artifacts/code-calibration.json`
- `<change>/artifacts/code-calibration.md`

The JSON compares canonical intent with observed code. It does not change the canonical source.

### Recovery

Use only when a TestSpec change exists but no versioned canonical source is available and the user explicitly asks to recover behavior from legacy code.

Output:

- `<change>/artifacts/code-calibration.json`
- `<change>/artifacts/code-calibration.md`
- `<change>/artifacts/recovered-prd-draft.md`

Write the draft before the JSON. The draft title and context must say `Observed implementation draft — not canonical`; record its SHA-256 and matching code snapshot in the JSON. Product confirmation is mandatory before `testspec-update` may promote confirmed statements into `requirements.md`.

Load `references/recovered-prd-draft-template.md` only in recovery mode.

### Change-diff

Use when a versioned canonical source exists and the user explicitly asks what changed between
production, test, requirement, release, staged, or worktree states.

Output:

- `<change>/artifacts/change-snapshot.json`
- `<change>/artifacts/code-calibration.json`
- `<change>/artifacts/code-calibration.md`

Load `references/change-diff-workflow.md`. A Diff is change evidence, not a test result or proof
that unchanged requirements are missing.

## Workflow

### 1. Confirm authorization and freeze scope

Record:

- `role`: `reference`, `verification-baseline`, or `change-evidence`
- non-sensitive `repository_label`
- branch/tag/ref and commit; use `unavailable` plus `snapshot_reason` only when the source is not a Git checkout
- one or more repository-relative scope paths; `.` means the repository root only when the user explicitly authorizes the whole repository

Stop before reading code when role or scope is missing. Reject `..`, absolute paths, remote URLs, and scope expansion not requested by the user.

If repository inspection is authorized but the requested module is ambiguous, load
`references/module-discovery.md`, inspect only discovery surfaces, return candidates, and wait
for the user to select scope before reading implementation bodies.

### 2. Locate the change and canonical source

Use `../_testspec-shared/references/common.md` to locate the change.

- Versioned source + ordinary implementation comparison → comparison mode
- Versioned source + explicit branch/Diff request → change-diff mode
- No versioned canonical source + explicit recovery request → recovery mode
- No canonical source + ordinary comparison request → stop and run `testspec-new` first

In comparison and change-diff modes, record the exact canonical `source_revision`, exact source
name (`requirements.md` or `proposal.md`), and a pre-read `sha256:<digest>` of the canonical file.
Do not increment the revision.

### 3. Extract observable evidence

Load `references/code-evidence-extraction.md` and inspect only the authorized scope. Extract product-visible evidence such as:

- entry points and module boundaries
- roles and permission enforcement
- fields, validation, enums, and visible messages
- state transitions and action branches
- observable success, failure, and recovery behavior

Every evidence item uses a repository-relative path, symbol/locator, line span, and concise observation. Assign finding-level `evidence_coverage` from the extraction reference. Do not treat comments, names, exported functions with unproven callers, unreachable code, feature-flagged paths, or a single frontend/backend layer as complete product truth.

Load `references/framework-locators.md` only for a matching framework. In change-diff mode,
collect and validate the safe snapshot first, use keyword matches only as candidate hints, then
read transient hunks and connected runtime paths for semantic evidence.

### 4. Classify findings

Load `references/calibration-contract.md` before writing JSON. Use exactly:

- `aligned`: intended and observed behavior agree
- `conflict`: intended and observed behavior disagree
- `code-only`: behavior exists in code but has no canonical requirement
- `prd-only`: canonical requirement was not observed in the authorized scope
- `unknown`: evidence is insufficient or contradictory

Rules:

- `conflict`, `code-only`, and `unknown` require stable `Q-*`, a matching top-level open question with product-ready wording, and `recommended_handoff=product-confirmation`.
- `prd-only` is not automatically an implementation defect; report the searched scope and hand off to `testspec-analysis`.
- `aligned` and `conflict` require `end-to-end` or `enforcement-layer` coverage. Partial paths must remain `unknown`.
- Recovery mode permits only `code-only` and `unknown`.
- Every recovery finding has a unique `OBS-*` draft reference; the recovery draft must contain that `OBS-*` and every linked `Q-*`.
- A finding cannot cite itself or a legacy case as product authority.
- Change-diff findings also follow the fixed trace-status mapping in
  `references/change-diff-workflow.md`; Diff absence becomes `unknown/not-observed`, never
  `prd-only`.

### 5. Write and validate

Write canonical machine output to `<change>/artifacts/code-calibration.json`. Do not overwrite an existing calibration artifact unless the user explicitly authorizes replacement.

Comparison:

```bash
python "<testspec-code-calibrate-skill-dir>/scripts/validate_code_calibration.py" \
  --input "<change>/artifacts/code-calibration.json" \
  --canonical "<change>/<requirements.md-or-proposal.md>"
```

Recovery:

```bash
python "<testspec-code-calibrate-skill-dir>/scripts/validate_code_calibration.py" \
  --input "<change>/artifacts/code-calibration.json" \
  --draft "<change>/artifacts/recovered-prd-draft.md"
```

Change-diff:

Collect `change-snapshot.json` with
`scripts/collect_change_snapshot.py` using the exact command and safe-label rules in
`references/change-diff-workflow.md`, then run:

```bash
python "<testspec-code-calibrate-skill-dir>/scripts/validate_change_snapshot.py" \
  --input "<change>/artifacts/change-snapshot.json"

python "<testspec-code-calibrate-skill-dir>/scripts/validate_code_calibration.py" \
  --input "<change>/artifacts/code-calibration.json" \
  --canonical "<change>/<requirements.md-or-proposal.md>" \
  --snapshot "<change>/artifacts/change-snapshot.json"
```

After JSON validation, render the snippet-free Markdown view:

```bash
python "<testspec-code-calibrate-skill-dir>/scripts/render_code_calibration.py" \
  --input "<change>/artifacts/code-calibration.json" \
  --output "<change>/artifacts/code-calibration.md"
```

Fix every validation error. In comparison and change-diff modes, read the canonical file again
after validation and verify its digest still matches `_context.canonical_source_digest`.

### 6. Hand off

- all findings `aligned` or `prd-only` → `testspec-analysis`
- any `conflict`, `code-only`, or `unknown` → product confirmation
- confirmed product decision changes intent → `testspec-update`, then `testspec-analysis`
- recovery draft → product confirmation, then `testspec-update`; never go directly to points/generate
- change-diff `partial/not-observed/unknown` → product confirmation or explicitly authorized
  broader evidence collection; never claim missing implementation from Diff absence
- historical import remains quarantined; calibration evidence may explain drift but cannot prove `keep/revise`

## Anti-patterns

| Anti-pattern | Required correction |
|---|---|
| Scan code because a repository is available | Require explicit invocation, role, and scope |
| Write REQ/AC directly from code | Write a recovery draft or `code-only` finding |
| Treat absent code as proof a PRD requirement is wrong | Use `prd-only` and record searched scope |
| Use absolute paths in artifacts | Store repository-relative paths and a safe label |
| Treat comments or dead code as observed behavior | Mark inferred/unknown and register `Q-*` |
| Continue to generate cases from unresolved code conflict | Route through product confirmation and `testspec-update` |
| Treat a keyword hit as implementation evidence | Use it only to select a transient hunk for semantic inspection |
| Treat no changed hunk as `prd-only` | Use `unknown` + `not-observed`; full absence requires comparison mode |
| Store actual private refs or raw Diff | Store safe role labels, commits, metadata, and relative locators only |
| Auto-fetch, checkout, or switch two-dot/three-dot semantics | Use existing local refs and the explicitly selected Diff mode |

## Pre-delivery checklist

- [ ] Invocation, role, ref/commit, and scope were explicitly authorized.
- [ ] Canonical policy is still PRD-first and code authority is `reference`.
- [ ] Every finding uses a valid classification and repository-relative evidence.
- [ ] `conflict/code-only/unknown` findings have stable `Q-*` linked bidirectionally to product-ready question objects.
- [ ] Recovery output is visibly non-canonical.
- [ ] Validator passes with the canonical file or recovery draft.
- [ ] Canonical digest and revision remain unchanged.
- [ ] Change-diff snapshot validates, matches code evidence, and contains no raw Diff/snippet/private ref.
- [ ] Every end-to-end change finding spans at least two evidence layers.
- [ ] Markdown report was rendered from the validated JSON and contains locators rather than snippets.
- [ ] Final response names the next skill and unresolved product decisions.

Public evals and examples must be fully synthetic. Never copy private source code, repository paths, company names, tickets, URLs, or business values into this skill.
