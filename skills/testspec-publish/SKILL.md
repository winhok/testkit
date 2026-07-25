---
name: testspec-publish
license: MIT
description: TestSpec 用例入库（流程第 6 步）- 将评审通过的测试用例从变更工作区发布到 testlib 知识库，按模块/功能自动分类、增量合并、生成变更日志。当用户要「发布用例」「入库」「合并到知识库」「沉淀用例」「publish」「用例入主干」「存到知识库」或执行 testspec-publish 时使用。也适用于用户说「这些用例保存下来」「把用例归档到库里」「测完了，入库吧」的场景。产出 testspec/testlib/ 知识库更新及 changelog 条目。
---

# testspec-publish：用例入库（知识库管理）

铁律：绝不能删除 TestLib 用例，也不能隐式覆盖不同 ID 的语义匹配项。同 ID 可更新；所有歧义匹配都必须由用户明确裁决。

```text
TestSpec 发布进度：

- [ ] 步骤 1：定位当前 change 目录 ⚠️ 必需
- [ ] 步骤 2：加载 testcases 和可选 review/testpoints/proposal
- [ ] 步骤 3：评估路由与合并影响 ⚠️ 必需
- [ ] 步骤 4：写入 TestLib 前请求确认 ⛔ 阻塞
- [ ] 步骤 5：合并并重建 index、changelog、log 和统计信息
- [ ] 步骤 6：校验 TestLib 并报告变更文件
```

## 职责

将 testspec-review 评审通过的测试用例，从变更工作区（`testspec/changes/<name>/`）发布到持久化知识库（`testspec/testlib/`）。

核心能力：

1. **自动分类**：根据命名字典将用例路由到正确的 `modules/<module>/<feature>.json`
2. **增量合并**：同 ID 受控更新、新 ID 新增、不主动删除已有用例
3. **去重检测**：入库前基于 Case ID 和用例标题识别疑似重复用例
4. **交叉引用**：自动推断功能间关系，更新受影响文件的 `related_features`
5. **全局索引**：维护 `index.json`，为上游 skill 提供快速检索入口
6. **操作日志**：在 `log.md` 顶部插入人可读记录（最新在前），维护 `changelog/` 结构化 JSON
7. **统计维护**：更新 `.testlib.json` 全局统计信息

## 当前变更目录

参见 `../_testspec-shared/references/common.md` 的「当前变更目录定位规则」。

## 入库前评估

按 `../_testspec-shared/references/thinking-protocol.md` 进行推理。以下是 publish 场景的核心评估问题：

### Phase 1：材料评估

1. canonical `artifacts/testcases.json` 是否存在且非空？根目录 `testcases.json` 仅作为 Legacy fallback
2. `review-report.md` 是否存在？有无 S1 级阻塞问题？
3. `specs/testpoints.md` 中是否包含命名字典？
4. `testspec/testlib/` 中是否已有该模块/功能的用例？
5. 这次变更的用例是否适合长期沉淀？
6. canonical source、testcases 和 review-report 的 `source_revision` 是否一致？
7. `_context.origin` / `_context.trust` 是否表明这是未验证 Legacy Import？

### Phase 2：策略推理

根据材料评估结果确定策略：

- **有命名字典** → 精确路由模式：MODULE/FEATURE 缩写决定目录和文件名
- **无命名字典** → 降级路由模式：`feature` 字段 kebab-case 作为路径，必须告知用户
- **review-report 有 S1 问题** → 默认阻断；只有用户看到具体 S1 后明确要求 override 才能继续，并写入 changelog
- **versioned workflow 版本不一致** → 无条件阻断；版本不一致不能通过 override 绕过
- **Legacy workflow 无 source_revision** → 允许发布，但在写入确认中明确提示追溯置信度较低
- **incoming provenance 缺失或无效** → `origin` / `trust` 非对象、关键枚举为空/未知、组合非法或 artifact/case 不一致时，归类为 `provenance-unknown` 并无条件阻断；不能使用 Legacy 确认绕过
- **legacy-import + unverified** → 无条件阻断；必须先关联当前 PRD/TP、重新生成并通过 review，不能用 override 绕过
- **testlib 中已有同模块用例** → 进入 diff 合并，按 ID 匹配更新

### Phase 3：执行决策

向用户简报（1-2 句话）：

- 本次将发布 N 条用例到 M 个模块
- 其中预计新增 X 条，更新 Y 条
- 是否确认执行？（用户可中止）

## 输入策略

### 必需

| 文件 | 用途 |
|------|------|
| `artifacts/testcases.json` | canonical 用例数据源（对象格式，含 `schema_version` 和 `testcases` 数组） |
| `review-report.md` | versioned workflow 必需；证明当前 revision 已完成评审且无 unresolved S1 |

### Legacy 建议

| 文件 | 用途 |
|------|------|
| `review-report.md` | canonical source 无 revision 时仍建议提供；缺失只在 Legacy 模式告警 |
| `specs/testpoints.md` | 提供命名字典用于精确路由 |

### 可选

| 文件 | 用途 |
|------|------|
| `proposal.md` | 提取需求链接写入 changelog summary |

