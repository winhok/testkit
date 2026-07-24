# TestLib 审计契约

## 审计与验证的区别

- `validate_testlib.py`：单独验证结构、索引和统计一致性
- `audit_testlib.py`：组合执行结构验证与语义重复、错放、provenance 风险审计
- `testspec-review`：针对一个变更评审需求追溯、覆盖和 oracle

三者互补，不能互相替代。

## 只读默认

审计脚本不得修改：

- feature documents
- `index.json`
- `.testlib.json`
- changelog
- review report

输出报告也必须通过显式 `--output` 才写文件。

## Finding 类型

| 类型 | 默认严重度 | 生命周期建议 |
|---|---|---|
| `INVALID_JSON` | error | repair-structure |
| `INVALID_CASES` | error | repair-structure |
| `DUPLICATE_CASE_ID` | 跨文件结构冲突为 error；同文件语义候选为 warning | merge-review |
| `DUPLICATE_TITLE` | warning | merge-review |
| `DUPLICATE_BODY` | warning | merge-review |
| `FEATURE_MISMATCH` | warning | relocate-or-revise |
| `MISSING_PROVENANCE` | warning | provenance-review |
| `INVALID_PROVENANCE` | warning | provenance-review |
| `UNVERIFIED_LEGACY_ACTIVE` | warning | reconcile |

重复候选只是检索结果，不等于可以自动合并。
组合报告会按 finding type 与 case ID 去掉结构/语义层对同一问题的重复计数；原始结构和语义子报告仍各自保留证据。
`recommended_findings` 是带建议的 finding 数，`lifecycle_candidates` 是这些 finding 涉及的去重 case ID 数；不得把同一用例的多个信号伪装成多条独立候选。

## 证据要求

生命周期结论必须记录：

- case IDs
- 当前 PRD 的 `REQ-*` / `AC-*`
- 如有，稳定 `Q-*`
- 选择的 action
- 影响范围
- 是否需要重新生成/评审

代码证据不是默认项。仅在用户明确授权并指定角色后使用，且必须标为 `observed`；不能把实现偶然行为写成产品意图。

## Handoff after confirmation

`testspec-audit` 永久只读。用户确认具体 proposal 后，向后续任务移交：

1. 新增或同 ID 内容更新交给 `testspec-publish`
2. retire/relocate/merge 交给单独授权、范围明确的维护任务
3. 后续任务必须更新 changelog、重建索引/统计并复跑验证

任何 `legacy-import + unverified` 用例都不能通过批量脚本直接升级为 verified。
