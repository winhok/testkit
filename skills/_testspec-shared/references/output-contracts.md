# TestSpec 输出契约

> 目标：集中维护 `testspec-*` skills 的产物结构约束。此文件是共享契约，不改变既有导出脚本或历史产物格式。

## 目录

- 兼容性原则
- requirements.md
- requirements-analysis.md
- specs/testpoints.md
- testcases.json
- Excel 输出契约
- XMind 输出契约
- 变更控制

## 兼容性原则

- `proposal.md`、`requirements.md`、`requirements-analysis.md`、`specs/testpoints.md` 的 Markdown 结构保持兼容现有模板。
- `testcases.json`、Excel、XMind 的字段与层级以生成脚本及单测为准。
- 如文档说明与脚本行为冲突，必须以脚本和单测为准，不得擅自改动历史 schema。

## requirements.md

`requirements.md` 是 testspec-new 从原始 PRD/需求片段净化出的可验收需求源，供 testspec-analysis 优先读取。它不是测试分析报告，不包含测试点、测试步骤或技术实现方案。

兼容结构：

```markdown
# 可验收需求：<被测对象>

## 需求来源
- 原始 PRD：<链接/路径/摘要>
- 补充信息：<用户回答/会议纪要>

## 用户角色
- <角色>：<职责或场景>

## 用户故事
- 作为<角色>，我需要<动作/能力>，以便<业务价值>

## 功能列表
- REQ-001 <功能名称>：<功能行为>；验收条件：<可观察、可断言、可量化的完成标准>
  - 来源：<原 PRD 章节/第 N 条/链接锚点/用户回答>

## 边界声明
- 本期不支持：<明确不做的范围>
- 输入边界：<格式/容量/状态限制>
- 权限/数据边界：<角色可见范围/数据隔离/审计合规>

## 风险点
- RISK-001 <风险>：<影响>；决策条件：<何时/由谁/以什么标准确认>；备选处理：<未确认时如何降级或阻断>

## 阻塞澄清项
- [ ] <问题>（影响：<不澄清会阻塞什么分析/验收判断>）

## 执行期动态跟进
- [ ] <问题>（处理：<测试执行中发现后再补充，不阻塞当前分析>）

## UI 补充记录
- 页面、状态、入口、筛选/弹层、Tooltip、跳转、权限/空态、数据字段、来源

## PRD Intake 审查记录
- 模糊表述、隐含依赖、缺失验收条件

## 需求质量复核
- 六维评分：完整性、清晰性、一致性、可测试性、可追溯性、可行性（0-100）
- 总分：<六维平均分>
- 结论：<ready_for_analysis / needs_clarification / needs_revision / blocked>
- 技术词混入检查
- 陌生人测试
```

说明：

- 「功能列表」中的每条功能必须带验收条件；缺少验收条件的条目只能进入「阻塞澄清项」「执行期动态跟进」或「风险点」。
- 「功能列表」中的每条功能必须使用 `REQ-001` 形式编号，并保留来源。
- 只描述"做什么"，不描述"怎么做"；实现方案、接口拆分、存储设计等不进入 requirements.md。
- 涉及 AI/搜索/推荐/识别/生成类效果需求时，验收条件应包含评估样本、阈值或人工复核标准；缺失则标风险。
- 总分低于 90 或存在阻塞澄清项时，结论不得为 `ready_for_analysis`；执行期动态跟进不阻塞 `ready_for_analysis`。
- 每个扣分原因必须指向具体 REQ、RISK、章节或原 PRD 位置；风险点缺少决策条件或备选处理时必须扣分。
- `requirements_intake.open_question_count` 只统计阻塞澄清项。
- 已有下游产物若基于旧口径生成，必须标记 stale 并指出应重跑的下游 skill。
- stale 标记必须保持文件格式有效：Markdown 可写顶部 notice；JSON 只能更新 `_context` 字段；Excel/XMind 等二进制导出只能通过 `artifacts/update-log.md`、sidecar metadata 或最终回复标记。
- 最新接口文档推翻旧接口口径时，`artifacts/api-doc.md` 是当前变更的接口真相源；requirements.md 中依赖旧接口形状的验收条件必须同步改写。
- UI 图或原型补充应先沉淀到 `artifacts/source-prd.md`，再把影响验收的行为同步为 REQ 或边界。
- readiness 不是 `ready_for_analysis` 时，应输出可直接复制给产品/开发的问题清单，按阻塞优先级排序。

## requirements-analysis.md

分析阶段最终写入 Markdown，而不是 JSON。若中间推理采用结构化输出，落盘时必须映射到以下兼容结构：

```markdown
# 需求分析：<被测对象>

## 需求来源
- PRD：<文档名或链接>
- 设计稿：<链接>

## 分析摘要
- 分析模式：<本次执行的模式列表>
- 总结：<一句话总结>

## 主要问题

### 高优先级问题
- [类别] <描述>
  - 位置：<location>
  - 建议：<suggestion>

### 中低优先级问题
- ...

## 已明确内容
- <strengths>

## 建议补充
- <recommendations>

## 功能模块拆解
- 保持与既有模板兼容；必要时补充输入/输出、边界、状态迁移、业务规则

## 非功能性关注点
- 性能：...
- 兼容性：...
- 安全：...

## 阻塞澄清项
- [ ] <问题>

## 执行期动态跟进
- [ ] <测试执行中持续补充、不阻塞当前分析的问题>
```

说明：

- 可以在内部按 `analysis_type / issues / strengths / recommendations` 思考。
- 对外落盘时必须保持现有 `requirements-analysis.md` 可读的 Markdown 产物，不要求输出 JSON 文件。

## specs/testpoints.md

- 顶部必须保留 `# 测试点：<被测对象>`
- 顶部必须包含「命名字典」
- 模块、功能点、五类验证点分组结构保持兼容
- 每条测试点必须包含：
  - `TP_ID`
  - 测试点名称
  - 验证要点
  - 优先级
  - 关联需求

## testcases.json

由 `testspec-generate` 生成，格式为对象包装：

- `schema_version: 2`
- `testcases: []`

单个用例建议至少包含：

- `id`（源用例编号：通常为 `{需求名称}_YYYYMMDD{SEQ}`，用于当前变更追溯；publish 会结合 testlib 现状做增量管理）
- `title`
- `feature`
- `type`
- `preconditions`
- `steps`
- `expected_result`
- `priority`
- `tp_refs`（当前变更内的 TP 追溯）

## Excel 输出契约

Excel 结构不得变更，固定为：

1. 编号
2. 用例标题
3. 级别
4. 预置条件
5. 操作步骤
6. 测试预期内容
7. 执行结果
8. 执行人
9. 执行日期
10. 备注

- 工作表名称固定：`测试用例`
- 7~10 列保留人工填写

## XMind 输出契约

XMind 结构不得变更，固定分组为：

- `feature -> type -> case`

其中：

- 功能模块节点：`{feature} - 测试用例`
- 类型节点：`{type}用例`
- 用例详情子节点链：`预置条件 -> {priority}操作步骤 -> 期望结果`

## 变更控制

- 任何涉及 Excel 列头、XMind 层级、Markdown 主结构的修改，都属于高风险行为变更。
- 只有在同步修改脚本、单测、历史使用方后，才允许调整。
