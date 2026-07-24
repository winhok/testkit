# specs/testpoints.md 模板

```markdown
# 测试点：<被测对象>

## 概述
<一两句话说明本次测试覆盖范围与重点>

## 知识库复用摘要

> 仅在 testlib 实际命中时输出。

| 模块 | 功能点 | testlib 历史覆盖 TP 数 | 本次策略 |
|------|--------|-------------------------|----------|
| <模块> | <功能> | N | 复用 / 新增 / 替代 |

## 可复用资产

> 仅在发现可复用项时输出。

- testlib 可直接复用：<功能点及路径>
- 自动化友好区域：<模块及原因>
- 可共享测试数据：<数据类型及模块>
- 快速收益点：<TP_ID 及说明>

## 命名字典

### 模块字典

| 模块名称 | MODULE |
|----------|--------|
| <模块名称> | <2-5 位大写缩写> |

### 功能点字典

| 模块名称 | 功能点名称 | FEATURE |
|----------|------------|---------|
| <模块名称> | <功能点名称> | <2-10 位大写缩写> |

### [模块名称]模块

#### [功能点名称]功能

##### 功能验证点 (Functional)

- TP_<MODULE>_<FEATURE>_001: <测试点名称>
  - 验证要点: <验证什么（What），不写步骤/数据>
  - 优先级: P1/P2/P3
  - Oracle 状态: confirmed/needs-confirmation
  - Oracle 范围: direct/contract/indirect/out-of-scope
  - 回归层级: Smoke/Full/Targeted
  - 关联需求: <需求编号/段落>

##### 边界验证点 (Boundary)

##### 异常验证点 (Exception)

##### 集成验证点 (Integration)

##### 非功能性验证点 (Non-Functional)

<!-- testspec-context
{
  "source_skill": "testspec-points",
  "canonical_source_policy": "prd-first",
  "evidence_sources": [],
  "questions": [],
  "source_revision": {"version": "<canonical 版本>", "summary": "<原样继承>", "updated_by_skill": "<原样继承>"},
  "blocking_open_questions": [],
  "dynamic_followups": [],
  "material_quality": "<从上游继承>",
  "stale_downstream_artifacts": [],
  "coverage_estimate": "<覆盖摘要>",
  "risks_identified": [],
  "regression_tiers": {"smoke": [], "full": [], "targeted": []},
  "testlib_reuse": {"trust_filter": "exclude legacy-import+unverified from facts/oracles", "existing_tp_ids": [], "new_tp_ids": []}
}
-->
```