## 分类与路由规则

### 精确路由（有命名字典）

从 `specs/testpoints.md` 顶部的命名字典表格提取映射关系：

1. 解析模块字典：`模块名称 → MODULE 缩写`
2. 解析功能点字典：`模块名称 + 功能点名称 → FEATURE 缩写`
3. 用例的 `feature` 字段匹配模块名称 → 得到 MODULE
4. 用例标题的第二段匹配功能点名称 → 得到 FEATURE
5. 目录转换：MODULE/FEATURE 大写转小写，`_` 转 `-`

```
用例 feature="登录", 标题="登录_凭据验证_xxx"
  → MODULE=LOGIN → 目录 testlib/modules/login/
  → FEATURE=CRED → 文件 testlib/modules/login/cred.json
```

### 降级路由（无命名字典）

当 testpoints.md 不存在或缺少命名字典时：

1. 用例的 `feature` 字段作为模块名
2. 用例标题的第二段（`_` 分割）作为功能名
3. 中文转拼音或英文 kebab-case 作为目录/文件名
4. `module_key` 和 `feature_key` 设为大写版本

**必须告知用户正在使用降级路由**，建议后续补充命名字典以确保一致性。

## 合并策略

写入前必须运行当前 skill 目录的确定性冲突检测器：

```bash
python "<testspec-publish-skill-dir>/scripts/detect_conflicts.py" \
  --incoming <变更目录>/artifacts/testcases.json \
  --testlib testspec/testlib \
  --fail-on-conflict
```

`<testspec-publish-skill-dir>` 从当前已加载 SKILL.md 所在目录解析。退出码 2 表示存在 hard conflict，必须停止写入。

对每个目标 `<feature>.json` 文件执行增量合并：

| 情况 | 处理 |
|------|------|
| 目标文件不存在 | 创建新文件，所有用例 `status = "active"` |
| 文件存在，incoming 用例 ID 与库中匹配 | **受控更新**：更新可变内容，保留 `created_at`、`status`，刷新 `updated_at` |
| 文件存在，ID 不匹配但 normalized title 相同或非空 `scenario_key` 相同 | **hard conflict，停止写入该条**：使用检测器输出 existing/incoming ID、命中键和文件，请用户选择“新增独立用例”或“按已有 ID 更新” |
| 文件存在，ID 与语义均不匹配 | **新增**：追加用例，`created_at` 和 `updated_at` 均为今天 |
| 库中有但本次 incoming 中未出现的 ID | **不动**：不主动删除或变更状态 |

### 生命周期字段填充

| 字段 | 新入库 | 更新已有 |
|------|--------|----------|
| status | `"active"` | 保留原值（不自动变更） |
| source_change | 变更目录名 | 更新为当前变更目录名 |
| created_at | 今天 YYYY-MM-DD | 保留原值 |
| updated_at | 今天 YYYY-MM-DD | 今天 YYYY-MM-DD |
| tags | 空数组（或用户指定） | 合并原有 + 新增 |

## 执行步骤

### 1. 确定变更目录

按 `../_testspec-shared/references/common.md` 定位规则确定 `testspec/changes/<name>/`。

### 2. 读取输入文件

- 读取 `artifacts/testcases.json`；只有该文件不存在时才读取根目录 `testcases.json` 作为 Legacy fallback 并告警。两者同时存在时忽略根目录副本
- 读取 `review-report.md`（如存在，检查 S1 问题数量）
- 读取 `specs/testpoints.md`（如存在，提取命名字典）
- 读取 `proposal.md`（如存在，提取需求链接）
- 读取 canonical source（优先 `requirements.md`，否则 `proposal.md`）及三者 context

### 3. 入库前检查

- 用例源文件非空（`testcases` 数组长度 > 0）
- canonical 有 `source_revision` 且无 review-report.md → 终止并提示先执行 testspec-review
- canonical 无版本且无 review-report.md → Legacy 告警「用例未经评审，建议先执行 testspec-review」，经最终写入确认后仍可继续
- versioned workflow 必须解析 review-report 末尾 context 的 `review_gate`：
  - `status = pass` 且 `s1_unresolved_count = 0` → 通过
  - `status = blocked`、count > 0、`s1_issue_ids` 非空或字段缺失 → 列出 issue IDs 并终止
  - 报告中保留的 `resolved/accepted` 历史 S1 不计入 unresolved count
  - 用户在看到具体问题后明确要求 override 才可继续，并把 issue IDs、原因写入 changelog `_context.review_override`
