---
name: testspec-publish
description: TestSpec 用例入库（流程第 6 步）- 将评审通过的测试用例从变更工作区发布到 testlib 知识库，按模块/功能自动分类、增量合并、生成变更日志。当用户要「发布用例」「入库」「合并到知识库」「沉淀用例」「publish」「用例入主干」「存到知识库」或执行 testspec-publish 时使用。也适用于用户说「这些用例保存下来」「把用例归档到库里」「测完了，入库吧」的场景。产出 testspec/testlib/ 知识库更新及 changelog 条目。
---

# testspec-publish：用例入库（知识库管理）

## 职责

将 testspec-review 评审通过的测试用例，从变更工作区（`testspec/changes/<name>/`）发布到持久化知识库（`testspec/testlib/`）。

核心能力：

1. **自动分类**：根据命名字典将用例路由到正确的 `modules/<module>/<feature>.json`
2. **增量合并**：同 ID 更新、新 ID 新增、不主动删除已有用例
3. **去重检测**：入库前基于 Case ID 和用例标题识别疑似重复用例
4. **交叉引用**：自动推断功能间关系，更新受影响文件的 `related_features`
5. **全局索引**：维护 `index.json`，为上游 skill 提供快速检索入口
6. **操作日志**：在 `log.md` 顶部插入人可读记录（最新在前），维护 `changelog/` 结构化 JSON
7. **统计维护**：更新 `.testlib.json` 全局统计信息

## 当前变更目录

参见 `../testspec-shared/common.md` 的「当前变更目录定位规则」。

## 入库前评估

按 `../testspec-shared/thinking-protocol.md` 进行推理。以下是 publish 场景的核心评估问题：

### Phase 1：材料评估

1. `testcases.json` 或 `artifacts/testcases.json` 是否存在且非空？（必须，缺失则终止）
2. `review-report.md` 是否存在？有无 S1 级阻塞问题？
3. `specs/testpoints.md` 中是否包含命名字典？
4. `testspec/testlib/` 中是否已有该模块/功能的用例？
5. 这次变更的用例是否适合长期沉淀？

### Phase 2：策略推理

根据材料评估结果确定策略：

- **有命名字典** → 精确路由模式：MODULE/FEATURE 缩写决定目录和文件名
- **无命名字典** → 降级路由模式：`feature` 字段 kebab-case 作为路径，必须告知用户
- **review-report 有 S1 问题** → 警告用户建议先修复，但不阻断（用户可能已在 JSON 中修复）
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
| `testcases.json` 或 `artifacts/testcases.json` | 用例数据源（对象格式，含 `schema_version` 和 `testcases` 数组） |

### 建议

| 文件 | 用途 |
|------|------|
| `review-report.md` | 确认用例已通过评审，缺失时发出警告 |
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

对每个目标 `<feature>.json` 文件执行增量合并：

| 情况 | 处理 |
|------|------|
| 目标文件不存在 | 创建新文件，所有用例 `status = "active"` |
| 文件存在，incoming 用例 ID 与库中匹配 | **更新**：覆盖用例内容，保留 `created_at`，刷新 `updated_at` |
| 文件存在，ID 不匹配但语义上是同一条用例 | **更新**：视为同一用例的新版本，按增量更新处理（判断依据：同模块 + 同功能 + 标题描述的测试场景相同，允许措辞差异） |
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

按 `../testspec-shared/common.md` 定位规则确定 `testspec/changes/<name>/`。

### 2. 读取输入文件

- 读取用例源文件（优先 `testcases.json`，否则 `artifacts/testcases.json`；二者都不存在则终止并提示用户先执行 testspec-generate）
- 读取 `review-report.md`（如存在，检查 S1 问题数量）
- 读取 `specs/testpoints.md`（如存在，提取命名字典）
- 读取 `proposal.md`（如存在，提取需求链接）

### 3. 入库前检查

- 用例源文件非空（`testcases` 数组长度 > 0）
- 如无 review-report.md → 警告「用例未经评审，建议先执行 testspec-review」
- 如 review-report 中存在 S1 问题 → 警告并列出问题，询问是否继续

### 4. 确保 testlib 目录结构

每次 publish 必须先读取仓库当前 `testspec/testlib/` 状态；若不存在则按以下结构初始化（兜底，不阻断发布）：

