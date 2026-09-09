# 代码校准契约

## 内容

- 用途
- 顶层 schema
- 代码快照
- Finding schema
- 分类矩阵
- 产品问题 registry
- 摘要与状态
- 隐私与完整性

## 用途

`code-calibration.json` 在不改变产品意图的前提下记录实现证据。它是 evidence artifact，不是 PRD、测试点 source、review approval 或 publish input。

`code-calibration.md` 是从已校验 JSON 渲染的可选无代码片段视图，不能替代 JSON 契约。

## 顶层 schema

schema v1 保持单仓格式并继续受 validator 支持。新生成的多仓 artifact 使用 schema v2；不得在同一 artifact 混用 v1 单仓字段与 v2 数组字段。

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
      "summary": "合成的偏好设置修订",
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
      "question": "关闭该偏好设置后是否也应停止未来调度？",
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
      "intended_behavior": "关闭摘要后停止创建未来摘要。",
      "observed_behavior": "设置已保存，但调度器仍保持启用。",
      "reason": "",
      "evidence": [
        {
          "path": "src/preferences/digest.ts",
          "symbol": "saveDigestPreference",
          "lines": "42-68",
          "observation": "持久化该标记，但未改变调度状态。"
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

### Schema v2 多仓扩展

v2 只改变代码来源与 change snapshot 的绑定方式；canonical digest、`source_revision`、finding 分类、coverage 和产品确认规则不变：

```json
{
  "schema_version": 2,
  "_context": {
    "code_evidence": {
      "sources": [
        {"id":"backend","role":"verification-baseline","repository_label":"synthetic-service","ref":"main","commit":"aaaaaaaa","scope":["src/shared"]},
        {"id":"web","role":"verification-baseline","repository_label":"synthetic-web","ref":"main","commit":"bbbbbbbb","scope":["src/shared"]},
        {"id":"mobile","role":"verification-baseline","repository_label":"synthetic-mobile","ref":"main","commit":"cccccccc","scope":["app/shared"]}
      ]
    }
  },
  "findings": [{
    "evidence": [{"source_id":"web","path":"src/shared/entry.ts","symbol":"completeFlow","lines":"10-20","observation":"完成可见流程。"}]
  }]
}
```

`sources[].id` 匹配 `^[a-z][a-z0-9-]{0,31}$` 且全局唯一。每个 source 独立拥有 `role/repository_label/ref/commit/snapshot_reason/scope`；scope 非空、去重，`.` 不得与窄路径并列。`ref` 是 `main/master/production/test/requirement/release/staged/worktree/baseline/snapshot/unavailable` 之一（可带数字后缀）的持久化安全角色标签，不是实际私有分支名。

v2 每条 evidence 必须包含已声明的 `source_id`，其 `path` 必须是对应 source scope 内的仓库相对路径。`backend:src/shared/entry.ts` 与 `web:src/shared/entry.ts` 是两个不同 locator，renderer 显示为 `[backend] src/...:symbol:lines`。

comparison 的多个 sources 共同对照同一 canonical revision。`prd-only` 只有在 `searched_source_ids` 无重复且精确覆盖全部声明 sources 时成立；单个仓库未观察到行为只能是 `unknown`，不能推导整个产品未实现。

有效 v1 可用 validator 的 `--migrate-v2-output <new-file>` 确定性迁移：原单仓转成 `source-1`，evidence 和 change snapshot binding 补上同一 ID，原文件不覆盖。change-diff 的 companion snapshot 还要执行 `validate_change_snapshot.py --input <v1> --source-id source-1 --migrate-v2-output <change-snapshot-source-1.json>`；recovery companion draft 要按 v2 模板改为精确 source 表和 `[source-1]` OBS locator，再更新 digest。迁移后的整组 artifact 必须按当前模式重新验证；迁移不改变 finding、canonical digest 或 revision。

recovery 模式使用以下字段替代 canonical 字段：

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

recovery 模式不得包含 `source_revision`、`canonical_source_path` 或 `canonical_source_digest`。先写 draft，再把其 SHA-256 记录到 `recovered_prd_draft_digest`。

change-diff 模式保留 comparison 的 canonical 字段，并增加：

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
        "reason": "未找到当前 REQ/AC 候选。"
      }
    ]
  }
}
```

change-diff 要求 `code_evidence.role=change-evidence`；`code_evidence.ref` 保存安全的 snapshot head 标签，绝不能保存真实私有 ref。`code_evidence.commit`、仓库标签和 scope 必须与已校验 change snapshot 一致。

schema v2 使用 `_context.change_snapshots[]`，每项包含 `source_id/path/digest/snapshot_id`。路径固定为 `artifacts/change-snapshot-<source_id>.json`，每个声明 source 恰好一个 binding；每个文件分别校验 source ID、仓库标签、head commit、安全 head label、scope、digest 与 snapshot ID。`change_trace.unmapped_changes[]` 也必须带 `source_id`。命令行按 binding 重复传入 `--snapshot`，文件 basename 用于确定性配对，禁止按数组位置猜测。

## 代码快照

`code_evidence` 要求：

| 字段 | 规则 |
|---|---|
| `role` | `reference`, `verification-baseline`, or `change-evidence` |
| `repository_label` | 非敏感标签；不得包含路径、URL、用户名或组织名 |
| `ref` | branch/tag/ref，或 `unavailable` |
| `commit` | commit hash，或 `unavailable` |
| `snapshot_reason` | ref 或 commit 为 `unavailable` 时必需 |
| `scope` | 非空仓库相对路径；不得包含 `..`；`.` 仅用于明确的全仓授权 |

即使 role 为 `verification-baseline`，`authority` 仍保持 `reference`。role 只控制证据如何比较，不会让代码变成产品事实。

## Finding schema

使用顶层示例中的完整 finding 结构。

recovery 模式的每个 finding 还要求唯一的 `"draft_ref": "OBS-001"`。其他模式不得包含 `draft_ref`。

change-diff 模式的每个 finding 要求：

- `change_trace_status`: `matched`, `partial`, `not-observed`, `deviation`, or `unknown`
- evidence `source`：`diff` 或 `snapshot`
- evidence `layer`：`entry`、`enforcement`、`state`、`feedback` 或 `external`

`matched` / `deviation` 至少要求一个 `source=diff` item。`end-to-end` 至少要求两个不同 layer。未变化的支持代码可使用 `source=snapshot`。

## 分类矩阵

| Classification | Requirement refs | Intended | Observed | Evidence | Coverage | Questions | Handoff |
|---|---:|---:|---:|---:|---:|---:|---|
| `aligned` | 必需 | 必需 | 必需 | 必需 | end-to-end / enforcement-layer | 无 | `none` / `testspec-analysis` |
| `conflict` | 必需 | 必需 | 必需 | 必需 | end-to-end / enforcement-layer | 必需 | `product-confirmation` |
| `code-only` | 空 | 空 | 必需 | 必需 | end-to-end / enforcement-layer / partial | 必需 | `product-confirmation` |
| `prd-only` | 必需 | 必需 | 空 | 搜索范围证据可选 | scoped-search | 无 | `testspec-analysis` |
| `unknown` | 可选 | 可选 | 可选 | 可选 | 任意合法 coverage | 必需 | `product-confirmation` |

`unknown` 要求非空 `reason`。`prd-only` 表示“授权范围内未观察到”，绝不表示“所有地方都未实现”。

`partial` 包括孤立函数、单一前后端层、未证明调用方、注释、flag 或不完整路径。它绝不能支持 `aligned` 或 `conflict`；证明可达性或 canonical enforcement layer 前应使用 `unknown`。

recovery 模式只允许 `code-only` 和 `unknown`，因为不存在能够支持 `aligned`、`conflict` 或 `prd-only` 的 canonical intent。

change-diff 映射固定为：

| Change trace | Classification |
|---|---|
| `matched` | `aligned` or `code-only` |
| `deviation` | `conflict` |
| `partial` / `not-observed` / `unknown` | `unknown` |

change-diff 绝不产生 `prd-only`；Diff 中缺失只能归为 `not-observed`，不能证明授权实现中不存在。

每次 calibration 至少包含一个 finding。没有观察到正向行为时，记录范围明确的 `prd-only` 或证据受限的 `unknown`，不能生成空的成功 artifact。

## 产品问题 registry

`questions` 始终存在，允许为 `[]`。每项包含：

- 匹配 `Q-*` 的稳定唯一 `id`
- 非空、可直接交给产品的 `question`
- `status: open`
- `blocking: true`
- 一个或多个 `finding_refs`

finding 的 `question_refs` 与 question 的 `finding_refs` 必须双向关联。问题不能孤立，`aligned` / `prd-only` finding 不能登记阻塞问题。

## 摘要与状态

summary 数量必须与 finding 精确一致。

- any `conflict`, `code-only`, or `unknown` → `needs-product-confirmation`
- otherwise → `ready-for-analysis`
- recovery 模式始终为 `needs-product-confirmation`

## 隐私与完整性

- 只存储仓库相对路径。
- 不得存储绝对路径、`file://` URL、远程仓库 URL、邮箱、IP、token 或工作区标识。
- change-diff artifact 不得持久化真实私有分支名、仓库根目录、原始 Diff、变更行文本或代码片段。
- 持久化 `production`、`test`、`requirement` 等安全分支角色标签；不可变 identity 使用 commit hash。
- `commit` 是 Git hash 或 `unavailable`；`canonical_source_path` 只能是 `requirements.md` 或 `proposal.md`，且必须匹配传给 validator 的文件。
- `source_revision` 包含正整数 `version`、非空 `summary` 和非空 `updated_by_skill`，并与 PRD-first canonical 文件精确匹配。
- comparison 模式必须记录读取前的 canonical SHA-256 digest。validator 在校准后与 canonical 文件比较。
- `canonical_mutation_performed` 必须为 `false`。
- artifact 不得包含生成测试用例或已通过的 review/publish gate。
- recovery draft 必须包含必需章节、准确代码快照值、每个 finding 的 `OBS-*` 和所有关联 `Q-*`。digest 必须与 JSON artifact 匹配，并通过相同隐私扫描。
