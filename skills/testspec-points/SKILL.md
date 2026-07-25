---
name: testspec-points
license: MIT
description: TestSpec 测试点（流程第 3 步）- 从需求分析中提炼「要测什么」的简短要点清单，产出 specs/testpoints.md。当用户要「写测试点」「提取测试要点」「列出要验证的内容」或执行 testspec-points / testspec points 时使用。也适用于用户说「这个功能要测哪些点」「帮我列测试清单」的场景。与测试用例区分：测试点只列验证目标（What），不写操作步骤（How）。产出供 testspec-generate 展开为完整测试用例。
---

# testspec-points：测试点

铁律：测试点只描述“验证什么”，绝不描述“如何执行”。

```text
TestSpec 测试点进度：

- [ ] 步骤 1：定位当前 change 目录 ⚠️ 必需
- [ ] 步骤 2：加载 requirements-analysis.md 或 proposal.md ⚠️ 必需
- [ ] 步骤 3：消费上游 context 和 TestLib 信号
- [ ] 步骤 4：生成包含命名字典的 specs/testpoints.md
- [ ] 步骤 5：校验命名契约并反思
- [ ] 步骤 6：写入 context 元数据并报告下一步
```

## 职责

从需求分析结论中**提炼**出简短的测试覆盖要点清单，作为 testspec-generate 的直接输入。

**与 analysis 的关系**：analysis 做深度拆解（等价类、边界值、状态迁移、风险点），points 是 analysis 的"精华版"——把分析结论转化为一条条简短的"要验什么"。如果已有 `requirements-analysis.md`，points 应该从中提炼而非重复分析；如果没有 analysis，按 `requirements.md` → `proposal.md` 的顺序降级提炼并明确覆盖置信度。

---

## 设计契约

生成测试点前，加载 `references/testpoint-design-rules.md`，获取：

- Functional/Boundary/Exception/Integration/Non-Functional 分类
- `TP_<MODULE>_<FEATURE>_<SEQ>` 分配规则
- P1/P2/P3 与 Smoke/Full/Targeted 规则
- 粒度、禁止内容和反模式

同时加载 `../_testspec-shared/references/naming-contract.md`。仅在涉及 TestLib 复用、可选代码证据或信任分类时，加载 `../_testspec-shared/references/source-provenance.md`。

不可妥协的规则：

- 测试点只说明验证目标，不写执行步骤或具体测试数据。
- 每个测试点只表达一个稳定业务意图。
- TestLib 绝不覆盖 PRD；未验证导入不能提供 priority 或 oracle。
- 每个测试点都有 category、TP_ID、priority、requirement reference、`oracle_scope` 和 `oracle_status`。

---

## 当前变更目录

参见 `../_testspec-shared/references/common.md` 中的「当前变更目录定位规则」。

---

## 推理式策略选择

> 按 `../_testspec-shared/references/thinking-protocol.md` 执行推理式决策。

### 上游上下文消费

1. 读取 canonical source（优先 `requirements.md`，否则 `proposal.md`）及直接上游 `requirements-analysis.md`（若存在）
2. 按 `../_testspec-shared/references/context-protocol.md` 比对 canonical revision：
   - 有 analysis 时，canonical 有版本但 analysis 缺少版本或版本更低：停止并提示先运行 `testspec-analysis`
   - 无 analysis 时，直接从 canonical source 降级生成；canonical 有版本则原样传播
   - canonical 无版本时按 Legacy 模式继续并告警，不伪造版本
   - 现有 testpoints 过期表示本 skill 应重新生成，不得提示用户再次运行当前 skill
3. 消费直接上游上下文：
   - 提取有证据的 `risks_identified` → 按影响决定测试点优先级
   - `intuition_flags.status = unverified` → 仅作为核查提示，不自动提升优先级
   - 提取 `blocking_open_questions` → 标注为"需确认"的测试点
   - 提取 `material_quality` → 影响推理深度
   - 提取 `testlib_coverage`（若有）→ 直接使用 analysis 的扫描结论
   - 提取 `canonical_source_policy`、`evidence_sources`、`questions` → 原样传播 PRD-first 证据和稳定问题状态
