# 使用 TestSpec 设计和维护测试用例

TestSpec 将需求材料转换为可审计的测试分析、测试点和测试用例。它以当前产品需求文档（PRD）为主基线，并通过显式分支处理需求更新、历史用例、代码证据和测试知识库（TestLib）维护。

## 理解主流程

主流程按上游事实到下游测试资产的顺序执行：

```text
testspec-new
→ testspec-update
→ testspec-analysis
→ testspec-points
→ testspec-generate
→ testspec-review
→ testspec-publish
```

`testspec-update` 可以重复执行。需求发生变化后，它会更新 `requirements.md`，并标记需要重新生成的下游产物。

| Skill | 主要职责 | 关键产物 |
|---|---|---|
| `testspec-new` | 创建测试变更并整理初始 PRD | `proposal.md`、`requirements.md` |
| `testspec-update` | 收敛新增或变更的需求事实 | 更新后的 `requirements.md`、影响摘要 |
| `testspec-analysis` | 分析风险、边界、状态和可测性 | `requirements-analysis.md` |
| `testspec-points` | 提炼验证目标，不编写操作步骤 | `specs/testpoints.md` |
| `testspec-generate` | 将测试点展开为完整用例 | JSON、Excel 或 XMind |
| `testspec-review` | 执行规则检查和启发式评审 | `review-report.md` |
| `testspec-publish` | 将评审通过的用例增量写入 TestLib | 模块用例、索引和 changelog |

## 收敛需求事实

当前 PRD、产品回答和验收规则是权威来源。TestLib、历史用例和代码只能提供回归提示或实现证据。

当产品补充接口文档、UI、权限规则或字段口径时，执行：

```text
testspec-update
```

如果实现与产品意图冲突，先记录差异并请求产品确认，再通过 `testspec-update` 修改 canonical requirements。

## 导入历史用例

`testspec-import` 支持 Excel、CSV、JSON、Markdown、TXT 和 XMind。导入结果只写入当前变更的隔离区，不会直接修改 TestLib。

```text
testspec-import legacy-cases.xlsx
```

旧用例必须在 `imports/reconciliation.json` 中按当前 PRD 分类。标记为 `legacy-import + unverified`、来源缺失或信任状态非法的内容不能通过 review 和 publish。

完成 reconciliation 后，重新执行 analysis、points、generate 和 review，生成原生候选用例。

## 使用代码校准需求

`testspec-code-calibrate` 只在你明确授权代码角色、Git ref 和仓库内 scope 后运行。它不会直接修改 `requirements.md`。

支持三种模式：

- **Comparison**：比较当前 PRD 与完整实现快照
- **Recovery**：从遗留实现恢复非 canonical 行为草稿
- **Change-diff**：比较生产、测试或需求分支的静态变更

```text
用代码校准当前 PRD，比较 main 和 feature/login 的登录行为
```

每种模式都生成经过校验的 `code-calibration.json`。代码与需求的冲突需要产品确认。

## 生成和评审用例

生成 Excel 或 XMind 用例：

```text
testspec-generate Excel
testspec-generate XMind
```

执行默认评审或深度评审：

```text
testspec-review
testspec-review --deep
```

评审会检查上游输入健康度、覆盖关系、用例字段、优先级、可执行性和 TestLib 信任边界。发现问题后，按报告指向返回 generate、points 或 analysis 修正。

## 发布和审计 TestLib

`testspec-publish` 只发布评审通过的用例，并按模块和功能增量合并：

```text
testspec-publish
```

`testspec-audit` 默认只读。它识别重复、错放、来源缺失和未验证历史导入，并输出 lifecycle proposal：

```text
testspec-audit
```

合并、废弃或迁移用例前，需要确认具体 case ID。

## 遵守 TestSpec 边界

执行 TestSpec 时遵守以下数据和权限边界：

- 不用代码覆盖当前 PRD
- 不把历史用例直接写入 TestLib
- 不跳过 analysis 和 points 直接扩写大量用例
- 不发布未通过 review 或 provenance 不完整的用例
- 不在审计阶段自动修改 TestLib

完整执行契约位于各 `skills/testspec-*/SKILL.md`。
