---
name: testspec-import
license: MIT
description: 隔离导入和迁移历史测试用例，将旧 Excel、CSV、JSON、Markdown、文本、XMind 或旧 TestLib 数据转换为可审计的 staging artifact，并按当前 PRD 做 reconciliation。用户说「导入历史用例」「迁移旧 Excel/XMind」「整理旧测试用例」「旧 TestLib 被污染」「把老用例对齐新需求」或执行 testspec-import 时使用。导入数据不会直接写入 TestLib，代码也不是默认输入。
---

# TestSpec 历史用例导入

铁律：历史导入用例在依据当前 PRD 完成 reconciliation，并重新生成为新的 testspec-native 用例前，绝不能发布、验证、复用为需求事实。

```text
TestSpec 导入进度：

- [ ] 步骤 1：定位目标 change 和当前 PRD ⚠️ 必需
- [ ] 步骤 2：检查隔离输出路径和覆盖意图 ⛔ 阻塞
- [ ] 步骤 3：将历史数据以未验证状态导入 staging
- [ ] 步骤 4：依据当前 REQ/AC/Q 证据逐条 reconciliation ⚠️ 必需
- [ ] 步骤 5：校验生成就绪状态
- [ ] 步骤 6：报告数量、阻塞项和后续 skill
```

## 核心边界

1. 当前 PRD、产品答复和验收标准是 canonical source。
2. 代码不是默认输入；仅在用户明确授权访问或要求校准时读取。
3. 历史 TestLib、表格和 JSON 都只是候选知识，不是需求事实。
4. 只能写入 `<change>/imports/`，绝不能写入 `testspec/testlib/`。
5. 导入记录永久保持 `legacy-import + unverified`。
6. artifact 中不得记录输入文件的绝对路径、用户名、工作区路径或文件 URL。

判断权威、可选代码证据或信任转换时，加载 `../_testspec-shared/references/source-provenance.md`。

## 工作流

### 1. 建立 PRD 基线

按顺序读取：

1. `<change>/requirements.md`
2. `<change>/proposal.md`
3. 当前对话中提供的产品答复

若都不存在，可继续机械导入，但 reconciliation 保持 pending，且禁止进入 publish。

### 2. 导入隔离区

写入前检查两个输出是否已存在。除非用户明确要求，否则不得覆盖。

```bash
python "<testspec-import-skill-dir>/scripts/import_legacy_cases.py" \
  --input "<legacy.xlsx|legacy.csv|legacy.json|legacy.md|legacy.txt|legacy.xmind>" \
  --output "<change>/imports/legacy-cases.json" \
  --source-label "legacy-source"
```

脚本还会创建 `<change>/imports/reconciliation.json`，为每个导入用例生成一条 `unresolved` 记录。仅在用户明确授权覆盖后使用 `--overwrite`。运行脚本前加载 `references/import-contract.md`。

脚本只负责：

- 字段映射和最小规范化
- 保守解析 Markdown、文本和 XMind 结构
- 缺失字段与重复候选警告
- 来源行 provenance
- 隔离数据与初始 reconciliation 记录

它不会判断业务正确性、修改 TestLib 或提升可信度。

### 3. 对照当前 PRD 完成 reconciliation

更新 `imports/reconciliation.json` 中每条记录：

- `keep`：PRD 仍支持该场景
- `revise`：意图仍有效，但操作或 oracle 已变化
- `merge`：另一候选表达相同的当前意图
- `retire`：当前 PRD 明确移除该行为
- `unresolved`：产品证据不足

`keep` 和 `revise` 必须引用当前 `REQ-*` 或 `AC-*`。`merge` 必须提供 `replacement_candidate_id`。未决事项在可用时保留稳定 `Q-*`。历史用例不能自证 `keep`。全部决策完成后，将 `_context.status` 设为 `ready-for-generate`；任何记录仍为 unresolved 时不得设置。

校验 artifact：

```bash
python "<testspec-import-skill-dir>/scripts/validate_reconciliation.py" \
  --imported "<change>/imports/legacy-cases.json" \
  --reconciliation "<change>/imports/reconciliation.json"
```

交给生成流程前增加 `--ready-for-generate`。存在 unresolved，或 `keep/revise` 缺少当前需求证据时，校验必须失败。

### 4. 可选代码校准

只有明确授权后才交接给 `testspec-code-calibrate`；本 skill 从不直接扫描代码。代码只能作为：

- `verification-baseline`：验证实现是否符合 PRD 意图
- `change-evidence`：解释可观察到的漂移或历史污染

校准 artifact 必须记录代码范围和角色。若与 PRD 冲突，应请求产品裁决，并在意图变化时执行 `testspec-update`。校准证据可以解释污染，但不能单独证明 `keep`、`revise` 或信任提升。

### 5. 重新生成原生候选

转换链路为：

```text
legacy-import/unverified
→ reconciliation.json
→ testspec-analysis / testspec-points
→ testspec-generate 生成新的 testspec-native/provisional 用例
→ testspec-review
→ testspec-publish 写入 testspec-native/verified 用例
```

绝不能把导入记录直接改为 `verified`；导入证据始终留在隔离区。

## 反模式

| 反模式 | 必需修正 |
|---|---|
| 将旧 JSON 直接复制到 `artifacts/testcases.json` | 执行隔离导入和 reconciliation |
| 把旧预期结果当作当前 oracle | 要求当前 REQ/AC 证据 |
| 因代码可用就读取 | 仅在明确授权后使用代码 |
| 覆盖已有 staging 文件重新导入 | 未明确授权覆盖时停止 |
| 在公开 eval 使用真实对话或公司材料 | 使用完全合成的 fixture；私有 fixture 放入忽略路径 |
| 把无标签的 XMind 叶节点当作完整 oracle | 缺失字段带警告导入，并保持未验证 |

## 交付前检查

- [ ] 两个导入 artifact 均已存在，且不含输入路径。
- [ ] 每条导入记录仍为 `legacy-import + unverified`。
- [ ] reconciliation 与导入用例严格一一对应。
- [ ] `keep/revise` 引用当前 REQ/AC 证据。
- [ ] 未将任何 unresolved 记录声明为可生成。
- [ ] 未向 `testspec/testlib/` 写入任何内容。
- [ ] 最终报告包含导入、跳过、重复候选、各 reconciliation 状态数量和未决 `Q-*`。

公开 eval 必须完全合成且不可识别。私有源材料只能放在仓库忽略的私有 fixture 路径中。
