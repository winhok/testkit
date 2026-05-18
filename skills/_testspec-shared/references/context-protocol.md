# TestSpec 上下文传播协议（Context Protocol）

> 跨 skill 上下文传播契约。允许上游 skill 的推理结论、风险发现、质量评估等元数据传递给下游 skill，使下游能基于上游的洞察做更好的决策。

## 目录

- 设计原则
- 传播介质
- 元数据字段定义
- 消费规则
- 回溯机制
- 各 skill 的播种责任
- 适用边界

## 设计原则

- **向下兼容**：无元数据时，下游按正常流程执行，不报错
- **人类不可见**：元数据不干扰人类阅读产物
- **消费可选**：下游 skill 可以读取元数据，但不依赖它

---

## 传播介质

### Markdown 产物（proposal.md / requirements-analysis.md / testpoints.md）

在文件末尾追加 HTML 注释块：

```markdown
<!-- testspec-context
{
  "source_skill": "testspec-analysis",
  "timestamp": "2026-03-18T15:00:00",
  "thinking_summary": "材料信息密度中等，核心风险在权限控制和并发场景",
  "signals_detected": ["权限矩阵不完整", "并发场景未描述"],
  "risks_identified": ["角色权限交叉可能导致越权", "并发修改无锁机制"],
  "material_quality": "medium",
  "strategy_used": "completeness + testability + logic",
  "open_questions": ["管理员和超级管理员的权限边界?", "并发修改时的优先级规则?"],
  "coverage_estimate": "functional 90%, boundary 70%, exception 60%"
}
-->
```

### JSON 产物（testcases.json）

在顶层对象中追加 `_context` 字段：

```json
{
  "schema_version": 2,
  "_context": {
    "source_skill": "testspec-generate",
    "thinking_summary": "基于功能测试策略展开，重点补充了权限和并发场景",
    "signals_detected": ["上游标注权限风险", "上游标注并发风险"],
    "risks_identified": ["权限边界用例可能不完整，依赖待澄清项"],
    "strategy_used": "functional + exception",
    "coverage_estimate": "TP 覆盖率 98%, 冒烟占比 30%",
    "iteration_count": 1,
    "iteration_summary": "Round 1 补充了 3 条权限异常用例"
  },
  "testcases": [...]
}
```

> 现有脚本（generate_excel.py / generate_xmind.py）只读取 `testcases` 数组，`_context` 字段不影响输出。

---

## 元数据字段定义

| 字段 | 类型 | 说明 |
|------|------|------|
| `source_skill` | string | 产生此元数据的 skill 名称 |
| `timestamp` | string | 生成时间（ISO 8601） |
| `thinking_summary` | string | 推理过程摘要（1-2 句） |
| `signals_detected` | string[] | 检测到的关键信号 |
| `risks_identified` | string[] | 识别到的风险 |
| `material_quality` | string | 材料质量评估：high / medium / low |
| `strategy_used` | string | 使用的策略组合 |
| `open_questions` | string[] | 未解决的问题（待澄清项） |
| `coverage_estimate` | string | 覆盖度估算 |
| `iteration_count` | number | 反思迭代次数（0 = 无迭代） |
| `iteration_summary` | string | 迭代修正摘要 |

所有字段均为可选。skill 按需填写，不强制要求全部填写。

### testlib 相关字段（用于知识库闭环）

| 字段 | 类型 | 说明 | 播种者 |
|------|------|------|--------|
| `testlib_coverage` | object | 从 index.json 扫描得到的已有覆盖情况 | analysis |
| `testlib_coverage.scanned` | boolean | 是否成功扫描了 testlib | analysis |
| `testlib_coverage.related_modules` | string[] | 匹配到的 testlib 模块目录名 | analysis |
| `testlib_coverage.existing_case_count` | number | 相关模块已有用例总数 | analysis |
| `testlib_coverage.reusable_features` | string[] | 可直接复用的功能点（无需新增测试点） | analysis |
| `testlib_coverage.regression_risk_features` | string[] | 可能需要回归验证的功能点 | analysis |
| `testlib_reuse` | object | 从 testlib 检索到的复用信息 | points |
| `testlib_reuse.existing_tp_ids` | string[] | testlib 历史用例覆盖过的 TP_ID（用于复用/回归判断） | points |
| `testlib_reuse.new_tp_ids` | string[] | 本次新增的 TP_ID | points |
| `testlib_reference` | object | 参考 testlib 已有用例的信息 | generate |
| `testlib_reference.referenced_features` | string[] | 参考了哪些功能的已有用例 | generate |
| `new_cross_refs` | array | 本次 publish 新建立的交叉引用 | publish |

---

## 消费规则

### 下游 skill 在执行前

1. 检查上游产物是否包含上下文元数据
2. **有元数据**：提取关键信息纳入思考协议的 Phase 1 材料评估
   - `risks_identified` → 影响策略选择和覆盖重点
   - `open_questions` → 纳入待关注项
   - `material_quality` → 影响推理深度
   - `coverage_estimate` → 作为基线参考
3. **无元数据**：按正常流程执行（向下兼容）

### 消费示例

```
testspec-points 读取 requirements-analysis.md 时：
  → 发现 risks_identified: ["角色权限交叉可能导致越权"]
  → 在权限模块增加更细粒度的测试点
  → 将 "并发修改无锁机制" 标记为高优先级测试点
```

---

## 回溯机制

当下游 skill 在执行过程中发现上游产物质量不足时：

### 发现信号

- 从 analysis 提炼测试点时，发现分析结论过于笼统，无法提炼
- 从 testpoints 展开用例时，发现测试点验证要点模糊
- review 发现系统性覆盖缺口

### 处理方式

**不默默降级**，而是：

1. 标记发现的问题
2. 提供选项给用户：
   - 选项 A：回到上游 skill 补充分析/测试点
   - 选项 B：在当前步骤尽力弥补，标注风险
   - 选项 C：继续执行，在 review 阶段集中处理
3. 用户选择后按选项执行

---

## 各 skill 的播种责任

| Skill | 播种位置 | 关键字段 |
|-------|---------|---------|
| testspec-new | proposal.md 末尾 | material_quality, signals_detected |
| testspec-analysis | requirements-analysis.md 末尾 | risks_identified, open_questions, strategy_used, material_quality, **testlib_coverage** |
| testspec-points | specs/testpoints.md 末尾 | coverage_estimate, risks_identified, **testlib_reuse** |
| testspec-generate | testcases.json `_context` | coverage_estimate, iteration_count, iteration_summary, **testlib_reference** |
| testspec-review | review-report.md 末尾 | risks_identified（反馈给 generate/points/analysis） |
| testspec-publish | changelog `_context` | publish_summary, affected_modules, **new_cross_refs** |

---

## 适用边界

- 元数据是辅助信息，不替代 skill 自身的推理
- 不在元数据中传递完整的产物内容（只传摘要和信号）
- 元数据格式可扩展，下游应忽略不认识的字段
