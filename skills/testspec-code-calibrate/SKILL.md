---
name: testspec-code-calibrate
license: MIT
description: 对明确授权的代码范围做 PRD-first TestSpec 校准：比较实现快照与当前 PRD、从遗留代码恢复非 canonical 行为草稿，或对生产/测试/需求分支的 Git Diff 做变更追踪。用户明确执行 testspec-code-calibrate、要求「用代码校准 PRD」「对比需求和实现」「从代码恢复行为草稿」「检查生产和测试分支差异」「看需求分支改了什么」「对照 REQ/AC 与 Diff」时使用；普通 PRD 新建、更新、分析或导入请求不触发。
---

# TestSpec 代码校准

铁律：未经产品通过 `testspec-update` 明确裁决，绝不能把可观察到的代码行为转成 canonical requirement 或 test oracle，也绝不能修改 `requirements.md`。

```text
TestSpec 代码校准进度：

- [ ] 步骤 1：确认明确授权、代码角色和范围 ⛔ 阻塞
- [ ] 步骤 2：定位 TestSpec change，并选择 comparison/recovery/change-diff 模式 ⚠️ 必需
- [ ] 步骤 3：冻结 canonical revision 和代码快照
- [ ] 步骤 4：提取可观察的实现证据
- [ ] 步骤 5：对发现分类并登记稳定问题
- [ ] 步骤 6：写入并确定性校验校准 artifact ⛔ 阻塞
- [ ] 步骤 7：确认 canonical 文件未变并完成交接
```

## 边界

1. 仅在明确调用本 skill，或用户明确要求检查代码时运行。无法访问代码不影响常规 TestSpec 流程。
2. 只读授权的仓库、ref 和相对范围，不得默认扩展到整个工作区。
3. 保持 `canonical_source_policy=prd-first`；代码权威始终是 `reference`。
4. 只将可观察行为标记为 `observed`；缺少支撑的解释标记为 `inferred` 或 `unknown`。
5. 不得把实现行为直接写入 `requirements.md`、`proposal.md`、测试点、用例或 TestLib。
6. 只存储非敏感仓库标签和仓库相对路径。不得存储绝对路径、用户名、远程 URL、token 或私有工作区标识。
7. change-diff 模式只保存安全的分支角色标签和 commit hash，不保存真实私有分支名、原始 Diff、变更行或代码片段。

选择 `code_evidence.role` 或处理权威冲突前，加载 `../_testspec-shared/references/source-provenance.md`。

## 模式

### Comparison

用于当前 change 已有版本化 `requirements.md` 或 `proposal.md`：

- `<change>/artifacts/code-calibration.json`
- `<change>/artifacts/code-calibration.md`

JSON 对照 canonical intent 与可观察代码，但不修改 canonical source。

### Recovery

仅用于 TestSpec change 已存在、没有版本化 canonical source，且用户明确要求从遗留代码恢复行为：

- `<change>/artifacts/code-calibration.json`
- `<change>/artifacts/code-calibration.md`
- `<change>/artifacts/recovered-prd-draft.md`

先写 draft 再写 JSON。draft 标题和上下文必须注明“可观察实现草稿——不是 canonical 文档”，并在 JSON 中记录其 SHA-256 和对应代码快照。产品确认前，`testspec-update` 不得将这些陈述提升到 `requirements.md`。

仅在 recovery 模式加载 `references/recovered-prd-draft-template.md`。

### Change-diff

用于已有版本化 canonical source，且用户明确要求比较 production、test、requirement、release、staged 或 worktree 状态：

- `<change>/artifacts/change-snapshot.json`
- `<change>/artifacts/code-calibration.json`
- `<change>/artifacts/code-calibration.md`

加载 `references/change-diff-workflow.md`。Diff 只是变更证据，不是测试结果，也不能证明未变化的需求缺少实现。

## 工作流

### 1. 确认授权并冻结范围

记录：

