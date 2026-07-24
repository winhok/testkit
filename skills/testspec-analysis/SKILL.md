---
name: testspec-analysis
description: TestSpec 需求分析和梳理（流程第 2 步）- 对需求做深度测试分析，运用等价类、边界值、状态迁移等方法，产出 requirements-analysis.md。当用户要「分析需求」「梳理测试点」「做需求分析」「拆解可测项」或执行 testspec-analysis / testspec analysis 时使用。也适用于用户说「这个 PRD 有哪些要测的」「帮我分析一下测试范围」「需求评审准备」的场景。注意：如果用户要的是简短的测试点清单而非深度分析，应使用 testspec-points。
---

# testspec-analysis：需求分析和梳理

IRON LAW: Never replace requirements analysis with a reformatted PRD; every issue must explain why it affects testing.

```
TestSpec Analysis Progress:

- [ ] Step 1: Locate current change directory ⚠️ REQUIRED
- [ ] Step 2: Load requirements/proposal and available source material ⚠️ REQUIRED
- [ ] Step 3: Choose analysis modes from references/analysis-modes.md
- [ ] Step 4: Analyze risks, gaps, and testability
- [ ] Step 5: Run interrogation loop when ambiguity affects test design
- [ ] Step 6: Reflect, seed context metadata, and report next step
```

## 职责

对需求进行**深度测试分析**，先基于用户目标和上下文选择合适的分析模式，再产出结构化的 `requirements-analysis.md`。核心价值是**发现隐含风险、缺失信息和逻辑漏洞**，而不是把需求文档换个格式重新罗列。

**与 testspec-points 的分工**：analysis 做深度拆解（"为什么要测、有哪些风险"），points 从 analysis 中提炼精简清单（"要测什么"，一句话一条）。

## 当前变更目录

参见 `../_testspec-shared/references/common.md` 中的「当前变更目录定位规则」。

## 共享规则源

- 分析模式单一数据源：`references/analysis-modes.md`
- 输出契约：`../_testspec-shared/references/output-contracts.md`
- 产物模板：`references/requirements-analysis-template.md`
- 需求审问闭环：`references/interrogation-loop.md`
- 来源、可选代码证据与 TestLib 信任：`../_testspec-shared/references/source-provenance.md`

## 执行步骤

1. **确定当前变更目录**。
2. **读取上下文**：优先读取 `requirements.md`（若存在）；否则读取 `proposal.md`（必须）。若有外部需求文档（PRD、设计稿链接），尽可能获取内容。
3. **判定分析模式**：根据用户目标和输入材料，从 `references/analysis-modes.md` 中选择一个或多个模式。
4. **按模式执行分析**：合并模式结果，生成兼容现有结构的 `requirements-analysis.md`。
5. **告知用户**：文件路径及下一步可执行 testspec-points 提炼测试要点。

---

## 推理式策略选择

> 按 `../_testspec-shared/references/thinking-protocol.md` 执行推理式决策。

### 材料评估与上下文消费

1. 读取所有可用需求输入（优先 requirements.md，其次 proposal.md、外部链接）。代码不是默认输入，只在用户授权时读取
2. 检查上游产物是否包含上下文元数据（按 `../_testspec-shared/references/context-protocol.md`）
3. 评估信息密度和关键信号：
   - 若存在 requirements.md：以其「功能列表」「边界声明」「风险点」「阻塞澄清项」「执行期动态跟进」作为主需求源；blocking_open_questions 直接纳入质询清单种子输入，dynamic_followups 作为执行期关注点记录但不阻塞分析
   - 将 requirements.md（否则 proposal.md）作为 canonical source。若其 context 有 `source_revision`，本次生成必须原样复制该版本；不得自行递增
   - canonical source 有版本，而现有 requirements-analysis.md 缺少版本、版本更低，或 stale 列表命中 requirements-analysis.md：重新生成分析，不复用旧口径结论
   - canonical source 无版本：按 Legacy 模式继续并告警，不得伪造 `source_revision`
   - 重新生成成功后，从向下传播的 stale 列表移除 requirements-analysis.md，保留仍需重跑的 testpoints/cases/review，并把 `next_skill` 指向 testspec-points
   - 若 requirements.md context 中 `requirement_quality.readiness` 为 `blocked` 或 `needs_revision`：先提示用户需求质量不足，建议回到维护当前 requirements.md 的 skill 补齐（若 `source_revision.updated_by_skill == "testspec-update"` 或变更目录已存在，使用 testspec-update；否则使用 testspec-new）；若用户仍要求继续，则加深质询并在 requirements-analysis.md 中标注低置信度
   - 检查 proposal.md 中「协作确认」勾选状态：全部未勾选 → `material_quality` 预判为 `low`，自动加深质询力度；已填写的「关键问题」项直接纳入质询清单种子输入
   - 保持 `canonical_source_policy = prd-first`；按 `evidence_sources` 区分 intended / observed / inferred / unverified，代码不可访问不得成为阻塞项
