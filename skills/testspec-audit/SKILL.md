---
name: testspec-audit
license: MIT
description: 只读审计 TestSpec TestLib 的结构健康、重复用例、模块错放、provenance 缺失和未验证历史导入。用户说「审计 TestLib」「检查知识库质量」「清理重复用例前先盘点」「TestLib 被污染了」「历史用例是否可信」「找出该废弃或合并的用例」或执行 testspec-audit 时使用。只输出证据和 lifecycle proposal，不修改 TestLib。
---

# TestSpec TestLib 审计

铁律：审计期间绝不修改、合并、移动、废弃、归档或验证任何 TestLib 用例。

```text
TestSpec 审计进度：

- [ ] 步骤 1：定位 TestLib 和当前 PRD 证据 ⚠️ 必需
- [ ] 步骤 2：执行结构与语义联合审计
- [ ] 步骤 3：依据当前 PRD 对发现分类
- [ ] 步骤 4：为具体用例生成生命周期建议
- [ ] 步骤 5：确认审计全程只读 ⚠️ 必需
- [ ] 步骤 6：报告健康状况、阻塞项和明确交接
```

## 权威顺序与范围

按以下顺序判断：

1. 当前 `requirements.md`、PRD、产品答复和验收标准
2. 明确的 API、UI 与可观察行为证据
3. TestLib 历史记录，仅作为候选知识
4. 仅在用户明确授权代码作为验证或变更证据时使用代码

无法访问代码不影响审计。代码与 PRD 冲突时只报告冲突，不得把实现行为提升为产品意图。

本 skill 永久只读。用户确认的生命周期建议必须交接给：

- 新增或同 ID 内容更新 → `testspec-publish`
- 退役、移动或合并维护 → 单独授权且范围明确的维护任务

不得在 `testspec-audit` 内执行这些写操作。

仅在判断权威或可信度时加载 `../_testspec-shared/references/source-provenance.md`。生成生命周期建议前加载 `references/audit-contract.md`。

## 执行联合审计

```bash
python "<testspec-audit-skill-dir>/scripts/audit_testlib.py" \
  --testlib "testspec/testlib"
```

该命令同时执行：

- 结构校验：JSON、必填字段、ID、引用、索引和统计信息
- 语义审计：重复 ID/标题/正文候选、模块错放、provenance 缺口和仍为 active 的未验证导入

结果分别给出 `structural_health` 和 `semantic_health`。只有两项都通过时，整体 `health` 才能为 `clean`。

仅在用户要求时保存报告：

```bash
python "<testspec-audit-skill-dir>/scripts/audit_testlib.py" \
  --testlib "testspec/testlib" \
  --output "testspec/audits/testlib-audit.json"
```

默认不覆盖已有报告。只有得到明确授权后才能使用 `--overwrite`。

## 对生命周期候选分类

依据当前 PRD 证据使用：

- `keep`：仍满足当前验收标准
- `revise`：意图仍有效，但操作或 oracle 已过时
- `merge`：另一用例表达相同的当前意图
- `relocate`：用例位于错误的模块或功能下
- `retire`：当前 PRD 明确移除了该行为
- `reconcile`：历史导入缺少当前 PRD 可追溯性
- `unresolved`：证据不足，登记稳定的 `Q-*`

TestLib 不能自证正确。每项建议都必须记录用例 ID、当前 `REQ-*`/`AC-*`、必要时的稳定 `Q-*`、建议动作、影响和复审要求。重复检测只产生候选信号，绝不是自动合并的授权。

## 反模式

| 反模式 | 必需修正 |
|---|---|
| 只扫描模块文件就报告 `clean` | 同时要求结构和语义健康 |
| 因为用例已存在就保留 | 引用当前 PRD/AC 证据 |
| 自动合并规范化标题相同的用例 | 展示候选对并请求单独维护决策 |
| 审计期间修改用例状态 | 停止修改，只生成生命周期建议 |
| 未明确授权就使用代码 | 保持 `code_evidence.role=none` |
| 把真实 TestLib 数据复制到公开 eval | 使用完全合成的 fixture |

## 交付前检查

- [ ] 结构和语义两部分都已执行。
- [ ] `clean` 表示结构错误和语义警告均为零。
- [ ] 每项生命周期建议都注明用例 ID 和当前证据。
- [ ] 未决事项使用稳定 `Q-*`，不做猜测。
- [ ] 未修改 TestLib、索引、配置、变更日志或用例状态。
- [ ] 报告声明 `mutation_performed=false`。
- [ ] 最终答复指出后续独立动作，但没有执行它。

公开 eval 必须完全合成且不可识别。私有源材料只能放在被忽略的私有 fixture 路径中。
