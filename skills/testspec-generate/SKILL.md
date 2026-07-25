---
name: testspec-generate
description: TestSpec 生成测试用例（流程第 4 步）- 根据测试点（specs/*.md）生成完整测试用例并导出 Excel (.xlsx) 或 XMind (.xmind) 格式。当用户要「生成用例」「写测试用例」「导出 Excel」「导出 XMind」「生成测试用例表格」或执行 testspec-generate / testspec generate 时使用。也适用于用户说「把测试点展开成用例」「帮我出一份测试用例表」「生成 Excel 测试文档」的场景。使用内置 Python 脚本完成 Excel/XMind 文件生成，不依赖外部技能。
---

# testspec-generate：用例生成

铁律：每条生成用例都必须可执行、可验证，并可追溯到至少一个当前 TP_ID。

```text
TestSpec 用例生成进度：

- [ ] 步骤 1：定位当前 change 目录 ⚠️ 必需
- [ ] 步骤 2：加载 specs/*.md 和上游 context ⚠️ 必需
- [ ] 步骤 3：选择策略并设计用例
- [ ] 步骤 4：写入 schema v2 testcases.json
- [ ] 步骤 5：运行 validate_testcases.py ⛔ 阻塞
- [ ] 步骤 6：导出 Excel/XMind 并报告产物
```

## 职责

读取当前变更的 `specs/*.md`（测试点），先根据用户目标选择测试类型策略，再将测试点展开为完整测试用例；最后根据用户指定的格式（Excel 或 XMind）生成测试用例文件，输出到当前变更的 `artifacts/` 目录。若存在 `strategy.md` 可参考其测试类型、层级与通过标准；否则从共享规则源读取默认策略。导出行为必须保持兼容现有脚本和历史产物格式。

## 当前变更目录

参见 `../_testspec-shared/references/common.md` 中的「当前变更目录定位规则」。

## 共享规则源

- 测试类型策略单一数据源：`references/test-type-strategies.md`
- 用例设计规则：`references/case-design-rules.md`
- 输出契约：`../_testspec-shared/references/output-contracts.md`
- 命名契约：`../_testspec-shared/references/naming-contract.md`
- 来源与信任：`../_testspec-shared/references/source-provenance.md`

---

## 测试点到用例的转换规则

### 推理式策略选择

> 按 `../_testspec-shared/references/thinking-protocol.md` 执行推理式决策。

#### 上游上下文消费

1. 读取 canonical source（优先 `requirements.md`，否则 `proposal.md`）和直接上游 `specs/testpoints.md`（必须）
2. 按 `../_testspec-shared/references/context-protocol.md` 比对 canonical revision：
   - canonical 有版本，而 testpoints 缺少版本或版本更低：停止并提示先运行 `testspec-points`
   - testpoints 版本高于 canonical：停止并报告版本元数据损坏
   - canonical 无版本：按 Legacy 模式继续并告警，不伪造版本
   - 现有 testcases 过期表示本 skill 应重新生成，不得提示用户再次运行当前 skill
3. 消费 testpoints 上下文：
   - 提取 `risks_identified` → 对风险区域增加异常/边界用例
   - 提取 `coverage_estimate` → 作为覆盖基线
   - 提取 `blocking_open_questions` → 相关用例标注风险
   - 提取 `testlib_reuse`（若有）→ 识别哪些 TP 已在 testlib 中有用例
   - 提取 `regression_tiers`（若有）→ 用例继承对应 TP 的回归层级
   - 提取 `canonical_source_policy`、`evidence_sources`、`questions` → 原样传播；代码不可访问不影响生成
4. 成功生成后原样传播 canonical envelope，从 stale 列表移除 `artifacts/testcases.json`，保留 review，并将 `next_skill` 指向 `testspec-review`

#### testlib 参考用例检索

当 testlib 中存在与当前变更相关的已有用例时，读取作为参考以保持一致性：

1. 每次生成前先检查仓库当前工作区中的 `testspec/testlib/index.json` 是否存在
2. 若存在，通过 testpoints.md 的命名字典匹配 index 中的模块/功能
3. 对匹配到的功能，只读取 2-3 条可用参考：排除 `legacy-import + unverified`；缺少新版 provenance 的历史用例只参考命名和格式
4. 参考用例的作用：
   - **步骤风格一致性**：新用例的步骤写法（编号格式、动作动词、粒度）与同模块已有用例保持一致
   - **预期结果格式一致性**：验证标准的描述粒度和格式与已有用例对齐
   - **前置条件模式复用**：同模块用例的公共前置条件可直接复用
5. 参考用例不影响用例内容设计（场景选择、覆盖策略仍由测试点驱动），仅影响表达风格
6. 若 testlib 不存在或无匹配，兜底走默认生成逻辑（保持兼容）

#### 测试策略推理

通过 3 个核心问题推导测试类型策略，而非关键词匹配：

- **”用户需要什么粒度的测试？”**
  - 上线前快速验证 → smoke 策略
  - 完整功能验证 → functional 策略
  - 回归测试 → functional + boundary + exception

- **”哪些场景最容易被遗漏？”**
  - 权限交叉、并发操作、状态边界 → 补充对应类型
  - 上游标注的风险区域 → 加深覆盖

- **”冒烟用例应该覆盖哪条业务主线？”**
  - 识别最短业务闭环
  - 失败影响最大的功能优先

用户显式指定测试类型时，直接使用，不推理。未指定时默认 `functional`。策略从 `references/test-type-strategies.md` 选取，但选择理由来自推理。

#### 推理结论记录

在 testcases.json 的 `_context` 字段记录推理结论（按 `../_testspec-shared/references/context-protocol.md`），包括：

- canonical revision envelope：source_revision, blocking_open_questions, dynamic_followups, material_quality, stale_downstream_artifacts, stale_reason, next_skill
- 常规字段：coverage_estimate, iteration_count, iteration_summary
- testlib 参考信息：`testlib_reference.referenced_features`（参考了哪些 testlib 功能的已有用例）

### 转换原则

- **一对多映射**：一个测试点可能对应多个测试用例场景
- **场景细化**：根据测试点的验证要点，细化为具体的测试场景；涉及多种输入条件或状态时，须设计多个独立用例
- **数据驱动**：针对边界验证点，设计多组边界数据的测试用例
- **异常覆盖**：针对异常验证点，设计各种异常情况的测试用例
- **优先级独立判断**：测试点中的优先级仅供参考，每个用例根据具体场景独立判断；同一测试点可衍生 P1 到 P3 不同级别的用例

### 验证点类型对应

- 功能验证点 → 正向测试用例（验证功能正常工作）
- 边界验证点 → 边界测试用例（验证临界值处理）
- 异常验证点 → 异常测试用例（验证错误处理）
- 集成验证点 → 集成测试用例（验证模块间交互）
- 非功能性验证点 → 非功能测试用例（性能、安全、兼容性等）

---

## 用例设计方法

生成用例前加载 `references/case-design-rules.md`。按测试点特征选择等价类、边界值、判定表、Pairwise、场景法、错误推测或状态迁移；中等及以上复杂度的 TP 额外做创意测试探索，并在 `_context` 记录新增场景数量。

---

## 用例类型与冒烟用例

测试类型和策略定义见 `references/test-type-strategies.md`。冒烟用例是 P1 的核心子集，只覆盖最短业务闭环、阻塞性功能和高频主流程；质量优先于数量。

### 回归套件层级继承

用例从测试点继承 `regression_tier`（Smoke / Full / Targeted），作为回归测试选取的分层依据：

- **继承规则**：用例的 `regression_tier` 默认等于其 `tp_refs` 中最高层级的测试点（Smoke > Full > Targeted）
- **允许降级**：Agent 可将复杂测试点的部分衍生用例降级（如 Smoke 测试点的边界用例降为 Full）
- **不允许升级**：不得将 Full/Targeted 测试点的用例升级为 Smoke，除非用户显式要求
- **未标注兜底**：若上游 testpoints.md 未包含 `regression_tier`，所有用例默认 `Full`

---

## 优先级规则

按风险和业务影响判定优先级，不套固定比例。P1 覆盖核心业务流程、关键入口、阻塞性功能和所有冒烟用例；P2 覆盖常规重要场景；P3 覆盖低频、边缘、体验类场景。

---

## 用例字段、粒度与反模式

执行前读取：

- `references/case-design-rules.md`：字段规范、设计方法、JSON 转义和反模式
- `references/case-granularity.md`：复杂度自适应、拆分与合并
- `../_testspec-shared/references/naming-contract.md`：标题与模块命名
- `references/testcases-json-example.md`：schema v2 示例

不可省略的主契约：

- `id` 在当前变更内唯一；`title` 使用 `{模块}_{功能点}_{场景}`；`feature` 等于模块
- `tp_refs` 非空且只引用当前变更 TP；多 TP 用例的步骤和预期覆盖每个引用
- TP 的 `oracle_scope = indirect` 时只断言当前系统可观察产物；`out-of-scope` 不生成正式用例
- preconditions/steps/expected_result 使用可执行、可验证的编号文本
- 每条原生用例写 `origin.kind = testspec-native` 和 `trust.status = provisional`
- JSON 合法转义；生成后必须通过结构校验

---

## 校验与迭代

写入用例后，加载 `references/generation-quality-loop.md` 并运行：

```bash
python "<_testspec-shared-skill-dir>/scripts/validate_testcases.py" \
  --input <变更目录>/artifacts/testcases.json \
  --testpoints <变更目录>/specs/testpoints.md \
  --pretty
```

导出前解决全部错误和未通过的 TP 覆盖。最多执行两轮有证据支撑的修正；warning 必须人工检查，不得自动忽略。

## Review 定向返修

用户要求根据 `review-report.md` 修复时进入 repair 模式：

1. 校验 review 与 canonical revision 一致。
2. 只消费 `status = open` 且明确分配给 generate 的 finding；points/analysis finding 必须回到对应上游。
3. 只修改 finding 指定的 case IDs，默认保留 ID；未命中范围的用例保持字节级语义不变。
4. 在 `_context.review_repairs` 记录 `issue_id`、`changed_case_ids` 和动作摘要。
5. generate 不得自行把 finding 标记 resolved；修复后必须重跑 testspec-review。

## 输出格式

- **Excel**：生成 .xlsx 文件，列头依次为：编号、用例标题、级别、预置条件、操作步骤、测试预期内容、执行结果、执行人、执行日期、备注。
- **XMind**：生成 .xmind 思维导图（XMind 8 格式，兼容 XMind 桌面版打开），按功能模块组织，叶子节点使用用例标题（优先使用 title，其次 name），包含正向用例、负向用例、边界值用例、异常用例等分类。用例详情节点格式：`预置条件：xxx` → `{级别}操作步骤：xxx`（如 `P1操作步骤：xxx`）→ `期望结果：xxx`。

导出契约统一以 `../_testspec-shared/references/output-contracts.md` 和当前 skill 目录下的 `scripts/generate_excel.py`、`scripts/generate_xmind.py` 及单测为准。如文档表述与实现冲突，必须以脚本与单测为准，不得擅自改动历史格式。

## 执行步骤

1. **确定当前变更目录**（按上规则）。
2. **读取上下文**：读取 `specs/*.md`（必须）；若存在 `strategy.md`、`requirements-analysis.md` 或 `proposal.md` 可一并读取以保持策略与优先级一致，否则按默认策略展开。
3. **从 specs 提取测试用例**：解析每个 spec 文件中的测试点，运用上述设计方法和转换规则将其展开为结构化测试用例列表。每个用例包含：
   - 功能/模块（必须来自 points 文档的标题层级 `### {模块}模块`；用例字段 `feature` 必须等于 `{模块}`）
   - 用例标题（格式：`{模块}_{功能点}_{测试场景}`；其中 `{模块}`/`{功能点}` 必须与 points 标题层级严格一致）
   - 类型：冒烟 / 正向 / 负向 / 边界 / 异常
   - 前置条件、步骤、预期结果
   - 优先级：P1 / P2 / P3
4. **生成 testcases.json**（schema v2 格式）：

   顶层为对象，包含 `schema_version`、`_context` 和 `testcases` 数组。canonical source 有版本时，`_context.source_revision` 必须与 `specs/testpoints.md` 完全一致。原生生成写 `_context.origin.kind = testspec-native`、`_context.trust.status = provisional`，不得冒充已 review。

### JSON 写入策略

为确保 JSON 格式正确且写入成功：

1. **首选方案**：使用当前执行环境的标准文件编辑机制写入 schema v2 对象
2. **兜底方案**：如果手写转义风险较高，使用结构化 JSON 序列化方式生成文件，避免手动拼接字符串
3. **验证**：`python3 -m json.tool <变更目录>/artifacts/testcases.json > /dev/null && echo "JSON OK"`

固定写入 `<变更目录>/artifacts/testcases.json`，不在变更根目录创建第二份副本。需要字段示例时加载 `references/testcases-json-example.md`。

> 注意：字段值中若包含双引号必须转义（`\"`），推荐用「」替代以避免转义问题。详见「JSON 字符串转义规则」。

5. **调用生成脚本**：
   - **Excel**：执行
     ```bash
     python "<testspec-generate-skill-dir>/scripts/generate_excel.py" --input <变更目录>/artifacts/testcases.json --output <变更目录>/artifacts/<name>_cases.xlsx
     ```
   - **XMind**：执行
     ```bash
     python "<testspec-generate-skill-dir>/scripts/generate_xmind.py" --input <变更目录>/artifacts/testcases.json --output <变更目录>/artifacts/<name>_cases.xmind --title "测试用例"
     ```
   `<testspec-generate-skill-dir>` 必须从当前已加载 SKILL.md 所在目录解析为绝对路径。
6. **保留源文件**：默认保留 `artifacts/testcases.json` 供 review/publish 复用；仅在用户明确要求时清理。
7. **告知用户**：列出生成的文件路径及简要说明。

---

## 生成后反思

确定性校验后使用 `references/generation-quality-loop.md`。报告迭代次数、具体修正、最终 TP 覆盖率、优先级分布和用例数量。

---

## 依赖

- **Excel**：需要 `openpyxl`
- **XMind**：无额外依赖，使用 XMind 8 格式生成，兼容 XMind 桌面版打开
- 当前 skill 的依赖清单位于 `requirements.txt`

若 Excel 生成失败且提示缺少 openpyxl，按当前项目的包管理方式安装 `openpyxl`，不要在未确认的全局环境中直接安装依赖。

## 产物

- `testspec/changes/<name>/artifacts/<name>_cases.xlsx`（Excel 格式）
- `testspec/changes/<name>/artifacts/<name>_cases.xmind`（XMind 格式）

文件名可根据变更名或用户指定调整。
