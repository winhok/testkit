---
name: testspec-update
license: MIT
description: TestSpec 需求源更新与口径收敛（可重复执行的轻量 rebaseline）- 当已有 testspec/changes/{name}/ 后，用户补充、修改、删除、澄清或替换 PRD、产品回答、验收规则、接口/UI 口径和需求范围时使用。它是唯一能把 accepted/modified 产品决定晋升为 canonical REQ/AC 并增加 source revision 的 Skill，同时维护 question graph 和 stale 下游产物。
---

# testspec-update：需求源更新与口径收敛

铁律：PRD、API、UI 或产品意图变化后，绝不能让下游 artifact 继续伪装成与旧需求基线一致。

## 工作流

复制以下检查表，并在完成各项后勾选：

```text
TestSpec 更新进度：

- [ ] 步骤 1：定位当前 change 目录 ⚠️ 必需
- [ ] 步骤 2：对传入的 source 更新分类 ⚠️ 必需
- [ ] 步骤 3：收敛上游事实
- [ ] 步骤 4：重新计算需求状态
- [ ] 步骤 5：标记过期的下游 artifact
- [ ] 步骤 6：报告影响和后续 skill
```

## 适用范围

仅在 TestSpec change 工作区已经存在时使用。本 skill 更新当前 change 的 source of truth；不会新建 change，默认也不重新生成 analysis、测试点或用例。

## 共享规则

- 当前 change 目录：`../_testspec-shared/references/common.md`
- 输出契约：`../_testspec-shared/references/output-contracts.md`
- Context 元数据：`../_testspec-shared/references/context-protocol.md`
- Source 与信任策略：`../_testspec-shared/references/source-provenance.md`
- 问题状态机：`../_testspec-shared/references/interrogation-protocol.md`
- Requirements 模板：`../testspec-new/references/requirements-template.md`

## 执行规则

### 步骤 1：定位当前 change

应用共享 current-change 规则。没有 active change 时停止。canonical context 不是 schema v2 时，先运行 `migrate_change_context.py`，不得在 update 内隐式兼容。

### 步骤 2：对传入更新分类

优先依据用户最新输入和现有 artifact 分类，不要以澄清问卷开场。

在内部判断：

- 新输入是在新增、替换、修正还是删除需求？
- 变化的 source 类型是 PRD、API 文档、UI/原型、产品答复、业务规则、数据映射、权限规则，还是时间/日历规则？
- 是否与 `proposal.md`、`requirements.md`、`artifacts/source-prd.md`、`artifacts/api-doc.md` 或 `requirements-analysis.md` 中的陈述冲突？
- 是否影响已生成的 `specs/testpoints.md`、`artifacts/testcases.json`、Excel/XMind 文件或 `review-report.md`？

用户最新提供的信息优先于旧本地 artifact。除非用户明确说明两个版本并存，否则不得把旧表述保留为同等有效的替代项。

保持 `canonical_source_policy = prd-first`。本 skill 从不直接搜索代码。用户明确要求调查代码时，先交给 `testspec-code-calibrate`；只有产品答复解决 `conflict/code-only/unknown` 后，才能使用其已校验 artifact。绝不能静默替换 PRD 意图。

只有在答案会改变“写入、删除或将重要 artifact 标记为 stale”的决策，且无法从输入推断时，才询问用户。只问一个影响最大的阻塞问题，然后停止。

### 步骤 3：收敛上游事实

确保 `artifacts/` 存在，然后创建或更新 source artifact：

- `proposal.md`：更新关联 source、范围说明和 context 元数据。
- `requirements.md`：缺失时按 `../testspec-new/references/requirements-template.md` 创建；否则合并变更需求、移除已删除需求、更新 source，并尽量保持 REQ/RISK ID 稳定。
- `artifacts/source-prd.md`：PRD、产品答复、业务规则、UI 图片或原型材料变化时创建或更新。
- `artifacts/api-doc.md`：API、技术接口、字段、响应结构或错误码材料变化时创建或更新。
- `artifacts/code-calibration.json`：来自 `testspec-code-calibrate` 的只读证据输入；不得在此重写。只有明确的产品裁决可以改变 canonical requirement。
- `artifacts/recovered-prd-draft.md`：non-canonical recovery 输入；只提升已确认陈述，并在 `requirements.md` 中分配新的 REQ/AC ID。
- `artifacts/update-log.md`：需要标记 Excel/XMind 等过期二进制导出且不能内联编辑时创建或更新。