4. 成功生成后原样传播 canonical envelope，从 stale 列表移除 `specs/testpoints.md`，保留 cases/review，并将 `next_skill` 指向 `testspec-generate`

### testlib 知识库检索

若上游 `testlib_coverage` 不存在或 `scanned = false`，points 自行扫描：

1. 检查 `testspec/testlib/index.json` 是否存在
2. 若存在，读取 index.json 并匹配当前变更涉及的模块关键词
3. 从匹配的模块中提取：
   - **已有 TP_ID 列表**（`tp_ids` 字段）：该功能历史用例曾覆盖过的测试点，用于理解覆盖范围
   - **已有功能覆盖**：哪些功能点已有测试覆盖
   - **关联功能**（`related_features`）：可能需要回归的关联功能
4. 检索结论影响测试点生成策略：
   - **功能未变更，已验证 TestLib 用例覆盖** → 可标注“testlib 已覆盖”；不得仅凭未验证 legacy import 减少覆盖
   - **功能有变更** → 正常生成新 TP（每次变更 SEQ 独立），并结合历史 `tp_ids` 判断哪些区域需要回归
   - **全新功能** → 正常生成
   - **关联功能** → 考虑是否需要补充集成/回归类测试点

### 可复用资产识别

> 工作流中不应只找问题和风险——发现"我们已经有什么"同样重要，能显著提升效率。

在 testlib 检索完成后、覆盖策略推理前，回答以下问题：

1. **已有覆盖复用**：testlib 中哪些已有用例可以直接复用或微调？
2. **自动化友好区域**：哪些模块的功能天然适合自动化（纯数据校验、API 调用、幂等操作）？
3. **测试数据共享**：哪些模块之间可以共享测试前置数据（同一用户、同一订单贯穿多个模块）？
4. **快速收益点**：哪些测试点投入最小但覆盖价值最大（如一条冒烟用例覆盖核心链路 80%）？

**产出**：在 testpoints.md 的「知识库复用摘要」之后增加「可复用资产」小节：

```markdown
## 可复用资产

- testlib 可直接复用：<功能点列表及对应 testlib 路径>
- 自动化友好区域：<模块列表及原因>
- 可共享测试数据：<数据类型及适用模块>
- 快速收益点：<TP_ID 及收益说明>
```

**下游影响**：
- testlib 已覆盖的功能点标记为"复用优先"，generate 阶段优先参考已有用例风格
- 快速收益点在覆盖策略中获得优先安排

### 覆盖策略推理

通过 4 个核心问题决定覆盖深度：

- **"核心业务价值链是什么？"** → 决定 P1 测试点集中在哪些模块
- **"哪些区域风险最高？"** → 上游标注的风险区域加深覆盖
- **"验证粒度应该多细？"** → 材料信息密度高则可细化，低则保持粗粒度
- **"知识库中已有哪些覆盖？"** → testlib 已覆盖的功能点可降低优先级或标记复用

---

## 执行步骤

1. **确定当前变更目录**。
2. **读取上下文**：
   - 优先读 `requirements-analysis.md`（从中提炼）
   - 若不存在，读 `proposal.md`（直接提炼）
3. **生成 specs/testpoints.md**：

### 写入策略（重要）

为确保大文件写入成功，按以下优先级执行：

1. **首选方案**：使用当前执行环境的标准文件编辑机制写入完整内容
2. **兜底方案**：如果一次性写入失败，分段写入同一文件并保持 Markdown 结构完整
3. **验证写入**：读回文件前 10 行和末尾上下文元数据，确认内容正确

### 提炼原则

