# 历史用例导入契约

## 目录

- [目标](#目标)
- [输入](#输入)
- [隔离输出](#隔离输出)
- [Reconciliation 输出](#reconciliation-输出)
- [信任状态转换](#信任状态转换)
- [发布门禁](#发布门禁)

## 目标

把不可直接信任的历史用例转换成隔离、可追溯、可审计的 staging artifact。导入成功只代表格式可读，不代表业务正确，也不代表允许发布。

## 输入

- `.xlsx`：读取第一个工作表和第一行表头
- `.csv`：UTF-8 或 UTF-8 BOM
- `.json`：顶层数组，或包含 `testcases` / `cases` 数组的对象
- `.md`：优先读取带表头的 Markdown 表格；否则读取 H2-H4 用例段落及带标签字段
- `.txt`：按空行分块，读取 `标题/前置条件/步骤/预期` 等带标签字段
- `.xmind`：读取 `content.json` 或 `content.xml`；仅把至少带有标题、前置条件、步骤或
  预期之一的已识别字段子节点的主题作为结构化用例；只有模块/优先级等元数据的分组继续向下查找

支持字段：

| Canonical 字段 | 常见输入列 |
|---|---|
| id | `id`、`case_id`、`编号` |
| title | `title`、`标题`、`用例标题` |
| priority | `priority`、`优先级`、`级别` |
| preconditions | `preconditions`、`前置条件`、`预置条件` |
| steps | `steps`、`步骤`、`操作步骤` |
| expected_result | `expected_result`、`预期结果`、`测试预期内容` |
| type | `type`、`类型` |
| feature | `feature`、`功能`、`模块` |

Markdown、文本和 XMind 只做保守结构解析。无法可靠识别的字段保持为空并产生
`missing_key_fields` warning；不得从叶子标题猜测步骤、预期或业务规则。

## 隔离输出

顶层：

- `schema_version: 2`
- `_context.source_skill: testspec-import`
- `_context.canonical_source_policy: prd-first`
- `_context.publish_eligibility: blocked`
- `_context.origin.kind: legacy-import`
- `_context.trust.status: unverified`
- `import_summary`
- `warnings`
- `testcases`

每条用例：

- 保留可识别的业务字段；重复旧 ID 使用确定性的 `__DUP_N` staging 后缀
- 写入 `origin.kind=legacy-import`
- 写入通用 `origin.source_label` 和 `origin.source_row`；source label 只允许非敏感的
  字母、数字、点、下划线和连字符，不得传入路径、文件名或组织标识
- 写入非敏感的 `origin.source_format`，只记录扩展名类别，不记录输入文件名或路径
- 原始旧 ID 存在时写入 `origin.source_case_id`，不得用重复旧 ID 破坏 staging 唯一性
- 写入 `trust.status=unverified`
- `tp_refs=[]`，不得伪造测试点追溯

输出不得包含输入文件绝对路径、本机用户名、编辑器会话路径或内部 URL。

## Reconciliation 输出

固定路径为同目录的 `reconciliation.json`：

```json
{
  "schema_version": 1,
  "_context": {
    "source_skill": "testspec-import",
    "canonical_source_policy": "prd-first",
    "status": "pending"
  },
  "summary": {
    "keep": 0,
    "revise": 0,
    "merge": 0,
    "retire": 0,
    "unresolved": 1
  },
  "records": [
    {
      "legacy_case_id": "LEGACY_0001",
      "source_row": 2,
      "status": "unresolved",
      "requirement_refs": [],
      "question_refs": [],
      "replacement_candidate_id": "",
      "reason": ""
    }
  ]
}
```

约束：

- exactly one record per imported case
- status 只能是 `keep/revise/merge/retire/unresolved`
- `keep/revise` 必须有当前 `REQ-*` / `AC-*`
- `merge` 必须有 `replacement_candidate_id`
- `summary` 必须与 records 计数一致
- 进入 generate 前不得残留 `unresolved`
- 完成全部决策后必须将 `_context.status` 改为 `ready-for-generate`

只有当前 PRD/产品回答明确支持的 `keep/revise` 内容，才能作为后续原生生成输入。`merge/retire` 只保留审计记录。代码证据只在用户明确授权后用于验证或变更取证，不能成为默认权威源。

## 信任状态转换

原始导入行永远保持 `legacy-import/unverified`。reconciliation 不直接改变用例信任状态；`testspec-generate` 根据已对齐意图创建新的 `testspec-native/provisional` 用例，review 通过后 publish 才把新的原生用例写为 `verified`。

## 发布门禁

以下任一情况阻断发布：

- `origin.kind=legacy-import` 且 `trust.status=unverified`
- incoming 缺少 provenance，属于 `provenance-unknown`
- 没有当前 `REQ-*` / `AC-*` / `TP_*` 追溯
- reconciliation 仍为 `unresolved`
- review 出现 `GLOBAL:legacy-traceability` S1
