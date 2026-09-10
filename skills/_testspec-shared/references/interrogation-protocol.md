# TestSpec 质询协议

本协议是 `testspec-new`、`testspec-update` 和 `testspec-analysis` 共享的问题状态机。它负责确定哪些事实应由 Agent 查证、哪些产品决定必须由用户裁决，以及何时允许进入下游阶段。

## 职责边界

- `testspec-new`：从初始材料建立问题图和稳定 `Q-###`。
- `testspec-analysis`：发现风险与缺口，拆分复合问题，补充依赖和阶段阻塞；不得把新的产品回答写成 canonical requirement。
- `testspec-update`：接收产品回答，更新 decision 状态；只有本 skill 可以把 accepted/modified 决定写入 REQ/AC 并递增 `source_revision`。
- 下游 `plan/points/generate/review/publish`：只消费并原样传播直接上游的问题图。

问题分为：

- `fact`：可以从已授权 PRD、接口、UI、环境、工具或代码校准证据验证。Agent 负责查证，不把可查事实转问用户。
- `decision`：产品范围、规则、优先级或验收口径，需要用户或产品裁决。

推荐答案只能写为 `recommendation.status = proposed`。它不能成为 REQ、AC、oracle、测试优先级或已解决状态。

## Question schema

```json
{
  "id": "Q-001",
  "kind": "decision",
  "status": "open",
  "question": "重复请求是否返回同一业务结果？",
  "depends_on": [],
  "blocks_stages": ["plan", "points", "generate", "review", "publish"],
  "affects": ["REQ-003"],
  "source": "requirements.md#REQ-003",
  "recommendation": {
    "value": "建议返回同一业务结果，以建立可判定的幂等 oracle。",
    "status": "proposed"
  },
  "resolution": null
}
```

必需字段是 `id`、`kind`、`status`、`question`、`depends_on`、`blocks_stages`、`recommendation` 和 `resolution`。`recommendation` 可以为 `null`；非空时状态只能是 `proposed`。

状态只能是 `open`、`resolved`、`invalidated`、`deferred`。resolution 使用对象：

```json
{
  "outcome": "accepted",
  "value": "重复请求返回同一业务结果。",
  "source_ref": "产品回答 2026-09-11"
}
```

- decision：`accepted`、`modified`、`rejected`
- fact：`verified`、`refuted`、`inconclusive`
- `open` 必须使用 `null` resolution。
- `resolved` decision 只能是 accepted/modified；`resolved` fact 只能是 verified/refuted。
- rejected decision 使用 invalidated；inconclusive fact 使用 deferred。

## 建图与提问

1. 只登记会改变需求范围、测试策略、oracle、测试点、用例或 verdict 的问题。
2. 一个问题只表达一个可解决事项。配置、鉴权、外部可达性、数据语义和视觉验收必须拆成独立 fact。
3. `depends_on` 只引用同一 registry 中已存在的 Q-ID；不得自依赖或形成环。
4. 完整 frontier 是所有 `status = open` 且依赖均 resolved 的问题。
5. 默认只展示 frontier 中影响最高的一个问题并等待回答。
6. 用户明确接受批量模式时，最多展示少量彼此无依赖的 frontier 问题；不得展示依赖仍未解决的问题。
7. 回答改变问题图时重新计算完整 frontier，不维护虚假的固定问题总数。

Fact 优先由 Agent 从已授权来源查证并记录 `source_ref`。查不到的 fact 保持 open/deferred；不得改写为 decision 让用户猜测环境事实。

## 阶段门禁

进入目标阶段前运行：

```bash
python "<_testspec-shared>/scripts/validate_question_graph.py" \
  --input <直接上游产物> \
  --target-stage <analysis|plan|points|generate|review|publish>
```

以下任一情况阻断：

- 目标阶段存在 open/deferred blocker；
- blocker 因未解决依赖未出现在当前 frontier；
- Q-ID、依赖引用、状态、recommendation 或 resolution 非法；
- 问题图存在环。

没有列入目标阶段 `blocks_stages` 的执行期 fact 可以继续传播，但不能在未验证时被描述为通过。

## 旧版迁移

正常工作流只接受 `context_schema_version = 2`。旧 change 使用唯一迁移入口：

```bash
python "<_testspec-shared>/scripts/migrate_change_context.py" \
  --change-dir testspec/changes/<name> \
  --check
```

检查报告无歧义后改用 `--write`。迁移器消费旧 `blocking_open_questions`、`dynamic_followups` 和平面 questions；v2 产物不再写这些重复字段。