```bash
mkdir -p testspec/testlib/modules testspec/testlib/changelog
```

若 `testspec/testlib/.testlib.json` 不存在，创建初始配置：

```json
{
  "schema_version": 1,
  "created_at": "<今天>",
  "last_updated": "<今天>",
  "stats": {
    "total_modules": 0,
    "total_features": 0,
    "total_cases": 0,
    "by_status": { "active": 0, "deprecated": 0, "archived": 0 },
    "by_priority": { "P1": 0, "P2": 0, "P3": 0 }
  }
}
```

若 `testspec/testlib/index.json` 不存在，创建初始索引：

```json
{
  "schema_version": 1,
  "last_updated": "<今天>",
  "modules": []
}
```

若 `testspec/testlib/log.md` 不存在，创建初始日志：

```markdown
# TestLib 操作日志

> 每次 testspec-publish 入库后自动追加记录。最新条目在前。

```

### 5. 去重检测

在执行合并之前，做去重预检：

1. 扫描目标 `feature.json` 及必要的相关 feature 文件，读取已有 Case ID
2. 对比本次 incoming 用例的 `id`：
   - Case ID 已存在于同一 feature 文件中 → 视为正常更新
   - Case ID 已存在于其他 feature 文件中 → 视为异常冲突，列出告警
3. 对比本次 incoming 用例的标题与目标 feature 中已有用例标题：
   - 标题完全一致但 Case ID 不同 → 疑似重复，告警
4. 对比本次 incoming 用例的 `tp_refs` 与历史 `tp_ids`：
   - 仅作为覆盖参考，帮助识别“历史是否测过类似测试点”
   - 不作为重复判断条件，不参与 TP_ID 编号分配
5. 汇总告警信息，向用户报告后继续（不阻断，用户决定是否处理）

### 6. 构建路由映射

- 有命名字典 → 解析模块字典和功能点字典，构建 `{中文模块 → module_dir}` 和 `{中文功能 → feature_file}` 映射
- 无命名字典 → 使用降级路由规则

### 7. 分组用例

遍历 testcases.json 中每条用例：

1. 从 `feature` 字段确定模块
2. 从 `title` 第二段（`_` 分割）确定功能点
3. 通过路由映射得到目标路径 `testspec/testlib/modules/<module>/<feature>.json`
4. 将用例归入对应分组

无法归类的用例（feature 为空或匹配失败）归入 `uncategorized/misc.json`，并警告用户。

### 8. 执行合并

对每个分组（= 一个目标文件）：

1. 检查目标模块目录是否存在，不存在则 `mkdir -p`
2. 读取已有文件内容（如文件存在）
3. **文件级元数据稳定性**：若目标文件已存在，`module`/`module_key`/`feature`/`feature_key` 以库中现有值为准，不用 incoming 数据覆盖。若 incoming 与库中不一致，发出告警（命名字典可能已变更），由用户决定是否更新
4. 按用例 ID 进行 diff：
   - 匹配 → 更新内容，保留 `created_at`，刷新 `updated_at`
   - 不匹配 → 追加，填充所有生命周期字段
5. 更新文件级元信息：`last_updated`、`case_count`
6. 写入文件（JSON pretty-print，2 空格缩进）

记录操作统计：added_ids、updated_ids、affected_modules。

### 9. 更新交叉引用

#### 确定扫描范围

通过三层发现确定需要更新交叉引用的 feature 文件集合：

1. **直接涉及**：本次 publish 写入的 feature 文件
2. **引用发现**：扫描 incoming 用例的 `preconditions` 和 `tp_refs`，通过 `index.json` 匹配到被引用的其他 feature 文件（如 preconditions 提到"用户已注册" → 通过 index.json 定位 register 模块下的 feature）
3. **同模块发现**：本次写入的模块目录下已有的其他 feature 文件

三层合集即为完整的交叉引用更新范围。

#### 推断关联关系

对范围内的每个 feature.json，推断并更新 `related_features`：

1. **同模块关联**：同一 `<module>/` 目录下的 feature 文件自动互为 `同模块` 关系
2. **前置依赖推断**：incoming 用例 `preconditions` 中引用了其他模块的功能 → `前置依赖`
3. **业务关联推断**：incoming 用例 `tp_refs` 中存在跨模块的 TP_ID 模式 → `业务关联`
4. **双向更新**：在 A 的 `related_features` 中添加 B 的同时，也在 B 的 `related_features` 中添加 A
5. **去重**：不重复添加已有的关联