- `role`：`reference`、`verification-baseline` 或 `change-evidence`
- 非敏感 `repository_label`
- branch/tag/ref 和 commit；仅在来源不是 Git checkout 时使用 `unavailable` 并提供 `snapshot_reason`
- 一个或多个仓库相对范围路径；只有用户明确授权整个仓库时，`.` 才表示仓库根目录

角色或范围缺失时，在读取代码前停止。拒绝 `..`、绝对路径、远程 URL 和未请求的范围扩张。

若已授权检查仓库但模块范围不明确，加载 `references/module-discovery.md`，只检查 discovery surface，返回候选并等待用户选择范围后再读取实现正文。

### 2. 定位 change 和 canonical source

使用 `../_testspec-shared/references/common.md` 定位 change：

- 有版本化 source + 常规实现对照 → comparison
- 有版本化 source + 明确 branch/Diff 请求 → change-diff
- 无版本化 canonical source + 明确恢复请求 → recovery
- 无 canonical source + 常规对照请求 → 停止，先运行 `testspec-new`

comparison 和 change-diff 模式必须记录精确的 canonical `source_revision`、source 名称（`requirements.md` 或 `proposal.md`），以及读取代码前计算的 `sha256:<digest>`。不得增加 revision。

### 3. 提取可观察证据

加载 `references/code-evidence-extraction.md`，只检查授权范围，提取：

- 入口与模块边界
- 角色和权限强制逻辑
- 字段、校验、枚举与可见消息
- 状态转换与动作分支
- 可观察的成功、失败和恢复行为

每项证据都使用仓库相对路径、symbol/locator、行范围和简短观察。依据该 reference 设置 finding 级 `evidence_coverage`。注释、命名、未证明调用方的导出函数、不可达代码、feature flag 路径或单一前后端层，都不能视为完整产品事实。

只有框架匹配时加载 `references/framework-locators.md`。change-diff 模式应先收集并校验安全快照；关键词命中仅用于发现候选，再读取临时 hunk 和相连运行时路径形成语义证据。

### 4. 对发现分类

写 JSON 前加载 `references/calibration-contract.md`，只使用：

- `aligned`：意图与可观察行为一致
- `conflict`：意图与可观察行为冲突
- `code-only`：代码存在行为，但 canonical requirement 未记录
- `prd-only`：授权范围内未观察到 canonical requirement
- `unknown`：证据不足或互相矛盾

规则：

- `conflict`、`code-only`、`unknown` 必须有稳定 `Q-*`、措辞可直接交给产品的顶层 open question，并设置 `recommended_handoff=product-confirmation`。
- `prd-only` 不自动代表实现缺陷；报告搜索范围并交给 `testspec-analysis`。
- `aligned` 和 `conflict` 要求 `end-to-end` 或 `enforcement-layer` 覆盖；部分路径只能归为 `unknown`。
- recovery 模式只允许 `code-only` 和 `unknown`。
- recovery 的每项 finding 都有唯一 `OBS-*` draft reference；draft 必须包含该 `OBS-*` 和所有关联 `Q-*`。
- finding 不得引用自身或历史用例作为产品权威。
- change-diff finding 还必须遵守 `references/change-diff-workflow.md` 的固定 trace-status 映射；Diff 中没有变化只能是 `unknown/not-observed`，不能是 `prd-only`。

### 5. 写入并校验

将 canonical machine output 写入 `<change>/artifacts/code-calibration.json`。除非用户明确授权替换，否则不得覆盖已有校准 artifact。

Comparison：

```bash
python "<testspec-code-calibrate-skill-dir>/scripts/validate_code_calibration.py" \
  --input "<change>/artifacts/code-calibration.json" \
  --canonical "<change>/<requirements.md-or-proposal.md>"
```

Recovery：

```bash
python "<testspec-code-calibrate-skill-dir>/scripts/validate_code_calibration.py" \
  --input "<change>/artifacts/code-calibration.json" \
  --draft "<change>/artifacts/recovered-prd-draft.md"
```