- 按模块/功能点组织，并按类别分区（Functional / Boundary / Exception / Integration / Non-Functional）
- 每条测试点必须包含：TP_ID、测试点名称、验证要点、优先级（P1/P2/P3）、关联需求
- 每条测试点标注 `oracle_scope: direct/contract/indirect/out-of-scope`；`indirect` 不得声称下游副作用完成，`out-of-scope` 不生成正式用例
- 确保覆盖 analysis 中识别的风险点和边界值
- 不确定项标注"需与产品确认"，同时记录 `oracle_status: needs-confirmation`；优先级仍按潜在业务影响判断，高影响歧义可以是 P1/P2，不补充假设性业务规则

### 输出质量要求

- 测试点必须完整覆盖已确认需求；未确认范围必须显式关联稳定问题，不能假装已覆盖
- 测试点之间不得重复
- 每个测试点必须可独立验证
- 测试点应可直接用于后续测试用例设计

### 默认行为

- 未特别说明时，按"最小充分覆盖"原则生成测试点
- 不主动扩展需求之外的业务场景
- 不推断实现细节

### 产出结构

执行前读取 `references/testpoints-template.md`，严格按模板生成。产物至少包含：

- 概述；实际命中时才输出知识库复用摘要和可复用资产
- 模块/功能命名字典
- 五类测试点分组
- 每条 TP 的 ID、验证要点、影响型优先级、Oracle 状态、回归层级和关联需求
- 文件末尾 canonical revision envelope

4. **告知用户**：产出路径及下一步可执行 testspec-generate。

---

## 反思与迭代

> 按 `../_testspec-shared/references/reflection-protocol.md` 执行产物反思。

产物首次生成后，执行反思循环：

1. **覆盖均衡性**：各模块的测试点数量是否均衡？是否有模块只有 1-2 个点而其他模块 10+？
2. **粒度一致性**：不同模块的测试点粒度是否一致？（同样复杂度的功能，测试点数量差异不应超过 3 倍）
3. **验证要点质量**：每个验证要点是否可独立验证？是否有"验证功能正常"这种模糊描述？

反思后修正产物，最多 2 轮迭代。告知用户迭代次数和修正摘要。

### 上下文播种

在 specs/testpoints.md 末尾，按 `../_testspec-shared/references/context-protocol.md` 播种元数据：

```markdown
<!-- testspec-context
{
  "source_skill": "testspec-points",
  "canonical_source_policy": "prd-first",
  "evidence_sources": [{"type": "<prd/api/ui/code/testlib>", "source_ref": "<从上游继承>", "authority": "<canonical/reference>"}],
  "questions": [{"id": "Q-001", "status": "<open/resolved/invalidated/deferred>", "blocking": true, "question": "<从上游继承>", "resolution": ""}],
  "coverage_estimate": "<各类别覆盖情况>",
  "risks_identified": ["<从上游继承或新发现的风险>"],
  "blocking_open_questions": ["<从上游继承的阻塞问题>"],
  "dynamic_followups": ["<从上游继承的执行期跟进项>"],
  "material_quality": "<从上游继承>",
  "source_revision": {"version": "<canonical 版本>", "summary": "<原样继承>", "updated_by_skill": "<原样继承>"},
  "stale_downstream_artifacts": ["<移除 specs/testpoints.md 后仍过期的产物>"],
  "stale_reason": "<仍有 stale 产物时继承>",
  "next_skill": "<仍有 stale 产物时为 testspec-generate>",
  "regression_tiers": {
    "smoke": ["<Smoke 层级的 TP_ID>"],
    "full": ["<Full 层级的 TP_ID>"],
    "targeted": ["<Targeted 层级的 TP_ID>"]
  },
  "testlib_reuse": {
    "trust_filter": "exclude legacy-import+unverified from facts/oracles",
    "existing_tp_ids": ["<testlib 中已覆盖的 TP_ID>"],
    "new_tp_ids": ["<本次新增的 TP_ID>"]
  }
}
-->
```

## 产物

- `testspec/changes/<name>/specs/testpoints.md`