4. **扫描 testlib 已有覆盖**（若 `testspec/testlib/index.json` 存在）：
   - 从 proposal.md 提取被测模块关键词
   - 读取 `index.json`，匹配相关模块和功能
   - 统计已有用例数、优先级分布、已覆盖功能点和关联功能
   - 仅当需要参考具体用例内容时，再按 `index.json` 中的 `file` 路径定点读取对应 `<feature>.json`
   - TestLib 只用于回归、命名和覆盖提示，不覆盖 PRD；`legacy-import + unverified` 不得成为风险证据或 oracle
   - 结论纳入分析：哪些已验证功能可复用、哪些是新增、哪些历史用例需要审计

### 假设扫描

> 在正式分析前快速记录可能遗漏的方向。这里产生的是待验证假设，不是风险结论。

在完成材料评估后、进入正式模式推理前，快速浏览需求材料并记录待验证假设：

1. **待核查模块**：哪个模块可能存在未显式说明的状态、权限或边界？
2. **过于顺畅的描述**：哪些描述可能省略了异常或依赖？
3. **质量直觉**：对整体需求质量的信心评估（几成把握认为信息足够设计测试？）

**规则**：

- 每条假设标记 `unverified`，并在正式分析中寻找需求、接口、设计或历史用例证据
- 找到证据后才能进入 `risks_identified`，并记录证据位置
- 未找到证据的假设保留在 `intuition_flags`，不得自动提高 points 优先级或增加 generate 用例
- 扫描控制在 30 秒到 1 分钟

**产出**：在 requirements-analysis.md 的「分析摘要」后增加「假设扫描」小节：

```markdown
## 假设扫描

- 待验证：<模块/功能名> — <可能遗漏的方向> — 状态：unverified/confirmed/rejected
- 证据：<REQ/API/设计稿/testlib 位置；unverified 时写“暂无”>
- 整体信心：<X/10>
```

**下游影响**：

- confirmed 假设进入 `risks_identified`，注明证据位置
- unverified 假设仅作为后续核查提示，不改变测试点优先级和用例数量
- rejected 假设保留一句结论，避免后续重复猜测

### 模式推理

通过 3 个核心问题推导分析模式，而非关键词匹配：

- **"这份材料最大的测试风险在哪里？"**
  - 信息缺失多 → completeness 权重高
  - 逻辑状态复杂 → logic 权重高
  - 预期结果模糊 → testability 权重高

- **"材料中是否有技术/安全/歧义/矛盾特征？"**
  - 涉及第三方依赖、性能、安全 → 增加 feasibility
  - 术语不一致、一词多义 → 增加 clarity
  - 前后规则冲突 → 增加 consistency

- **"用户的实际关注点是什么？"**
  - 用户明确指定模式时，直接使用
  - 用户描述了关注方向时，推导对应模式
  - 未指定时，按推理结论选择，兜底 completeness + testability + logic

### 工具使用决策

