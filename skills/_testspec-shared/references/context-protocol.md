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

- **向下兼容**：canonical source 没有元数据或 `source_revision` 时，按 Legacy 模式继续并告警，不得仅因缺少版本而阻断
- **人类不可见**：元数据不干扰人类阅读产物
- **版本单调**：一旦 canonical source 出现 `source_revision`，所有后续 active workflow 产物必须逐级复制同一版本
- **stale 可收敛**：阶段重生成后，从传播给下游的 `stale_downstream_artifacts` 中移除本阶段产物；不得让历史 stale 标记永久阻断整条链
- **PRD-first**：默认权威源是已收敛的 PRD、产品回答和验收规则；代码仅在用户授权并明确角色时作为可选证据
- **来源可追溯**：用例和关键结论记录来源与信任状态；旧数据导入不得伪装成原生、已验证产物

---

## 传播介质

### Markdown 产物（proposal.md / requirements.md / requirements-analysis.md / testpoints.md）

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
  "blocking_open_questions": ["管理员和超级管理员的权限边界?", "并发修改时的优先级规则?"],
  "dynamic_followups": [],
  "source_revision": {
    "version": 2,
    "summary": "补充权限边界",
    "updated_by_skill": "testspec-update"
  },
  "stale_downstream_artifacts": ["specs/testpoints.md", "artifacts/testcases.json", "review-report.md"],
  "stale_reason": "需求源版本已更新",
  "next_skill": "testspec-points",
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
    "risks_identified": ["权限边界用例可能不完整，依赖阻塞澄清项"],
    "strategy_used": "functional + exception",
    "coverage_estimate": "TP 覆盖率 98%, 冒烟占比 30%",
    "blocking_open_questions": [],
    "dynamic_followups": [],
    "source_revision": {
      "version": 2,
      "summary": "补充权限边界",
      "updated_by_skill": "testspec-update"
    },
    "stale_downstream_artifacts": ["review-report.md"],
    "stale_reason": "需求源版本已更新",
    "next_skill": "testspec-review",
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
| `coverage_estimate` | string | 覆盖度估算 |
| `iteration_count` | number | 反思迭代次数（0 = 无迭代） |
| `iteration_summary` | string | 迭代修正摘要 |
| `blocking_open_questions` | string[] | 不确认就不能进入下一步分析或无法判断测试 oracle 的阻塞问题 |
| `dynamic_followups` | string[] | 测试执行中发现后再补充、不阻塞当前分析的问题 |
| `source_revision` | object | 当前需求源口径版本摘要 |
| `stale_downstream_artifacts` | string[] | 因需求源变化而需要重跑或复核的下游产物 |
| `stale_reason` | string | 下游过期原因摘要 |
| `next_skill` | string | stale 链中下一步应执行的 skill |
| `canonical_source_policy` | string | 默认 `prd-first`；当前只允许显式记录，不得静默切换为代码优先 |
| `evidence_sources` | object[] | PRD、产品回答、接口、UI、可选代码证据和 TestLib 历史来源 |
| `questions` | object[] | 带稳定 ID、状态、阻塞性和 resolution 的问题登记 |
| `origin` | object | 产物来源；常见 kind 为 testspec-native / legacy-import |
| `trust` | object | 产物信任状态：verified / provisional / unverified |

### Canonical revision envelope

以下字段组成版本传播 envelope：

- `source_revision`
- `blocking_open_questions`
- `dynamic_followups`
- `material_quality`
- `stale_downstream_artifacts`
- `stale_reason`
- `next_skill`

兼容规则：

- canonical source（优先 `requirements.md`，否则 `proposal.md`）没有 `source_revision`：视为 Legacy，可继续执行；输出中不得伪造版本。
- canonical source 有 `source_revision`：上述 envelope 对 active workflow 产物属于必传契约。数组没有内容时写 `[]`；没有 stale 时写空数组并省略 `stale_reason`、`next_skill`。
- `source_revision` 必须原样复制，不得由 analysis/points/generate/review 自行递增；只有 new/update 能建立或递增版本。
- 非 envelope 的分析性字段仍为可选，skill 按需填写。
- provenance 扩展字段 `canonical_source_policy`、`evidence_sources`、`questions` 为向后兼容的可选字段；一旦上游提供，下游必须原样传播。
- `canonical_source_policy` 缺失时按 `prd-first` 处理；不得因代码不可访问而阻断。
- `questions` 缺失时兼容读取两个旧数组；新建或更新需求源时应补齐稳定问题登记。
- 详细权威顺序、代码授权条件和用例 provenance 见 `source-provenance.md`。

### PRD Intake 相关字段（用于 requirements.md 闭环）