交叉引用为累积式——只新增不自动删除。如需清理错误引用，用户手工编辑 feature.json 的 `related_features`。

### 10. 重建全局索引

扫描 `testspec/testlib/modules/` 下所有 `*.json` 文件，重建 `index.json`：

对每个 feature.json 提取：
- module/module_key/feature/feature_key 信息
- case_count、by_priority、by_status 统计
- 所有用例的 tp_refs 汇总为 `tp_ids` 列表（仅用于模块/功能维度的覆盖范围检索，不用于精确去重）
- related_features 路径列表
- last_updated

按模块分组写入 `index.json`，更新 `last_updated`。

### 11. 生成 changelog 条目

写入 `testspec/testlib/changelog/<YYYY-MM-DD>_<change-name>.json`：

- `change_name`：变更目录名
- `date`：今天
- `source_dir`：变更目录相对路径
- `summary`：从 proposal.md 标题提取，或自动生成「<change-name> 用例入库」
- `operations`：added/updated/deprecated ID 列表 + unchanged 计数
- `affected_modules`：涉及的模块目录名
- `new_cross_refs`：本次新建立的交叉引用列表
- `_context`：播种上下文元数据

同一 change 重复 publish 时，覆盖同名 changelog 文件（幂等）。

### 12. 插入操作日志

在 `testspec/testlib/log.md` 顶部插入新条目（`# TestLib 操作日志` 标题之后、已有条目之前），最新记录始终在最前面：

```markdown
## YYYY-MM-DD: <change-name> 入库

**来源**: testspec/changes/<change-name>
**操作**: 新增 X 条，更新 Y 条，废弃 Z 条
**涉及模块**: <模块中文名>（<module>/<feature>, ...）
**新增交叉引用**: <A> ↔ <B>（<关系类型>）或"无"
```

### 13. 更新全局统计

扫描 `testspec/testlib/modules/` 下所有 `*.json` 文件：

- 统计总模块数（子目录数）
- 统计总功能数（JSON 文件数）
- 统计总用例数（所有 cases 数组长度之和）
- 按 status 分组计数
- 按 priority 分组计数

写入 `testspec/testlib/.testlib.json`，更新 `last_updated`。

### 14. 自检验证

- 所有新写入的 JSON 文件可正常解析
- 跨文件无重复用例 ID（扫描所有 feature.json）
- 每个文件的 `case_count` 与 `cases` 数组长度一致
- `index.json` 中的 tp_ids 与 feature.json 中的 tp_refs 一致
- `index.json` 中的 related_features 与 feature.json 中的 related_features 一致
- changelog 条目的 `added` + `updated` 数量与实际操作一致
- `.testlib.json` 的 stats 与实际文件内容一致

发现不一致时自动修复（最多 1 轮）。

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
| 未经评审直接入库 | 检查 review-report.md，缺失时警告 |
| 所有增量用例都入库 | 提醒用户区分「资产型用例」和「任务型用例」，非所有变更都需要入库 |
| 入库后不提交 Git | 在摘要中明确提示 git commit 命令 |
| 同一 change 重复 publish 产生重复 | 幂等设计：同 ID 覆盖更新，changelog 同名覆盖 |
| 降级路由时不告知用户 | 必须明确提示正在使用降级路由及其影响 |
| 只入库不回顾 | 建议定期执行 testlib 健康检查（标记 stale 用例） |

## 上下文传播

按 `../testspec-shared/context-protocol.md`，在 changelog 条目的 `_context` 中播种：

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

## 产出

| 产物 | 路径 | 说明 |
|------|------|------|
| 功能用例文件 | `testspec/testlib/modules/<module>/<feature>.json` | 新增或更新，含交叉引用 |
| 全局索引 | `testspec/testlib/index.json` | 每次 publish 后重建 |
| 操作日志 | `testspec/testlib/log.md` | 顶部插入新条目 |
| 变更日志 | `testspec/testlib/changelog/<YYYY-MM-DD>_<change-name>.json` | 结构化 JSON |
| 库统计 | `testspec/testlib/.testlib.json` | 更新 |

## 格式契约

testlib 知识库的详细 JSON Schema、字段说明和生命周期规则见 `../testspec-shared/testlib-contracts.md`。