- 信息不足时，主动获取外部信息（按 `../_testspec-shared/references/thinking-protocol.md` 的优先级）
- 信息足够时，直接进入分析

### 执行原则

- 先做推理判断，再分析，不要一上来套统一大模板
- 只读取本次任务需要的模式定义，避免把所有模式全文复述给用户
- 分析结论聚焦"为什么这是风险/缺口"，不输出测试步骤和具体数据
- 发现需求不明确时，标记"需与产品确认"，不要替需求方编造规则
- 不要把 requirements.md 再格式化一遍；analysis 必须指出需求对测试设计、验收判断或覆盖策略的影响
- 用户显式启用代码校准时，将实现细节放入「实现证据附录」并标明组件和可观察范围；正文仍保持长期稳定的业务分析

---

## 反思与迭代

> 按 `../_testspec-shared/references/reflection-protocol.md` 执行产物反思。

产物首次生成后，执行反思循环：

1. **完整性检查**：是否有功能模块被跳过？风险点是否仅停留表面？
2. **价值检查**：产出中有多少内容是直接从需求文档复述的？每个问题是否指出了"为什么这是风险"？
3. **迭代决策**：points 作者能否从这份分析中直接提炼测试点？

反思后修正产物，最多 2 轮迭代。告知用户迭代次数和修正摘要。

### 上下文播种

在 requirements-analysis.md 末尾，按 `../_testspec-shared/references/context-protocol.md` 播种元数据：

```markdown
<!-- testspec-context
{
  "source_skill": "testspec-analysis",
  "canonical_source_policy": "prd-first",
  "evidence_sources": [{"type": "<prd/api/ui/code/testlib>", "source_ref": "<从上游继承>", "authority": "<canonical/reference>"}],
  "questions": [{"id": "Q-001", "status": "<open/resolved/invalidated/deferred>", "blocking": true, "question": "<问题>", "resolution": ""}],
  "thinking_summary": "<推理过程摘要>",
  "risks_identified": ["<有材料证据的关键风险，附证据位置>"],
  "intuition_flags": [{"signal": "<待验证假设>", "status": "unverified/confirmed/rejected", "evidence": "<证据位置或空>"}],
  "blocking_open_questions": ["<不确认就不能进入下一步的问题>"],
  "dynamic_followups": ["<执行期跟进项>"],
  "material_quality": "<high/medium/low>",
  "strategy_used": "<使用的分析模式组合>",
  "source_revision": {"version": "<从 requirements.md 消费的版本号>", "summary": "<需求源摘要>", "updated_by_skill": "<上游 skill>"},
  "stale_downstream_artifacts": ["<移除 requirements-analysis.md 后仍过期的下游产物>"],
  "stale_reason": "<仍有 stale 产物时继承>",
  "next_skill": "<仍有 stale 产物时通常为 testspec-points>",
  "testlib_coverage": {
    "scanned": true,
    "related_modules": ["<匹配到的 testlib 模块>"],
    "existing_case_count": 0,
    "reusable_features": ["<可复用的功能点>"],
    "regression_risk_features": ["<可能需要回归的功能点>"],
    "trust_filter": "exclude legacy-import+unverified from facts/oracles"
  }
}
-->
```

## 反模式识别（Agent 自检参照）

> 生成产物后，对照以下反模式自查。发现符合的情况时自动修正。

| 反模式       | 表现                                       | 正确做法                                                   |
| ------------ | ------------------------------------------ | ---------------------------------------------------------- |
| **需求复述** | 分析内容只是把需求文档换了个说法重写一遍   | 每个分析项必须指出"为什么这是风险"或"缺了什么"             |
| **万能模板** | 所有功能模块的分析结构完全相同，缺少针对性 | 根据模块特性选择性使用分析框架，复杂模块深入、简单模块精简 |
| **伪风险**   | 风险点全是"可能出错""需要注意"等泛泛之言   | 风险必须指向具体场景（"并发修改同一订单时状态冲突"）       |
| **实现泄漏** | 未授权时读取代码，或把内部细节混入产品需求 | 默认 PRD-first；显式代码校准时放入带 scope 的实现证据附录 |
| **过度发散** | 分析了大量与当前需求无关的"最佳实践"       | 只分析当前需求范围内的内容，标注明确的需求边界             |
| **缺失审问** | 发现需求不明确但没有列出问题清单           | 发现不明确处必须产出结构化问题，标注测试影响               |