在现有 change 目录首次创建 `requirements.md` 时，将其视为该 change 的首个 canonical requirements source：设置 `source_revision.version` 为 `1`，`source_revision.updated_by_skill` 为 `testspec-update`。

使用 calibration 输入前，先运行对应 validator：comparison 模式使用 `--canonical requirements.md`；recovery 模式使用 `--draft artifacts/recovered-prd-draft.md`；change-diff 模式先校验 snapshot，再使用 `--canonical requirements.md --snapshot artifacts/change-snapshot.json`。将每个已回答的 calibration `Q-*` 连同 resolution 和 `CAL-*` / `OBS-*` source reference 复制到 canonical `questions` registry，绝不能修改 calibration artifact。requirements revision 变化后，该 artifact 只能作为历史 `evidence_sources` 输入保留；除非基于新 revision 重新校准，否则不得继续作为当前 `code_calibration` 传播。

#### 接口替换模式

用户提供与旧接口事实冲突的最新 API 文档时，不要只修补零散词句。把 `artifacts/api-doc.md` 作为该 change 的 API truth source：

- 根据最新文档重建或同步 `artifacts/api-doc.md` 中受影响的 API 部分。
- 从 `requirements.md` 移除已被替代的 endpoint、字段或响应结构陈述，不要保留两个版本。
- 反向更新依赖旧 API 结构的验收标准。
- 在影响摘要记录新旧 API 差异。

例如：旧报表接口返回厂商专用渲染配置，而最新契约返回规范化 series data 时，`api-doc.md` 和关联 REQ 验收标准只能保留规范化 series 契约。

#### UI 输入

补充 UI 图片或原型时，先在 `artifacts/source-prd.md` 记录输入；只有 UI 证据改变可观察行为或验收标准时，才更新或新增 `requirements.md` REQ。使用以下结构：

```markdown
## UI 补充记录

| 页面 | 状态 | 入口 | 筛选/弹层 | Tooltip | 跳转 | 权限/空态 | 数据字段 | 来源 |
|------|------|------|-----------|---------|------|-----------|----------|------|
| <page> | <state> | <entry> | <filter/modal> | <tooltip> | <navigation> | <permission/empty> | <fields> | <image/link/user answer> |
```

### 步骤 4：重新计算需求状态

每次更新 `requirements.md` 后：

- 重新计算六项需求质量分：completeness、clarity、consistency、testability、traceability、feasibility。
- 重新计算 `requirement_quality.readiness`。
- 写 context 前读取现有 `source_revision.version`。成功更新 requirements source 后写入 `old_version + 1`；没有旧版本或刚创建 `requirements.md` 时从 `1` 开始。始终将 `source_revision.updated_by_skill` 设为 `testspec-update`。
- 在 `questions` 中保持稳定 `Q-###`，补齐 kind、depends_on、blocks_stages、proposed recommendation 和结构化 resolution。
- accepted/modified decision 同步写入 canonical REQ/AC；rejected 使用 invalidated，暂缓使用 deferred。
- Agent 仅凭已授权证据解决 fact；不得把 recommendation 当作回答。
- `requirements_intake.open_question_count` 统计阻塞 analysis 的 active questions。
- 重新评估 `strategy_requirement`；本轮只做简单单环境纯用例设计时可 skipped，其余复杂信号使用 required。

例如，“执行时验证未知文件类型”是非阻塞 fact；“未知类型归到哪个产品分类”是 decision，可阻塞 plan/points。

### 步骤 5：标记过期下游 artifact

任何下游 artifact 可能不再匹配更新后的 source 时，按不破坏文件格式的方式标记 stale：

Markdown 文件（`requirements-analysis.md`、`strategy.md`、`specs/testpoints.md`、`review-report.md`）：
```markdown
> 注意：旧口径，仅供历史参考。此 artifact 基于旧需求基线生成，依赖前请重新运行指定的上游 skill。
```

JSON 文件（`artifacts/testcases.json`）：

- 保持合法 JSON。
- 更新或新增 `_context.stale_downstream_artifacts`、`_context.stale_reason` 和 `_context.next_skill`。
- 不得在 JSON 前添加 Markdown 或纯文本。

Excel/XMind 文件：

- 不得向二进制导出写入内联提示。
- 在 `artifacts/update-log.md` 和最终答复中标记 stale。
- 需要机器可读标记时，创建或更新 `artifacts/stale-artifacts.json` 等 sidecar metadata 文件。

使用以下默认值：

