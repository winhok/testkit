# 测试策略：<变更名称>

## 范围

- In scope：<引用 REQ/RISK>
- Out of scope：<明确排除项及来源>

## 最少充分测试 Seams

| Seam | 证明目标 | 覆盖 REQ/RISK/Q | 为什么需要 | 替代/重叠证据 |
|---|---|---|---|---|
| <API/UI/service/DB/event/log> | <可观察行为> | <IDs> | <独立证据价值> | <可替代或不可替代> |

## Oracle Catalog

| Oracle | 权威来源 | 可观察值 | 通过条件 | Inconclusive 条件 |
|---|---|---|---|---|
| <名称> | <REQ/API/已授权证据> | <结果> | <判定规则> | <证据不足条件> |

## Environment Matrix

| 环境 | 用途 | 允许操作 | 数据隔离 | 限制 |
|---|---|---|---|---|
| <环境> | <目标> | <read/write/execute> | <方式> | <缺口> |

## Capability Matrix

| 能力 | 状态 | 证据 | 影响 | Fallback |
|---|---|---|---|---|
| <browser/api/db/log/device/runner> | <available/limited/unavailable> | <来源> | <覆盖影响> | <替代证据或 inconclusive> |

## Evidence Strategy

| 证据 | 采集位置 | 关联 Oracle | 保留方式 | 隐私/脱敏 |
|---|---|---|---|---|
| <响应/截图/DB snapshot/trace/report> | <seam> | <oracle> | <artifact> | <规则> |

## Coverage Tiers

- Smoke：<最低可接受信号>
- Targeted：<变更风险覆盖>
- Full：<完整范围>

## Entry / Exit Criteria

- Entry：<开始测试所需状态>
- Exit：<完成且可判定所需证据>

## Fallback / Inconclusive

- <能力缺失或证据冲突时如何降级；何时必须给出 inconclusive>

## Traceability

| REQ/RISK/Q | Seam | Oracle | Evidence | Coverage tier |
|---|---|---|---|---|
| <ID> | <seam> | <oracle> | <evidence> | <tier> |

<!-- testspec-context
{
  "context_schema_version": 2,
  "source_skill": "testspec-plan",
  "source_revision": {"version": 1, "summary": "<原样继承>", "updated_by_skill": "<原样继承>"},
  "questions": [],
  "strategy_requirement": {"status": "required", "reasons": ["<原样继承>"]},
  "material_quality": "<原样继承>",
  "stale_downstream_artifacts": ["specs/testpoints.md", "artifacts/testcases.json", "review-report.md"],
  "stale_reason": "<仍有 stale 时继承>",
  "next_skill": "testspec-points"
}
-->