- Legacy workflow 没有 `review_gate` 时，可降级解析 Markdown 并告警；`S1: 0` 不视为存在 S1
- canonical 有 `source_revision` 时，testcases 与 review-report 必须包含完全相同的 revision；任一缺失、较低或较高都终止，并分别提示先运行 `testspec-generate` / `testspec-review`
- canonical 无版本时按 Legacy 模式继续，但必须在最终写入确认中告知追溯置信度较低
- incoming `_context` 或任一 case 的 `origin` / `trust` 缺失、非对象、关键枚举为空/未知、组合非法或上下不一致时，标记为 `provenance-unknown` 并无条件阻断。空对象不算有效 provenance。必须先运行 `testspec-import`，或从当前 PRD/TP 重新生成 `testspec-native + provisional` 用例；Legacy 告警确认和 review override 均不能绕过
- `_context.origin.kind = legacy-import` 且 `trust.status = unverified` 时，无论是否存在旧版 Markdown “通过”字样或用户要求 review override 都无条件阻断。必须先完成当前 PRD 对齐，重新经过 points/generate/review；publish 不能自动升级信任状态
- 原生 versioned workflow 通过当前 revision review 后，publish 写入 `origin.kind = testspec-native`、`trust.status = verified` 和 `trust.reviewed_revision`

### 4–14. 按 TestLib 契约执行

写入前读取 `references/testlib-contracts.md`，严格执行其中的目录初始化、Schema、生命周期、交叉引用、索引、日志、统计和验证规则。主流程保持为：

1. 读取现有 testlib，构建精确或降级路由；无法归类的用例进入 `uncategorized/misc.json` 并告警。
2. 运行 `scripts/detect_conflicts.py`，预检全库 ID、normalized title 和可选 `scenario_key`：
   - 同 ID → 受控更新，保留 `created_at` 与 `status`。
   - 不同 ID 且 normalized title 或非空 `scenario_key` 相同 → hard conflict，等待用户选择新增或按已有 ID 更新。
   - 无冲突的新 ID → 追加并填充生命周期字段。
   - 仅靠模糊语义感觉相近、但未命中确定性键 → 可报告 `possible_duplicate`，绝不自动更新；不得把它伪装成 hard conflict。
3. 仅在冲突全部解决且用户确认后写入 feature 文件。
4. 累积更新双向 `related_features`，不自动删除历史引用。
5. 重建 `index.json`，生成幂等 changelog，在 `log.md` 顶部插入记录并重算 `.testlib.json`。
6. 运行 `validate_testlib.py`；JSON、跨文件 ID、case_count、索引、引用、changelog 或 stats 不一致时最多自动修复 1 轮，仍失败则报告并停止。

### 15. 告知用户

输出发布摘要：

```
✅ 用例入库完成

变更：<change-name>
新增：X 条用例
更新：Y 条用例
涉及模块：<module-1>, <module-2>
新增交叉引用：N 条

文件变更：
  - testspec/testlib/modules/<module>/<feature>.json（新增/更新）
  - testspec/testlib/index.json（重建）
  - testspec/testlib/log.md（顶部插入）
  - testspec/testlib/changelog/<date>_<name>.json（新增）

建议提交：
  git add testspec/testlib/
  git commit -m "testlib: publish <change-name> 用例入库"
```

## 反模式识别

| 反模式 | 修正 |
|--------|------|
| versioned 用例未经评审直接入库 | 缺 review-report.md 时阻断；只有 Legacy workflow 可告警后确认继续 |
| 所有增量用例都入库 | 提醒用户区分「资产型用例」和「任务型用例」，非所有变更都需要入库 |
| 入库后不提交 Git | 在摘要中明确提示 git commit 命令 |
| 同一 change 重复 publish 产生重复 | 幂等设计：同 ID 覆盖更新，changelog 同名覆盖 |
| 降级路由时不告知用户 | 必须明确提示正在使用降级路由及其影响 |
| 只入库不回顾 | 建议定期执行 testlib 健康检查（标记 stale 用例） |
| 旧 Excel/JSON 转换后直接入库 | 先运行 testspec-import；未验证导入默认阻断 |
| 无 provenance 的旧 JSON 作为 Legacy 直接入库 | 标记 `provenance-unknown` 并硬阻断；先隔离导入或从当前 PRD 重新生成 |
| 把 TestLib 当需求事实 | PRD-first；TestLib 仅用于回归、命名和风格 |

## 上下文传播

按 `../_testspec-shared/references/context-protocol.md`，在 changelog 条目的 `_context` 中播种：

```json
{
  "_context": {
    "source_skill": "testspec-publish",
    "source_change": "<change-name>",
    "publish_summary": {
      "added": 5,
      "updated": 2,
      "deprecated": 0
    },
    "affected_modules": ["login", "order"],
    "new_cross_refs": [
      { "from": "login/cred", "to": "register/basic", "relation": "前置依赖" }
    ]
  }
}
```

下游 skill（如 testspec-analysis 检索已有用例时）可消费此元数据。

## 产物

| 产物 | 路径 | 说明 |
|------|------|------|
| 功能用例文件 | `testspec/testlib/modules/<module>/<feature>.json` | 新增或更新，含交叉引用 |
| 全局索引 | `testspec/testlib/index.json` | 每次 publish 后重建 |
| 操作日志 | `testspec/testlib/log.md` | 顶部插入新条目 |
| 变更日志 | `testspec/testlib/changelog/<YYYY-MM-DD>_<change-name>.json` | 结构化 JSON |
| 库统计 | `testspec/testlib/.testlib.json` | 更新 |

## 格式契约

testlib 知识库的详细 JSON Schema、字段说明和生命周期规则见 `references/testlib-contracts.md`。