- 重大 PRD/API/UI/业务规则变化后，`requirements-analysis.md` 标记 stale；下一步：`testspec-analysis`。
- strategy 已存在或新 requirement 为 required 时，`strategy.md` 标记 stale；analysis 重跑后确认是否仍需 plan。
- 影响分析的需求变化后，`specs/testpoints.md` 标记 stale；下一步：`testspec-points`。
- 影响测试点的变化后，`artifacts/testcases.json`、Excel、XMind 标记 stale；下一步：`testspec-generate`。
- 需要重新生成用例后，`review-report.md` 标记 stale；下一步：`testspec-review`。

对 `requirements-analysis.md`，还要清理会误导读者的明显冲突：

- 将已明确被替代的摘要、优先问题或澄清项移入简短的“旧口径历史记录”，或标为“已失效”。
- 不重写完整分析；正确下一步仍是 `testspec-analysis`。
- stale 提示下方不得继续把直接冲突的陈述显示为有效结论。

除非用户明确要求，否则不删除旧下游 artifact。

硬规则：完成 stale 标记后，更新 `requirements.md` 最后的 `testspec-context` 块。它必须包含 `stale_downstream_artifacts`、`stale_reason`、`next_skill` 和刷新的 `source_revision`。下游 `testspec-analysis` 依赖该上游标记判断旧分析能否复用。

### 步骤 6：报告影响

最终报告包含：

- 更新的文件
- 新增、修改、删除的 REQ ID
- 各目标阶段的 active blocker 数量
- 非阻塞 open/deferred fact 数量
- stale artifact 和下一步应运行的准确 skill

若存在 active decision，输出 frontier 中“可复制给产品的问题清单”；可查 fact 由 Agent 处理：

```markdown
## 当前产品决策 frontier
1. [P0/P1/P2] <问题>（影响：<阻塞的分析/验收判断>；需要产品给出：<规则/范围/样例/口径>）
```

```markdown
## 非阻塞事实跟进
1. <问题>（触发条件：<测试执行中发现时>；处理方式：<提给产品补充后再纳入验收>）
```

每个问题必须关联 REQ/RISK/source；只展示依赖已解决的 frontier。

## 反模式

- 不为已有 change 新建工作区。
- 新增产品输入时，必须移除或修正与之冲突的旧结论。
- 不得让过时的 API/UI/业务表述继续在 `requirements.md` 中显示为有效。
- 上游事实变化时，不得遗漏 `requirements-analysis.md` 的 stale 标记。
- 不得向 JSON、Excel、XMind 或其他非 Markdown artifact 添加 Markdown stale 提示。
- stale 提示下不得保留明显冲突的旧分析结论为 active。
- 最新 API 文档改变响应结构、字段或验收标准时，不得只当作次要备注。
- 不得把执行期发现任务归为阻塞问题。
- 除非用户明确要求，不重新生成 analysis、points、cases 或 review。

## 交付前检查

- [ ] 更新后的 source 文件不含仍生效的旧结论。
- [ ] `requirements.md` 只使用 context schema v2 question graph，没有重复兼容数组。
- [ ] `canonical_source_policy` 仍为 `prd-first`；未直接扫描代码，且 calibration 输入在改变意图前已校验并经产品裁决。
- [ ] 产品答复使用结构化 resolution；accepted/modified 已写入 REQ/AC 并增加 revision。
- [ ] `requirements.md` 已存在；若由本次更新创建，其 context 包含 `source_revision.version = 1` 和 `updated_by_skill = testspec-update`。
- [ ] 更新已有 `requirements.md` source 时，`source_revision.version` 增加 1，且 `updated_by_skill = testspec-update`。
- [ ] `requirements_intake.open_question_count` 只统计阻塞 analysis 的 active questions。
- [ ] `requirement_quality.readiness` 与重算后的阻塞状态和分数一致。
- [ ] 最新 API 文档若有冲突，已重建或同步 `artifacts/api-doc.md`，并反向更新受影响的 REQ 验收标准。
- [ ] UI 补充已记录在 `artifacts/source-prd.md`，并使用固定的页面/状态/入口/弹层/tooltip/跳转/权限/数据字段结构。
- [ ] readiness 不是 `ready_for_analysis` 时，最终答复包含可复制的产品问题清单。
- [ ] 每个受影响的下游 artifact 仍有效，或已在不破坏格式的前提下标记 stale。
- [ ] `requirements.md` context 列出全部 stale downstream artifact，以及 `stale_reason` 和 `next_skill`。
