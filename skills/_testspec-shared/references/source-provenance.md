# TestSpec 来源、证据与信任契约

> 用于区分需求事实、可选代码证据、历史知识库和旧用例导入。默认流程必须在没有代码访问权限时完整可用。

## 目录

- 默认权威顺序
- 可选代码证据
- 独立校准边界
- 稳定问题登记
- 用例来源与信任
- TestLib 复用规则

## 默认权威顺序

TestSpec 默认采用 `prd-first`：

1. 当前 `requirements.md` 中已收敛的 PRD、产品回答和验收规则
2. 当前变更的接口文档与 UI/原型中可观察的契约
3. 用户明确授权使用的其他证据
4. TestLib 历史用例，仅用于回归提示、命名和表达风格

不得要求用户提供代码，也不得因为代码不可访问而降低正常 PRD 流程的可用性。

最新材料只在其负责的范围内覆盖旧材料。产品回答可以修正 PRD；接口文档可以修正接口契约，但不能单独发明产品规则；UI 图只能证明可观察交互。

## 可选代码证据

只有以下任一条件成立时才读取代码：

- 用户主动提供代码路径
- 用户明确要求检查代码
- 用户明确声明某个已上线实现可作为当前行为基线

`code_evidence.role`：

- `none`：默认；不读取代码
- `reference`：用于解释实现现状，不覆盖 PRD
- `verification-baseline`：用户明确要求按已上线实现校准当前行为
- `change-evidence`：仅参考指定开发分支或 diff 中的本次改动

即使使用代码，也必须分别记录：

- `intended`：PRD/产品要求的行为
- `observed`：代码直接表现的当前行为
- `inferred`：从代码或 diff 推断、但缺少明确契约的结论
- `unverified`：仍无证据

分支和仓库只对声明的 `scope` 有效。开发分支默认只能作为 `reference` 或 `change-evidence`，不得自动升级为产品验收口径。

### 独立校准边界

实际代码扫描统一由显式调用的 `testspec-code-calibrate` 执行。`testspec-new`、`testspec-update`、`testspec-analysis` 和 `testspec-import` 只负责路由或消费已验证的 `artifacts/code-calibration.json`，不得各自实现平行扫描逻辑。

- comparison：对比 versioned canonical source，不能修改它
- recovery：生成校准 JSON 和 `recovered-prd-draft.md`，草稿显著标记为非 canonical
- change-diff：对生产/测试/需求等显式 refs 做静态变更追踪；只保存 safe role labels、commit、merge-base 和相对定位，不保存实际私有 ref 或 raw Diff
- `conflict/code-only/unknown`：必须经产品确认；改变产品意图时由 `testspec-update` 收敛
- `prd-only`：仅允许 comparison 的授权 scope 搜索；change-diff 中未出现只能是 `not-observed/unknown`

校准 artifact 只保存非敏感 repository label、safe ref label/commit 和仓库相对路径。不得保存本机绝对路径、remote URL、实际私有分支名、raw Diff、snippet 或私有工作区标识。

## 上下文字段

```json
{
  "canonical_source_policy": "prd-first",
  "evidence_sources": [
    {
      "type": "prd",
      "source_ref": "requirements.md#REQ-001",
      "authority": "canonical",
      "scope": ["product-behavior"]
    },
    {
      "type": "code",
      "source_ref": "<用户授权的仓库别名>",
      "ref": "<branch/tag/commit>",
      "commit": "<可获取时记录>",
      "authority": "reference",
      "code_role": "reference",
      "scope": ["<组件范围>"]
    }
  ]
}
```

公开 skill、eval 和示例只使用占位符或合成名称。不得复制真实仓库路径、公司域名、工单号、接口、人员、截图内容或业务数值。

## 稳定问题登记

`blocking_open_questions` 和 `dynamic_followups` 继续作为兼容字段。新产物同时维护 `questions`：

```json
{
  "questions": [
    {
      "id": "Q-001",
      "status": "open",
      "blocking": true,
      "question": "<问题>",
      "affects": ["REQ-001"],
      "source": "<PRD/产品回答/接口文档>",
      "resolution": ""
    }
  ]
}
```

状态只能是 `open`、`resolved`、`invalidated`、`deferred`。产品回答必须更新原问题状态，不得复制出一个语义相同的新问题。兼容数组由 `questions` 派生：

- `open && blocking` → `blocking_open_questions`
- `open/deferred && !blocking` → `dynamic_followups`

## 用例来源与信任

原生生成用例：

```json
{
  "origin": {
    "kind": "testspec-native",
    "source_change": "<change-name>"
  },
  "trust": {
    "status": "provisional",
    "basis": "prd-first"
  }
}
```

旧数据导入：

```json
{
  "origin": {
    "kind": "legacy-import",
    "source_label": "<非敏感标签>",
    "source_row": 2
  },
  "trust": {
    "status": "unverified",
    "basis": "legacy-import"
  }
}
```

`trust.status`：

- `verified`：已关联当前 PRD/TP，并通过当前 revision 的 review
- `provisional`：正常 TestSpec 流程中尚未 review，或历史数据缺少新版 provenance
- `unverified`：旧数据导入且尚未重建追溯

合法组合只有：

- `testspec-native + provisional`
- `testspec-native + verified`
- `legacy-import + unverified`

空对象、未知枚举、其他组合，以及 artifact `_context` 与 case provenance 不一致，都视为 `provenance-unknown` 并阻断 review/publish。

信任状态链固定为：

```text
legacy-import/unverified
→ 按当前 PRD 完成 reconciliation
→ testspec-generate 生成新的 testspec-native/provisional 用例
→ testspec-review 通过
→ testspec-publish 写入 testspec-native/verified
```

原始 Legacy import 必须永久保留 `legacy-import/unverified` 并停留在变更工作区，不能原地升级。只有新生成的原生候选建立 TP 追溯并通过 review 后，才可由 publish 写入 TestLib。

Incoming artifact 缺少 `origin` 或 `trust` 时统一视为 `provenance-unknown`，不得按普通 Legacy workflow 发布。必须先经 `testspec-import` 隔离，或从当前 PRD/TP 重新生成原生候选。TestLib 中既有、缺少新版 provenance 的历史用例仍按兼容规则只用于命名和回归提示。

## TestLib 复用规则

- TestLib 永远不是 PRD 的替代品，不得覆盖当前需求事实。
- `testspec-native + verified`：可用于回归范围、命名和用例风格复用。
- 缺少新版 provenance 的历史用例：可用于命名和回归提示；不得单独成为新 oracle。
- `legacy-import + unverified`：不得作为需求事实、风险证据或用例 oracle。
- 发现单条或单批用例有问题时，仅审计该范围，不得默认把整个 TestLib 判为不可信。
- 需要批量清理、废弃或归档时使用 `testspec-audit`；publish 不承担隐式删除职责。
