# TestSpec 上下文传播协议 v2

TestSpec active workflow 只接受 `context_schema_version = 2`。旧 change 必须先运行 `scripts/migrate_change_context.py`；正常工作流不包含 Legacy fallback。

## 设计原则

- **版本单调**：new 建立、update 递增 `source_revision`；其余阶段原样传播。
- **问题可计算**：`questions` 使用共享依赖图协议，阶段门禁检查完整图而非只看当前展示问题。
- **策略可判定**：`strategy_requirement` 明确 plan 是 required 还是 skipped。
- **stale 可收敛**：阶段重生成后移除自己的 stale 路径，保留后续路径并更新 `next_skill`。
- **PRD-first**：canonical requirements、证据来源与 TestLib 信任遵循 `source-provenance.md`。
- **单一直接上游**：plan 之后的阶段必须原样传播 questions 与 strategy requirement。

## 传播介质

Markdown 产物在末尾使用：

```markdown
<!-- testspec-context
{
  "context_schema_version": 2,
  "source_skill": "testspec-analysis",
  "source_revision": {
    "version": 2,
    "summary": "补充权限边界",
    "updated_by_skill": "testspec-update"
  },
  "questions": [],
  "strategy_requirement": {
    "status": "required",
    "reasons": ["cross-component", "real-execution"]
  },
  "material_quality": "high",
  "stale_downstream_artifacts": [
    "strategy.md",
    "specs/testpoints.md",
    "artifacts/testcases.json",
    "review-report.md"
  ],
  "stale_reason": "需求源版本已更新",
  "next_skill": "testspec-plan"
}
-->
```

`artifacts/testcases.json` 在顶层对象的 `_context` 使用同一结构；顶层 testcase `schema_version` 保持独立，不得与 `context_schema_version` 混用。

## Canonical revision envelope

active workflow 必传：

- `context_schema_version`
- `source_revision`
- `questions`
- `strategy_requirement`
- `material_quality`
- `stale_downstream_artifacts`
- 有 stale 时的 `stale_reason` 和 `next_skill`

可选分析字段包括 `thinking_summary`、`signals_detected`、`risks_identified`、`strategy_used`、`coverage_estimate`、`iteration_count`、`iteration_summary`、`canonical_source_policy`、`evidence_sources`、`code_calibration`、`origin` 和 `trust`。

`code_calibration` 只能引用已通过 `validate_code_calibration.py` 且与 canonical revision 匹配的 artifact；不得内联代码或绕过 PRD-first 权威顺序。

v2 不写 `blocking_open_questions`、`dynamic_followups`、`open_questions` 或 `blocking`。问题状态、依赖和阶段影响全部由 `questions[]` 表达，详见 `interrogation-protocol.md`。

## Strategy requirement

```json
{
  "strategy_requirement": {
    "status": "required",
    "reasons": ["multiple-environments"]
  }
}
```

status 只能是：

- `required`：进入 points 前必须存在 current revision 的 `strategy.md`。
- `skipped`：当前 revision 可以从 analysis 直接进入 points；reasons 必须解释原因。

new/update 进行初判，analysis 可根据风险和证据复杂度从 skipped 提升为 required。plan 及其下游不得修改该字段。迁移完成的既有 revision 使用 skipped + `migrated-existing-revision`，避免反推一份未经确认的 strategy；下一次 revision 重新评估。

required 信号：多环境、多 runner、跨组件、非功能、真实执行、大型拆分、多个互补 oracle，或 capability/fallback/inconclusive 决策。简单单环境纯用例设计可以 skipped。

## 直接上游

```text
analysis ← requirements.md（否则 proposal.md）
plan     ← requirements-analysis.md
points   ← strategy.md（required）或 requirements-analysis.md（skipped）
generate ← specs/testpoints.md
review   ← artifacts/testcases.json
publish  ← review-report.md + artifacts/testcases.json
```

正常 v2 workflow 不使用 root `testcases.json` fallback。旧根目录用例先通过 `testspec-import` 隔离或重新生成；context 迁移器只更新已有 canonical `artifacts/testcases.json`。

## 阶段消费

每个阶段执行前：

1. 读取 canonical source 和直接上游。
2. 要求 `context_schema_version = 2`；否则停止并提示迁移。
3. 要求 `source_revision` 与 canonical 完全一致。
4. 调用 question validator，并传入目标阶段。
5. plan 之后要求 questions 与 strategy_requirement 和直接上游完全一致。
6. 目标产物 current revision 时，即使上游 stale 列表仍包含其路径，也视为已重建；生成本阶段输出时清除该路径。

阶段成功后按顺序选择下一 stale：

```text
requirements-analysis.md
strategy.md
specs/testpoints.md
artifacts/testcases.json
review-report.md
```

strategy skipped 时列表不得包含 `strategy.md`。stale 为空时省略 `stale_reason` 和 `next_skill`。

## Questions propagation

- new/update 可以维护 canonical registry。
- analysis 可以增加 fact/decision 或解决有充分证据的 fact；不能解决产品 decision。
- plan、points、generate、review、publish 原样传播直接上游 registry。
- recommendation 永远 proposed。
- accepted/modified decision 只有经 testspec-update 写入 requirements 并增加 revision 后，才成为 canonical 产品规则。

## PRD intake 字段

| 字段 | 说明 | 播种者 |
|---|---|---|
| `requirements_intake` | requirements 生成路径和问题统计 | new/update |
| `acceptance_quality` | 验收条件质量 | new |
| `requirement_quality` | 六维评分及 readiness | new/update |
| `source_revision` | 当前产品口径版本 | new/update |
| `strategy_requirement` | 当前 revision 是否要求 plan | new/update/analysis |

`requirements_intake.open_question_count` 统计 active decision/fact 中会阻塞 analysis 的数量。

## TestLib 字段

| 字段 | 说明 | 播种者 |
|---|---|---|
| `testlib_coverage` | 已有覆盖、可复用功能与回归风险 | analysis |
| `testlib_reuse` | existing/new TP IDs 和 trust filter | points |
| `testlib_reference` | generate 实际参考的已有功能 | generate |
| `review_gate` | publish 使用的机器可读门禁 | review |
| `new_cross_refs` | publish 新增交叉引用 | publish |

TestLib 只提供回归、命名和表达参考，不成为产品事实或新 oracle。

## 验证命令

```bash
python "<_testspec-shared>/scripts/validate_question_graph.py" \
  --input <直接上游> --target-stage <stage>

python "<_testspec-shared>/scripts/validate_context_chain.py" \
  --change-dir testspec/changes/<name> --through <stage>
```

任何阶段不得通过手写警告绕过 validator。