---

## 需求审问（Agentic 能力）

当需求存在会影响用例设计或测试结果判断的不明确项时，加载 `references/interrogation-loop.md`，生成「需求审问清单」并支持后续回答合并。

---

## 分析目标

识别需要验证的业务行为和质量属性，按 **Functional / Boundary / Exception / Integration / Non-Functional** 五个维度覆盖。分析聚焦"验证什么"和"为什么值得验证"，不涉及"如何执行测试步骤"。

## 通用分析方法

按需使用以下方法，不机械套用：

- **功能拆解**：将大功能拆为可独立验证的子功能
- **等价类划分**：识别输入/条件的有效类与无效类
- **边界值分析**：找出临界值（0/1、空/满、最大/最小+1）
- **状态迁移**：梳理状态机，关注非法状态转换
- **错误推测**：推测高风险异常场景（网络断开、并发操作、极端数据）
- **非功能性审视**：性能、安全、兼容性、可靠性、可用性

## 分析内容基线

从需求中识别以下内容，按 **模块 → 功能点** 层级组织：

- 核心业务模块
- 独立业务动作
- 明确状态变化
- 明确规则或约束
- 关键异常与恢复路径
- 非功能性关注点（若材料显式或隐式提及）

以下内容优先作为独立分析项：

- CRUD 行为
- 业务动作（登录、支付、审核、发布等）
- 状态变更（启用/禁用、成功/失败、通过/拒绝）
- 权限与角色控制
- 关键系统反馈（成功提示、错误提示、跳转、回退、重试）

必须覆盖以下异常类型：

- **输入异常**：空值、非法值、超长、特殊字符
- **权限异常**：未登录、无权限、会话失效
- **系统异常**：服务不可用、网络异常、超时

在需求中明确或隐含以下质量属性时，必须纳入分析：

- **性能**：响应时间、并发能力、资源使用
- **安全**：认证与授权、加密传输与存储、输入安全（XSS / SQL 注入）、审计日志
- **易用性**：错误提示清晰度、操作反馈完整性
- **兼容性**：浏览器 / 设备 / 系统兼容、新旧版本兼容
- **可靠性**：异常恢复能力、稳定性、数据保护能力

## 粒度控制

- 一个分析项只聚焦一个业务意图
- 不以字段为单位拆分
- 不以接口参数为单位拆分
- 出现"且 / 并且 / 同时"时，评估是否拆分为多个分析项
- 分析结论应长期稳定，不随实现细节变化

## 需求不明确处理

当需求未明确说明某行为时：

- 仍进行分析，但标注"需与产品确认"
- 不补充假设性业务规则
- 不推断实现细节

## 禁止事项

- 不包含操作步骤（点击、输入、跳转等）
- 不包含具体测试数据
- 默认正文不包含接口字段名、表结构或实现方式
- 显式代码校准时只记录与可测试契约有关的证据，并标记 `oracle_scope`
- 不生成测试用例形式内容

## 产出结构

严格按 `references/requirements-analysis-template.md` 写入完整结构。执行前读取该模板；不要在 SKILL.md 中临时发明平行格式。至少保留：

- 需求来源、分析摘要和假设扫描
- 有证据的位置化问题、已明确内容和建议补充
- 按模块组织的输入/输出、边界、状态、业务规则和风险
- testlib 已有覆盖摘要（仅在实际命中时）
- 非功能性关注点、阻塞澄清项、执行期动态跟进
- 文件末尾 canonical revision envelope

兼容约束见 `../_testspec-shared/references/output-contracts.md`。

## 产物

- `testspec/changes/<name>/requirements-analysis.md`
