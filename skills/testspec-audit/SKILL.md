---
name: testspec-audit
description: 只读审计 TestSpec TestLib 的结构健康、重复用例、模块错放、provenance 缺失和未验证历史导入。用户说「审计 TestLib」「检查知识库质量」「清理重复用例前先盘点」「TestLib 被污染了」「历史用例是否可信」「找出该废弃或合并的用例」或执行 testspec-audit 时使用。只输出证据和 lifecycle proposal，不修改 TestLib。
---

# TestSpec Audit

IRON LAW: Never modify, merge, relocate, deprecate, archive, or verify a TestLib case during an audit.

```
TestSpec Audit Progress:

- [ ] Step 1: Locate TestLib and current PRD evidence ⚠️ REQUIRED
- [ ] Step 2: Run combined structural and semantic audit
- [ ] Step 3: Classify findings against current PRD
- [ ] Step 4: Build a case-specific lifecycle proposal
- [ ] Step 5: Verify the audit was read-only ⚠️ REQUIRED
- [ ] Step 6: Report health, blockers, and explicit handoff
```

## Authority and scope

Use this order:

1. Current `requirements.md`, PRD, product answers, and acceptance criteria
2. Explicit API, UI, and observed behavior evidence
3. TestLib history as candidate knowledge only
4. Code only when the user explicitly authorizes it as verification or change evidence

Missing code access never blocks an audit. When code and PRD conflict, report the conflict; do not promote implementation behavior to product intent.

This skill is permanently read-only. A user-confirmed lifecycle proposal must be handed off:

- additions or same-ID content updates → `testspec-publish`
- retire/relocate/merge maintenance → a separately authorized, scoped maintenance task

Do not perform that handoff's mutations inside `testspec-audit`.

Load `../_testspec-shared/references/source-provenance.md` only when classifying authority or trust. Load `references/audit-contract.md` before building lifecycle proposals.

## Run the combined audit

```bash
python "<testspec-audit-skill-dir>/scripts/audit_testlib.py" \
  --testlib "testspec/testlib"
```

The command combines:

- structural validation: JSON, required fields, IDs, references, index, and stats
- semantic audit: duplicate ID/title/body candidates, module mismatch, provenance gaps, and active unverified imports

The result separates `structural_health` and `semantic_health`. Overall `health=clean` is allowed only when both pass.

Save a report only when requested:

```bash
python "<testspec-audit-skill-dir>/scripts/audit_testlib.py" \
  --testlib "testspec/testlib" \
  --output "testspec/audits/testlib-audit.json"
```

Existing reports are not overwritten by default. Use `--overwrite` only after explicit authorization.

## Classify lifecycle candidates

Use current PRD evidence:

- `keep`: still satisfies current acceptance criteria
- `revise`: intent remains valid but action or oracle is stale
- `merge`: another case represents the same current intent
- `relocate`: case is stored under the wrong module or feature
- `retire`: current PRD explicitly removed the behavior
- `reconcile`: legacy import lacks current PRD traceability
- `unresolved`: evidence is insufficient; register a stable `Q-*`

TestLib cannot prove itself correct. Every proposal records case IDs, current `REQ-*`/`AC-*`, stable `Q-*` when needed, action, impact, and re-review requirements. Duplicate detection is a candidate signal, never automatic merge authority.

## Anti-patterns

| Anti-pattern | Required correction |
|---|---|
| Report `clean` after scanning only module files | Require both structural and semantic health |
| Keep a case because it already exists | Cite current PRD/AC evidence |
| Auto-merge normalized-title matches | Present the pair and request a separate maintenance decision |
| Change case status during audit | Stop and produce a lifecycle proposal only |
| Use code without explicit authorization | Keep `code_evidence.role=none` |
| Copy real TestLib data into public evals | Use fully synthetic fixtures |

## Pre-delivery checklist

- [ ] Structural and semantic sections both ran.
- [ ] `clean` means zero structural errors and zero semantic warnings.
- [ ] Every lifecycle proposal names case IDs and current evidence.
- [ ] Unknown decisions use stable `Q-*` instead of guesses.
- [ ] No TestLib, index, config, changelog, or case status changed.
- [ ] The report states `mutation_performed=false`.
- [ ] The final response identifies the separate next action without executing it.

Public evals must be fully synthetic and non-identifying. Private source material belongs only in ignored private fixture paths.