| 字段 | 类型 | 说明 | 播种者 |
|------|------|------|--------|
| `requirements_intake` | object | PRD Intake 执行结果 | new |
| `requirements_intake.generated` | boolean | 是否生成 requirements.md | new |
| `requirements_intake.path` | string | requirements.md 相对路径 | new |
| `requirements_intake.open_question_count` | number | 阻塞澄清项数量，不统计 dynamic_followups | new/update |
| `acceptance_quality` | string | 验收条件质量：high / medium / low | new |
| `requirement_quality` | object | requirements.md 六维质量复核结果 | new/update |
| `requirement_quality.completeness` | number | 完整性评分 0-100 | new/update |
| `requirement_quality.clarity` | number | 清晰性评分 0-100 | new/update |
| `requirement_quality.consistency` | number | 一致性评分 0-100 | new/update |
| `requirement_quality.testability` | number | 可测试性评分 0-100 | new/update |
| `requirement_quality.traceability` | number | 可追溯性评分 0-100 | new/update |
| `requirement_quality.feasibility` | number | 可行性评分 0-100 | new/update |
| `requirement_quality.overall_score` | number | 六维平均分 0-100 | new/update |
| `requirement_quality.readiness` | string | ready_for_analysis / needs_clarification / needs_revision / blocked | new/update |
| `source_revision.version` | number | 当前需求源口径版本，从 1 递增 | new/update |
| `source_revision.summary` | string | 本轮口径摘要 | new/update |
| `source_revision.updated_by_skill` | string | 最近更新口径的 skill 名称 | new/update |
| `stale_downstream_artifacts` | string[] | 需要重跑或复核的 requirements-analysis.md / testpoints.md / testcases.json / review-report.md 等 | update |
| `stale_reason` | string | 下游产物过期原因摘要 | update |
| `next_skill` | string | 需要重跑或复核的下一步 skill 名称 | update |

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
| `review_gate` | object | review 提供给 publish 的机器可读门禁：status, s1_unresolved_count, s1_issue_ids | review |
| `testlib_reuse.trust_filter` | string | 复用时采用的 provenance/trust 过滤规则 | analysis/points/generate |
| `origin.kind` | string | testspec-native / legacy-import | import/generate/publish |
| `trust.status` | string | verified / provisional / unverified | import/generate/publish |

---

## 消费规则

### 下游 skill 在执行前

1. 读取 canonical source：优先 `requirements.md`，否则 `proposal.md`。
2. 读取当前阶段的直接上游产物：
   - analysis ← requirements/proposal
   - points ← requirements-analysis/proposal
   - generate ← specs/testpoints.md
   - review ← artifacts/testcases.json（根目录 testcases.json 仅作 Legacy fallback）
3. 比较 canonical source 与直接上游的 `source_revision.version`：
   - canonical 无版本：Legacy 模式继续并告警。
   - canonical 有版本、直接上游缺少版本或版本更低：停止生成新的下游产物，提示重跑“直接上游 skill”。
   - 版本相等：继续并原样传播 envelope。
   - 直接上游版本高于 canonical：停止，提示版本元数据损坏，不猜测正确版本。
4. `stale_downstream_artifacts` 只有在目标产物缺少版本或版本低于 canonical 时才表示未解决；目标产物版本与 canonical 相等时，该 stale 项已解决。
5. 当前阶段成功重生成后：
   - 从传播列表移除当前阶段产物；
   - 保留仍未重生成的后续产物；
   - 将 `next_skill` 指向剩余列表中的第一阶段；列表为空时省略 `stale_reason`、`next_skill`。
6. 提取其余信息纳入思考协议的 Phase 1 材料评估：
   - `risks_identified` → 影响策略选择和覆盖重点
   - `blocking_open_questions` → 纳入待关注项
   - `material_quality` → 影响推理深度
   - `coverage_estimate` → 作为基线参考
   - `stale_reason` → 理解过期原因，辅助判断 rebaseline 范围
   - `dynamic_followups` → 仅记录为执行期关注点，不阻塞当前分析或生成
   - `canonical_source_policy` / `evidence_sources` → 保持 PRD-first，并只在用户授权范围内消费代码证据
   - `questions` → 按稳定 ID 合并产品回答，避免已解决问题以旧 wording 残留
   - `origin` / `trust` → 阻止未验证旧数据成为需求事实或 oracle

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
| testspec-new | proposal.md / requirements.md 末尾 | **canonical revision envelope**, signals_detected, requirements_intake, acceptance_quality, requirement_quality |
| testspec-update | proposal.md / requirements.md / affected downstream artifacts | source_revision, blocking_open_questions, dynamic_followups, stale_downstream_artifacts, requirements_intake, requirement_quality |
| testspec-analysis | requirements-analysis.md 末尾 | **canonical revision envelope**, risks_identified, strategy_used, **testlib_coverage** |
| testspec-points | specs/testpoints.md 末尾 | **canonical revision envelope**, coverage_estimate, risks_identified, **testlib_reuse** |
| testspec-generate | artifacts/testcases.json `_context` | **canonical revision envelope**, coverage_estimate, iteration_count, iteration_summary, **testlib_reference** |
| testspec-review | review-report.md 末尾 | **canonical revision envelope**, risks_identified（反馈给 generate/points/analysis） |
| testspec-publish | changelog `_context` | source_revision（versioned workflow 原样继承）, publish_summary, affected_modules, **new_cross_refs** |

---

## 适用边界

- 元数据是辅助信息，不替代 skill 自身的推理
- 不在元数据中传递完整的产物内容（只传摘要和信号）
- 元数据格式可扩展，下游应忽略不认识的字段
