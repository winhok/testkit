# TestSpec 输出契约

> 目标：集中维护 `testspec-*` skills 的产物结构约束。此文件是共享契约，不改变既有导出脚本或历史产物格式。

## 目录

- 兼容性原则
- requirements-analysis.md
- specs/testpoints.md
- testcases.json
- Excel 输出契约
- XMind 输出契约
- 变更控制

## 兼容性原则

- `proposal.md`、`requirements-analysis.md`、`specs/testpoints.md` 的 Markdown 结构保持兼容现有模板。
- `testcases.json`、Excel、XMind 的字段与层级以生成脚本及单测为准。
- 如文档说明与脚本行为冲突，必须以脚本和单测为准，不得擅自改动历史 schema。

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

## 待澄清项
- [ ] <问题>
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
