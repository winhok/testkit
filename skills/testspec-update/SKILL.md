---
name: testspec-update
description: TestSpec 需求源更新与口径收敛（可重复执行的轻量 rebaseline）- 当已有 testspec/changes/<name>/ 后，用户补充、修改、删除、澄清、替换 PRD、接口文档、UI 图、原型图、产品回答、验收规则、权限规则、时间口径、收益映射、字段说明或需求范围时使用。适用于「产品改需求了」「补充接口文档」「新增 UI 图」「删掉这个需求」「同步最新 PRD」「口径收敛」「更新 requirements」「标记旧 analysis 过期」「用例写完后需求变了」「testspec-update / testspec update」。产出更新后的上游需求源、变更影响摘要、blocking_open_questions/dynamic_followups 分类，并标记 stale 下游产物。
---

# testspec-update：需求源更新与口径收敛

IRON LAW: Never let downstream artifacts pretend to match an older requirement baseline after PRD/API/UI/product intent changes.

## Workflow

Copy this checklist and check off items as you complete them:

```
Testspec Update Progress:

- [ ] Step 1: Locate current change directory ⚠️ REQUIRED
- [ ] Step 2: Classify incoming source update ⚠️ REQUIRED
- [ ] Step 3: Converge upstream facts
- [ ] Step 4: Recalculate requirements status
- [ ] Step 5: Mark stale downstream artifacts
- [ ] Step 6: Report impact and next skill
```

## Scope

Use this skill only after a TestSpec change workspace already exists. It updates the current change's source of truth; it does not create a new change and does not regenerate analysis, test points, or cases by default.

## Shared Rules

- Current change directory: `../_testspec-shared/references/common.md`
- Output contract: `../_testspec-shared/references/output-contracts.md`
- Context metadata: `../_testspec-shared/references/context-protocol.md`
- Requirements template: `../testspec-new/references/requirements-template.md`

## Execution Rules

### Step 1: Locate Current Change

Apply the current change directory rule from `../_testspec-shared/references/common.md`. If no active change exists, stop and tell the user to run `testspec-new` first.

### Step 2: Classify Incoming Update

Classify from the user's latest input and existing artifacts first. Do not start with a clarification questionnaire.

Answer internally:
- Is the new input adding, replacing, correcting, or deleting requirements?
- Which source type changed: PRD, API doc, UI/prototype, product answer, business rule, data mapping, permission rule, or time/calendar rule?
- Does it contradict an existing statement in `proposal.md`, `requirements.md`, `artifacts/source-prd.md`, `artifacts/api-doc.md`, or `requirements-analysis.md`?
- Does it affect already generated `specs/testpoints.md`, `artifacts/testcases.json`, Excel/XMind files, or `review-report.md`?

Latest user-provided information wins over older local artifacts. Do not preserve old wording as an equal alternative unless the user explicitly says both versions coexist.

Ask the user only when the answer would change whether you write, delete, or mark a major artifact stale and cannot be inferred from the input. Ask exactly one highest-impact blocking question, then stop.

### Step 3: Converge Upstream Facts

Ensure `artifacts/` exists, then create or update the source artifacts:
- `proposal.md`: update linked sources, scope notes, and context metadata.
- `requirements.md`: create it from `../testspec-new/references/requirements-template.md` when missing; otherwise merge changed requirements, remove deleted requirements, update sources, and keep REQ/RISK IDs stable where possible.
- `artifacts/source-prd.md`: create or update when PRD, product answer, business rule, UI image, or prototype material changed.
- `artifacts/api-doc.md`: create or update when API, technical interface, field, response-shape, or error-code material changed.
- `artifacts/update-log.md`: create or update when stale binary exports such as Excel/XMind must be marked without inline edits.

When creating `requirements.md` in an existing change directory, treat this as the first canonical requirements source for that change: set `source_revision.version` to `1` and `source_revision.updated_by_skill` to `testspec-update`.

#### Interface Replacement Mode

When the user provides a latest API document that contradicts older interface facts, do not patch isolated words. Treat `artifacts/api-doc.md` as the API truth source for this change:
- Rebuild or resync the affected API section in `artifacts/api-doc.md` from the latest document.
- Remove superseded endpoint/field/response-shape claims from `requirements.md` instead of keeping both versions.
- Reverse-update acceptance criteria that depended on the old API shape.
- Record the old-to-new API delta in the impact summary.

Example: if an old trend interface claimed it returns an ECharts option but the latest doc returns buckets/categories, `api-doc.md` and the related REQ acceptance criteria must say buckets/categories only.

#### UI Intake

When UI images or prototypes are supplemented, record the intake in `artifacts/source-prd.md` first, then update or add `requirements.md` REQs only when the UI evidence changes observable behavior or acceptance criteria. Use this shape:

```markdown
## UI 补充记录

| 页面 | 状态 | 入口 | 筛选/弹层 | Tooltip | 跳转 | 权限/空态 | 数据字段 | 来源 |
|------|------|------|-----------|---------|------|-----------|----------|------|
| <page> | <state> | <entry> | <filter/modal> | <tooltip> | <navigation> | <permission/empty> | <fields> | <image/link/user answer> |
```

### Step 4: Recalculate Requirements Status