Change-diff：先按 `references/change-diff-workflow.md` 的命令和安全标签规则，用 `scripts/collect_change_snapshot.py` 收集 `change-snapshot.json`，然后执行：

```bash
python "<testspec-code-calibrate-skill-dir>/scripts/validate_change_snapshot.py" \
  --input "<change>/artifacts/change-snapshot.json"

python "<testspec-code-calibrate-skill-dir>/scripts/validate_code_calibration.py" \
  --input "<change>/artifacts/code-calibration.json" \
  --canonical "<change>/<requirements.md-or-proposal.md>" \
  --snapshot "<change>/artifacts/change-snapshot.json"
```

JSON 校验通过后，渲染不含代码片段的 Markdown 视图：

```bash
python "<testspec-code-calibrate-skill-dir>/scripts/render_code_calibration.py" \
  --input "<change>/artifacts/code-calibration.json" \
  --output "<change>/artifacts/code-calibration.md"
```

修复所有校验错误。comparison 和 change-diff 模式需在校验后重新读取 canonical 文件，并确认 digest 仍等于 `_context.canonical_source_digest`。

### 6. 交接

- 全部 finding 为 `aligned` 或 `prd-only` → `testspec-analysis`
- 存在 `conflict`、`code-only` 或 `unknown` → 产品确认
- 产品确认导致意图变化 → `testspec-update`，再执行 `testspec-analysis`
- recovery draft → 产品确认，再执行 `testspec-update`；不得直接进入 points/generate
- change-diff 的 `partial/not-observed/unknown` → 产品确认或经明确授权扩大证据范围；不得因 Diff 缺失就声称未实现
- 历史导入继续隔离；校准证据可以解释漂移，但不能证明 `keep/revise`

## 反模式

| 反模式 | 必需修正 |
|---|---|
| 因仓库可用就扫描代码 | 要求明确调用、角色和范围 |
| 直接从代码写 REQ/AC | 写 recovery draft 或 `code-only` finding |
| 把代码缺失当作 PRD 错误的证明 | 使用 `prd-only` 并记录搜索范围 |
| artifact 使用绝对路径 | 使用仓库相对路径和安全标签 |
| 把注释或死代码当作 observed behavior | 标记为 inferred/unknown 并登记 `Q-*` |
| 代码冲突未解决就继续生成用例 | 先产品确认并执行 `testspec-update` |
| 把关键词命中当作实现证据 | 只用于选择临时 hunk，再做语义检查 |
| 没有变更 hunk 就归为 `prd-only` | 使用 `unknown` + `not-observed`；完整缺失需 comparison 模式证明 |
| 保存真实私有 ref 或原始 Diff | 只存安全角色标签、commit、元数据和相对 locator |
| 自动 fetch、checkout 或切换 two-dot/three-dot 语义 | 只使用本地已有 ref 和明确选择的 Diff 模式 |

## 交付前检查

- [ ] 调用、角色、ref/commit 和范围均已明确授权。
- [ ] canonical policy 仍为 PRD-first，代码权威仍为 `reference`。
- [ ] 每项 finding 使用有效分类和仓库相对证据。
- [ ] `conflict/code-only/unknown` 有稳定 `Q-*`，且与可直接交给产品的问题对象双向关联。
- [ ] recovery 输出明确标记为 non-canonical。
- [ ] validator 已依据 canonical 文件或 recovery draft 通过。
- [ ] canonical digest 和 revision 未变化。
- [ ] change-diff snapshot 校验通过、与代码证据匹配，且不含原始 Diff、代码片段或私有 ref。
- [ ] 每项端到端变更 finding 跨越至少两个证据层。
- [ ] Markdown 报告由已校验 JSON 渲染，只含 locator，不含代码片段。
- [ ] 最终答复明确后续 skill 和未决产品决策。

公开 eval 和示例必须完全合成。绝不能复制私有源代码、仓库路径、公司名、工单、URL 或业务数值。
