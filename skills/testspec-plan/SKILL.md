---
name: testspec-plan
license: MIT
description: TestSpec 测试策略规划阶段。为多环境、多 runner、跨组件、非功能测试、真实执行或大型测试拆分设计最少且证据充分的测试 seam、oracle、环境与 capability matrix、证据策略和准入退出条件，产出当前 change 的 strategy.md。用户明确要求测试策略、怎么证明、测试层级或执行证据方案时使用。分析需求风险使用 testspec-analysis；列测试点使用 testspec-points；生成具体步骤和预期结果使用 testspec-generate。
---

# testspec-plan：测试策略

铁律：strategy 只定义“如何证明”，不得新增产品行为、验收规则或实现要求；满足证据充分性的最少 seams 优先。

```text
TestSpec 策略进度：

- [ ] 步骤 1：定位 change 并读取当前 requirements-analysis.md ⚠️ 必需
- [ ] 步骤 2：校验 context schema、revision 和 plan blocker ⚠️ 必需
- [ ] 步骤 3：设计最少充分 seams、oracle、环境、能力和证据
- [ ] 步骤 4：写入 strategy.md 和完整 v2 context
- [ ] 步骤 5：验证产物并报告下一步
```

## 职责

输入当前 revision 的 canonical requirements 与 `requirements-analysis.md`，产出：

```text
testspec/changes/<name>/strategy.md
```

边界固定为：

- requirements：产品做什么、如何验收
- analysis：为什么存在风险和缺口
- strategy：如何取得足够证据
- points：要验证什么
- cases：具体步骤、数据和预期结果

## 何时必需

`strategy_requirement.status = required` 时不能跳过本阶段。以下任一信号应由 new/update/analysis 标记 required：

- 多环境或多 runner
- 跨组件或跨服务
- 非功能测试
- 真实执行或外部依赖验证
- 大型测试拆分
- 需要多个互补 oracle 或证据面
- 存在 capability、fallback 或 inconclusive 决策

简单、单环境、纯用例设计可以标记 skipped。用户明确要求测试策略时，即使上游判定可跳过，也可以生成 optional strategy；不得借此改变产品口径。

## 共享规则源

- context 与阶段传播：`../_testspec-shared/references/context-protocol.md`
- 质询与 blocker：`../_testspec-shared/references/interrogation-protocol.md`
- 输出契约：`../_testspec-shared/references/output-contracts.md`
- strategy 模板：`references/strategy-template.md`
- 来源权威与信任：`../_testspec-shared/references/source-provenance.md`

## 执行步骤

1. 按共享 current-change 规则定位唯一 change。
2. 读取 `requirements.md`（否则 proposal）与 `requirements-analysis.md`。analysis 缺失、revision 不同或 context 不是 v2 时停止。
3. 运行：

   ```bash
   python "<_testspec-shared>/scripts/validate_question_graph.py" \
     --input <change>/requirements-analysis.md \
     --target-stage plan
   ```

   blocker、隐藏 blocker、循环或非法 resolution 存在时不写 strategy。
4. 加载 `references/strategy-template.md`，只记录会改变后续测试选择或 verdict 的内容。
5. 为每条 REQ、RISK 和相关 Q-ID选择证据。优先复用已有 seam；一个 seam 能充分证明时不重复，多个 seam 分别证明不同事实时全部保留。
6. 对每个 oracle 标明来源、可观察值和不可判定条件。reference 代码、历史用例和 recommendation 不能单独成为产品 oracle。
7. 写 `strategy.md`，原样传播 `source_revision`、`questions`、`strategy_requirement` 和来源字段；从 stale 列表移除 `strategy.md`，其余顺序保持不变，下一步指向 `testspec-points`。
8. 运行 context chain validator `--through plan`，通过后再报告完成。

## 必需内容

- scope / out-of-scope
- fewest sufficient test seams
- oracle catalog
- environment matrix
- capability matrix
- evidence strategy
- coverage tiers
- entry / exit criteria
- fallback / inconclusive conditions
- canonical revision envelope
- REQ / RISK / Q 追溯

## 禁止事项

- 不把“理想只有一个 seam”当硬目标。
- 不重新采访已由 requirements 决定的产品行为。
- 不把 recommendation、代码现状或历史用例直接晋升为需求。
- 不写具体测试步骤、账号、数据值或逐条 expected result。
- 不访问真实环境或执行测试。
- 不在 blocker 未清零时生成看似完整的 strategy。

## 交付前检查

- [ ] strategy 只回答如何证明，没有新产品规则。
- [ ] 每个 seam 都对应独立证据价值。
- [ ] oracle 均有权威来源和 inconclusive 条件。
- [ ] 环境与 capability 缺口有 fallback，不伪造可执行性。
- [ ] REQ、RISK、Q 追溯完整。
- [ ] v2 context、revision、questions 和 stale 链验证通过。