After every `requirements.md` update:
- Recompute the six requirement quality scores: completeness, clarity, consistency, testability, traceability, feasibility.
- Recompute `requirement_quality.readiness`.
- Read the existing `source_revision.version` before writing context. After a successful requirements source update, write `old_version + 1`; if no previous version exists or `requirements.md` was just created, start at `1`. Always set `source_revision.updated_by_skill` to `testspec-update`.
- Split unresolved items:
  - `blocking_open_questions`: unresolved questions that prevent meaningful analysis or invalidate test oracle design.
  - `dynamic_followups`: execution-time discoveries that should be raised during testing but do not block analysis.
- Recompute `requirements_intake.open_question_count` from `blocking_open_questions` only.

Example: "mapping does not list every possible income source, but product says testers should report new sources during execution and wait for mapping updates" belongs in `dynamic_followups`, not `blocking_open_questions`.

### Step 5: Mark Stale Downstream Artifacts

If any downstream artifact may no longer match the updated source, mark it stale using the format that preserves the file type:

Markdown files (`requirements-analysis.md`, `specs/testpoints.md`, `review-report.md`):
```markdown
> NOTE: 旧口径，仅供历史参考。This artifact was generated from an older requirement baseline. Re-run the indicated upstream skill before relying on it.
```

JSON files (`artifacts/testcases.json`):
- Keep the file valid JSON.
- Update or add `_context.stale_downstream_artifacts`, `_context.stale_reason`, and `_context.next_skill`.
- Do not prepend Markdown or plain text to JSON.

Excel/XMind files:
- Do not write an inline notice into binary exports.
- Mark stale in `artifacts/update-log.md` and the final response.
- If a machine-readable marker is needed, create or update a sidecar metadata file such as `artifacts/stale-artifacts.json`.

Use these defaults:
- `requirements-analysis.md` stale after material PRD/API/UI/business-rule changes; next step: `testspec-analysis`.
- `specs/testpoints.md` stale after analysis-affecting requirement changes; next step: `testspec-points`.
- `artifacts/testcases.json`, Excel, and XMind stale after testpoint-affecting changes; next step: `testspec-generate`.
- `review-report.md` stale after any regenerated cases are needed; next step: `testspec-review`.

For `requirements-analysis.md`, also clean obvious contradictions that would mislead a reader:
- Move clearly superseded summary bullets, high-priority issues, or clarification items into a short "旧口径历史记录" note, or mark them "已失效".
- Do not rewrite the full analysis; the correct next step is still `testspec-analysis`.
- Do not leave directly contradicted claims visible as active conclusions below the stale notice.

Do not delete old downstream artifacts unless the user explicitly asks.

Hard rule: after stale marking, update the final `testspec-context` block in `requirements.md`. It must include `stale_downstream_artifacts`, `stale_reason`, `next_skill`, and the refreshed `source_revision`. Downstream `testspec-analysis` relies on this upstream marker to decide whether old analysis can be reused.

### Step 6: Report Impact

End with:
- Updated files
- Added/changed/removed REQ IDs
- `blocking_open_questions` count
- `dynamic_followups` count
- Stale artifacts and the exact next skill to run

If `blocking_open_questions` is non-empty or `dynamic_followups` is non-empty, output 可复制给产品的问题清单，分为两个独立块：

```markdown
## 阻塞问题（计入 blocking_open_questions）
1. [P0/P1/P2] <问题>（影响：<阻塞的分析/验收判断>；需要产品给出：<规则/范围/样例/口径>）
```

```markdown
## 执行期动态跟进（不计入阻塞问题数，不影响 ready_for_analysis）
1. <问题>（触发条件：<测试执行中发现时>；处理方式：<提给产品补充后再纳入验收>）
```

Keep each question tied to a REQ/RISK/source location. Blocking questions sort by priority; dynamic followups are informational only.

## Anti-Patterns

- Do not create a new change workspace for an existing change.
- Do not append new product input without removing or correcting contradicted old conclusions.
- Do not keep obsolete API/UI/business wording in `requirements.md` as if it is still valid.
- Do not leave `requirements-analysis.md` unmarked when upstream facts changed.
- Do not add Markdown stale notices to JSON, Excel, XMind, or other non-Markdown artifacts.
- Do not leave obviously contradicted old analysis conclusions active under a stale notice.
- Do not treat a latest API document as a minor note when it changes response shape, fields, or acceptance criteria.
- Do not classify execution-time discovery tasks as blocking questions.
- Do not regenerate analysis, points, cases, or review unless the user explicitly asks.

## Pre-Delivery Checklist

- [ ] No stale old conclusion remains in updated source files.
- [ ] `requirements.md` separates `blocking_open_questions` and `dynamic_followups`.
- [ ] `requirements.md` exists; if it was created by this update, its context has `source_revision.version = 1` and `updated_by_skill = testspec-update`.
- [ ] Existing `requirements.md` source updates increment `source_revision.version` by 1 and set `updated_by_skill = testspec-update`.
- [ ] `requirements_intake.open_question_count` counts only blocking questions.
- [ ] `requirement_quality.readiness` matches the recalculated blocking state and score.
- [ ] Latest API documents, if contradictory, rebuilt or resynced `artifacts/api-doc.md` and reverse-updated affected REQ acceptance criteria.
- [ ] UI supplements, if any, are recorded in `artifacts/source-prd.md` and use the fixed page/state/entry/modal/tooltip/navigation/permission/data-field intake shape.
- [ ] If readiness is not `ready_for_analysis`, the final response includes a copy-ready product question list.
- [ ] Every affected downstream artifact is either still valid or marked stale without breaking its file format.
- [ ] `requirements.md` context lists every stale downstream artifact plus `stale_reason` and `next_skill`.
