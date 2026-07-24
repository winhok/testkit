---
name: testspec-code-calibrate
description: 对明确授权的指定代码范围做 TestSpec 校准，把可观察实现与当前 PRD/requirements.md 比较，或在没有 PRD 的遗留系统中生成待产品确认的实现行为草稿。用户明确执行 testspec-code-calibrate、要求「用代码校准 PRD」「对比需求和实现」「从遗留代码恢复需求草稿」「检查代码与 REQ/AC 差异」时使用；普通 PRD 新建、更新、分析或导入请求不触发。
---

# TestSpec Code Calibrate

IRON LAW: Never convert observed code behavior into a canonical requirement or test oracle, and never modify `requirements.md`, without explicit product resolution through `testspec-update`.

```text
TestSpec Code Calibration Progress:

- [ ] Step 1: Confirm explicit authorization, code role, and scope ⛔ BLOCKING
- [ ] Step 2: Locate the TestSpec change and choose comparison/recovery mode ⚠️ REQUIRED
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

Load `../_testspec-shared/references/source-provenance.md` before choosing `code_evidence.role` or resolving an authority conflict.

## Modes

### Comparison

Use when the current change has versioned `requirements.md` or `proposal.md`.

Output:

- `<change>/artifacts/code-calibration.json`

The JSON compares canonical intent with observed code. It does not change the canonical source.

### Recovery

Use only when a TestSpec change exists but no versioned canonical source is available and the user explicitly asks to recover behavior from legacy code.

Output:

- `<change>/artifacts/code-calibration.json`
- `<change>/artifacts/recovered-prd-draft.md`

Write the draft before the JSON. The draft title and context must say `Observed implementation draft — not canonical`; record its SHA-256 and matching code snapshot in the JSON. Product confirmation is mandatory before `testspec-update` may promote confirmed statements into `requirements.md`.

Load `references/recovered-prd-draft-template.md` only in recovery mode.

## Workflow

### 1. Confirm authorization and freeze scope

Record:

- `role`: `reference`, `verification-baseline`, or `change-evidence`
- non-sensitive `repository_label`
- branch/tag/ref and commit; use `unavailable` plus `snapshot_reason` only when the source is not a Git checkout
- one or more repository-relative scope paths; `.` means the repository root only when the user explicitly authorizes the whole repository

Stop before reading code when role or scope is missing. Reject `..`, absolute paths, remote URLs, and scope expansion not requested by the user.

### 2. Locate the change and canonical source

Use `../_testspec-shared/references/common.md` to locate the change.

- Versioned `requirements.md` or `proposal.md` → comparison mode
- No versioned canonical source + explicit recovery request → recovery mode
- No canonical source + ordinary comparison request → stop and run `testspec-new` first

In comparison mode, record the exact canonical `source_revision`, exact source name (`requirements.md` or `proposal.md`), and a pre-read `sha256:<digest>` of the canonical file. Do not increment the revision.

### 3. Extract observable evidence

Load `references/code-evidence-extraction.md` and inspect only the authorized scope. Extract product-visible evidence such as:

- entry points and module boundaries
- roles and permission enforcement
- fields, validation, enums, and visible messages
- state transitions and action branches
- observable success, failure, and recovery behavior

Every evidence item uses a repository-relative path, symbol/locator, line span, and concise observation. Assign finding-level `evidence_coverage` from the extraction reference. Do not treat comments, names, exported functions with unproven callers, unreachable code, feature-flagged paths, or a single frontend/backend layer as complete product truth.

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

Fix every validation error. In comparison mode, read the canonical file again after validation and verify its digest still matches `_context.canonical_source_digest`.

### 6. Hand off

- all findings `aligned` or `prd-only` → `testspec-analysis`
- any `conflict`, `code-only`, or `unknown` → product confirmation
- confirmed product decision changes intent → `testspec-update`, then `testspec-analysis`
- recovery draft → product confirmation, then `testspec-update`; never go directly to points/generate
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

## Pre-delivery checklist

- [ ] Invocation, role, ref/commit, and scope were explicitly authorized.
- [ ] Canonical policy is still PRD-first and code authority is `reference`.
- [ ] Every finding uses a valid classification and repository-relative evidence.
- [ ] `conflict/code-only/unknown` findings have stable `Q-*` linked bidirectionally to product-ready question objects.
- [ ] Recovery output is visibly non-canonical.
- [ ] Validator passes with the canonical file or recovery draft.
- [ ] Canonical digest and revision remain unchanged.
- [ ] Final response names the next skill and unresolved product decisions.

Public evals and examples must be fully synthetic. Never copy private source code, repository paths, company names, tickets, URLs, or business values into this skill.
