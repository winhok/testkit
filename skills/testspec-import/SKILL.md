---
name: testspec-import
description: 隔离导入和迁移历史测试用例，将旧 Excel、CSV、JSON 或旧 TestLib 数据转换为可审计的 staging artifact，并按当前 PRD 做 reconciliation。用户说「导入历史用例」「迁移旧 Excel」「整理旧测试用例」「旧 TestLib 被污染」「把老用例对齐新需求」或执行 testspec-import 时使用。导入数据不会直接写入 TestLib，代码也不是默认输入。
---

# TestSpec Import

IRON LAW: Never publish, verify, or reuse a legacy-import case as a requirement fact until it has been reconciled against the current PRD and regenerated as a new testspec-native case.

```
TestSpec Import Progress:

- [ ] Step 1: Locate the target change and current PRD ⚠️ REQUIRED
- [ ] Step 2: Check isolated output paths and overwrite intent ⛔ BLOCKING
- [ ] Step 3: Import legacy rows as unverified staging data
- [ ] Step 4: Reconcile every row against current REQ/AC/Q evidence ⚠️ REQUIRED
- [ ] Step 5: Validate reconciliation readiness
- [ ] Step 6: Report counts, blockers, and the next skill
```

## Core boundaries

1. Current PRD, product answers, and acceptance criteria are canonical.
2. Code is not a default input. Read it only when the user explicitly provides access or requests calibration.
3. Historical TestLib, spreadsheets, and JSON are candidate knowledge, never requirement facts.
4. Write only to `<change>/imports/`; never write to `testspec/testlib/`.
5. Imported rows remain `legacy-import + unverified` permanently.
6. Never record the input absolute path, username, workspace path, or file URL in an artifact.

Load `../_testspec-shared/references/source-provenance.md` when deciding authority, optional code evidence, or trust transitions.

## Workflow

### 1. Establish the PRD baseline

Read, in order:

1. `<change>/requirements.md`
2. `<change>/proposal.md`
3. Product answers supplied in the current conversation

If none exists, mechanical import may continue, but reconciliation remains pending and publish eligibility stays blocked.

### 2. Import into quarantine

Before writing, check whether either output already exists. Do not overwrite unless the user explicitly requests it.

```bash
python "<testspec-import-skill-dir>/scripts/import_legacy_cases.py" \
  --input "<legacy.xlsx|legacy.csv|legacy.json>" \
  --output "<change>/imports/legacy-cases.json" \
  --source-label "legacy-source"
```

The script also creates `<change>/imports/reconciliation.json` with one `unresolved` record per imported case. Use `--overwrite` only after explicit overwrite authorization. Load `references/import-contract.md` before running the script.

The script performs only:

- field mapping and minimal normalization
- missing-field and duplicate-candidate warnings
- source-row provenance
- quarantine and initial reconciliation records

It does not decide business correctness, mutate TestLib, or upgrade trust.

### 3. Reconcile against current PRD

Update each record in `imports/reconciliation.json`:

- `keep`: PRD still supports the scenario
- `revise`: intent remains valid but action or oracle changed
- `merge`: another candidate represents the same current intent
- `retire`: current PRD explicitly removed the behavior
- `unresolved`: product evidence is insufficient

`keep` and `revise` require current `REQ-*` or `AC-*` references. `merge` requires `replacement_candidate_id`. Unresolved decisions retain stable `Q-*` references when available. A legacy case cannot prove its own `keep` decision. After every decision is complete, set `_context.status` to `ready-for-generate`; do not set it while any record is unresolved.

Validate the artifact:

```bash
python "<testspec-import-skill-dir>/scripts/validate_reconciliation.py" \
  --imported "<change>/imports/legacy-cases.json" \
  --reconciliation "<change>/imports/reconciliation.json"
```

Before handing candidates to generation, add `--ready-for-generate`. It fails when unresolved records remain or `keep/revise` records lack current requirement evidence.

### 4. Optional code calibration

Only after explicit authorization, code may serve as:

- `verification-baseline`: verify whether the implementation matches PRD intent
- `change-evidence`: explain observed drift or historical contamination

Record code scope and role. When code conflicts with PRD, register the conflict and request product resolution; do not silently promote implementation behavior.

### 5. Regenerate native candidates

The transition is:

```text
legacy-import/unverified
→ reconciliation.json
→ testspec-analysis / testspec-points
→ testspec-generate creates new testspec-native/provisional cases
→ testspec-review
→ testspec-publish writes testspec-native/verified cases
```

Never edit the imported row into `verified`; the imported evidence remains quarantined.

## Anti-patterns

| Anti-pattern | Required correction |
|---|---|
| Copy old JSON directly to `artifacts/testcases.json` | Run quarantine import and reconciliation |
| Treat an old expected result as the current oracle | Require current REQ/AC evidence |
| Read code because it is available | Use code only after explicit authorization |
| Re-run import over an existing staging file | Stop unless overwrite was explicitly authorized |
| Put real chat or company material in public evals | Use fully synthetic fixtures; keep private fixtures in ignored paths |

## Pre-delivery checklist

- [ ] Both import artifacts exist and contain no input path.
- [ ] Every imported row remains `legacy-import + unverified`.
- [ ] Reconciliation contains exactly one record per imported case.
- [ ] `keep/revise` decisions cite current REQ/AC evidence.
- [ ] No unresolved record is presented as ready for generation.
- [ ] Nothing was written to `testspec/testlib/`.
- [ ] Final report includes imported, skipped, duplicate, and reconciliation-status counts plus open `Q-*`.

Public evals must be fully synthetic and non-identifying. Private source material belongs only in the repository's ignored private fixture paths.
