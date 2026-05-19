---
name: testspec-new
description: TestSpec 新建测试工作（流程第 1 步）- 创建测试变更目录，编写 proposal.md，并在用户提供已有 PRD/需求片段时净化成可验收的 requirements.md。当用户要「新建测试」「开始测试」「创建测试变更」「建一个测试项目」或执行 testspec-new / testspec new 时使用。也适用于用户说「我要测 XXX 功能」「帮我准备测试」「有个新需求要测」「帮我整理/审查 PRD」的场景——如果尚无 testspec/changes/ 目录，这是流程的起点。产出 testspec/changes/<name>/ 目录结构、proposal.md，必要时产出 requirements.md。
---

# testspec-new：新建测试工作（需求文档）

IRON LAW: Never create a TestSpec change without a traceable requirement source or an explicit "information insufficient" marker; never turn a raw PRD into requirements.md by mere reformatting.

```
TestSpec New Progress:

- [ ] Step 1: Identify change name ⚠️ REQUIRED
- [ ] Step 2: Assess input material ⚠️ REQUIRED
- [ ] Step 3: Create change workspace
- [ ] Step 4: Write proposal.md with collaboration checkpoint
- [ ] Step 5: Run PRD intake and write requirements.md when raw PRD material is available
- [ ] Step 6: Review requirements.md quality when generated
- [ ] Step 7: Seed context metadata and report next step
```

## 职责

新建一次 TestSpec 测试工作：创建变更目录并编写测试提案初稿，在 proposal 中**关联或引用需求文档**（PRD、用户故事、接口说明等）。当输入是已有 PRD 或需求片段时，额外执行 PRD Intake：先审查模糊和缺失，再把材料净化成 `requirements.md`，作为后续 testspec-analysis 的高质量需求源。

`testspec-new` 只负责准备可信需求源；不要在本阶段做测试风险拆解、测试点设计或用例生成。

若当前变更目录已存在，且用户是在补充、修改、删除或澄清 PRD/API/UI/产品口径，改用 `testspec-update` 做需求源口径收敛，不要重新创建变更。

## 共享规则源

- proposal 模板：`references/proposal-template.md`
- requirements 模板：`references/requirements-template.md`
- 输出契约：`../_testspec-shared/references/output-contracts.md`
- 上下文协议：`../_testspec-shared/references/context-protocol.md`

## 确定变更名

- 从用户输入中提取被测对象（功能名、模块名、版本号等）。
- 将名称规范为短名：英文或拼音，空格与特殊字符替换为 `-`（如「用户登录」→ `user-login`，`release 2.0` → `release-2.0`）。

## 执行步骤

1. **确保根目录存在**：若项目下没有 `testspec/changes/`，直接创建（`mkdir -p testspec/changes`）。
2. **创建变更目录**：`testspec/changes/<name>/`，以及子目录 `specs/`、`artifacts/`。
3. **编写 proposal.md**：在变更目录下创建 `proposal.md`。

   模板见 `references/proposal-template.md`，核心字段：
   - 被测对象（功能/模块/版本）
   - **关联需求文档**：路径或链接（PRD、用户故事、接口文档等）
   - 测试目标与原因
   - 可选：关联的 OpenSpec

4. **协作检查点**（写入 proposal.md 末尾、context 元数据之前）：

   > 测试质量的上限取决于测试开始前的信息对齐程度。如果产品、开发、测试三方对需求范围和技术约束的理解不一致，后续分析和用例生成会建立在错误的假设之上。这个检查点的目的不是设置审批门禁，而是让 proposal 的信息质量从源头得到保障，减少下游返工。

   ```markdown
   ## 协作确认
   - [ ] 产品已确认需求范围和验收标准
   - [ ] 开发已确认技术约束和可测试性（如：是否有测试环境、数据准备方式、已知的技术限制）
   - [ ] 测试分析前需澄清的关键问题已列出（→ 将传递给 testspec-analysis 的质询清单）
   ```

   **使用说明**：
   - 默认生成为未勾选状态，不阻塞流程
   - 用户可手动勾选确认，也可跳过直接进入 testspec-analysis
   - 若全部未勾选进入 analysis，testspec-analysis 会在信号检测中识别到 material_quality 偏低，自动加深质询力度
   - 第三项"关键问题"若已填写，将直接传递给 testspec-analysis 作为质询清单的种子输入

5. **PRD Intake（按需）**：若用户提供已有 PRD 内容、PRD 链接/路径可读取内容，或明确要求审查/补全 PRD，则创建 `requirements.md`。
6. **需求质量复核（按需）**：若生成 `requirements.md`，执行六维质量复核并写入文档。
7. **告知用户**：变更目录路径、是否已生成 `requirements.md`，需求质量结论，以及下一步可执行 testspec-analysis 或 testspec-points。

## PRD Intake 模式

触发条件：

- 用户粘贴已有 PRD、需求片段、用户故事或功能清单
- 用户提供可读取的 PRD/需求文档路径或链接
- 用户要求「审查 PRD」「补全需求」「整理成 requirements.md」

执行规则：

1. **先挑刺，不整理**：先识别模糊表述、隐含依赖、缺失验收条件、边界不清、合规/权限/数据隔离等隐藏假设。
2. **只描述做什么**：`requirements.md` 不写 Redis、MQ、数据库表、接口拆分、算法选型等实现方案；未确认的技术约束按影响写入「阻塞澄清项」「执行期动态跟进」或「风险点」。
3. **功能必须可验收**：最终「功能列表」中的每一条必须同时包含功能行为和验收条件；没有验收标准的条目不得伪装完成，按影响移入「阻塞澄清项」「执行期动态跟进」或「风险点」。
4. **边界必须显式化**：明确本期不做什么、输入输出边界、格式/容量/权限/数据隔离边界。
5. **交互追问一次一个问题**：需要用户补信息时，一次只问最高影响的一个问题；可以在 `requirements.md` 中保留完整澄清清单，但对话中只推进一个阻塞点。
6. **AI/算法类需求要有评估标准**：涉及搜索、推荐、问答、识别、生成等效果型能力时，验收条件必须包含样本集/benchmark、通过阈值、人工复核或失败处理标准；缺失则标为风险。
7. **输出产品问题清单**：当 `readiness` 不是 `ready_for_analysis` 或存在阻塞澄清项时，在 `requirements.md` 和最终回复中输出「可复制给产品的问题清单」；对话中仍只追问最高优先级的一个问题。

### 审查维度

- 模糊词：合理、快速、稳定、友好、相关、适当、尽快、准确等不可直接验收的描述
- 隐含依赖：权限模型、租户/数据隔离、审计合规、通知链路、外部系统、内容安全
- 验收缺口：未说明完成标准、错误处理、边界值、容量限制、兼容范围、超时和重试
- 范围边界：本期不支持的角色、格式、平台、流程、异常数据和历史兼容
- 风险点：会影响开发排期、测试验收、合规或上线质量的未确认项

### requirements.md 写入规则

按 `references/requirements-template.md` 生成 `requirements.md`。材料不足时也可以生成，但必须：

- 在「功能列表」中只保留已有明确验收条件的条目
- 「功能列表」中的每条功能必须使用 `REQ-001` 形式编号，并保留来源（原 PRD 章节/第 N 条/链接锚点等）
- 在「阻塞澄清项」中列出不确认就不能进入分析的问题；在「执行期动态跟进」中列出测试执行时发现后再补充的问题
- 在「风险点」中使用 `RISK-001` 形式编号，并说明影响、决策条件或备选处理
- 在末尾播种 `testspec-context`，`source_skill` 为 `testspec-new`，并包含 `material_quality`、`signals_detected`、`blocking_open_questions`、`dynamic_followups`、`source_revision`、`requirements_intake`、`requirement_quality`；完整字段以 `references/requirements-template.md` 为准

### 需求质量复核

生成 `requirements.md` 后，按六维给出 0-100 分：完整性、清晰性、一致性、可测试性、可追溯性、可行性。总分为六维平均值。

结论规则：

- `ready_for_analysis`：总分 >= 90，且无阻断级澄清项
- `needs_clarification`：总分 75-89，或存在会影响测试设计但可继续分析的问题
- `needs_revision`：总分 60-74，需求需明显补写后再继续
- `blocked`：总分 < 60，或核心范围/验收标准缺失导致无法进入后续流程

复核要求：

- 每个扣分原因必须指向具体 REQ-ID、章节或原 PRD 位置
- 风险点不能只登记，必须说明影响、决策条件或备选处理；缺失则扣完整性/可行性
- 发现技术词混入（如缓存、索引、异步、向量、队列、数据库、接口、算法）时，判断它是否为业务可见概念；若只是实现方案，改写成用户可感知行为并扣清晰性
- 执行“陌生人测试”：5 分钟内能否从文档回答系统做什么、谁在用、本期不做什么、成功/失败怎么算、最大风险是什么；答不上来则扣清晰性/完整性
- 总分低于 90 时，不得把 `readiness` 标为 `ready_for_analysis`

### 产品问题清单

当 `readiness != ready_for_analysis` 或 `blocking_open_questions` 非空时，最终回复必须输出可直接转发给产品/开发的问题清单：

```markdown
## 可复制给产品的问题清单
1. [P0/P1/P2] <问题>（影响：<阻塞的分析/验收判断>；需要产品给出：<规则/范围/样例/口径>）
```

排序规则：阻塞澄清项在前，执行期动态跟进在后；每个问题必须关联 REQ/RISK/来源位置。不要把动态跟进计入阻塞问题数。

## 反模式

- 不把原始 PRD 改个格式就当 `requirements.md`
- 不为缺失验收条件的功能补编规则
- 不把实现方案写成需求事实
- 不在总分低于 90 时标记 `ready_for_analysis`
- 不生成无 REQ-ID 或无来源的功能条目
- 不在需求未 ready 时只说“请补充需求”，必须给出可复制给产品的问题清单

## 材料评估与工具使用

在编写 proposal.md 之前，对用户提供的材料进行评估：

### 信息密度判断

- **完整 PRD**：用户提供了详细的需求文档链接或内容 → 在 proposal 中完整引用，并触发 PRD Intake 生成 requirements.md
- **简短描述**：用户只说了功能名称或一句话 → 在 proposal 中标注信息不足，建议补充
- **代码仓库**：用户指向了代码实现 → 尝试读取关键文件，从实现反推需求

### 工具自主使用

- 若用户提供了 PRD 链接 → 抓取链接内容，提取关键信息写入 proposal
- 若用户提到了代码路径 → 读取相关文件或路径匹配结果，理解功能范围
- 若用户提供了设计稿链接 → 抓取可访问内容，提取交互流程

### 上下文播种

在 proposal.md 末尾，按 `../_testspec-shared/references/context-protocol.md` 播种元数据：

```markdown
<!-- testspec-context
{
  "source_skill": "testspec-new",
  "material_quality": "<high/medium/low>",
  "signals_detected": ["<从材料中发现的关键信号>"],
  "blocking_open_questions": ["<不确认就不能进入分析的问题>"],
  "dynamic_followups": ["<测试执行中发现后再补充的问题>"],
  "requirements_intake": {
    "generated": "<true/false>",
    "path": "<requirements.md 或空>",
    "open_question_count": "<阻塞澄清项数量>"
  },
  "source_revision": {
    "version": 1,
    "summary": "<本轮需求源口径摘要>",
    "updated_by_skill": "testspec-new"
  },
  "requirement_quality": {
    "overall_score": "<六维平均分或空>",
    "readiness": "<ready_for_analysis/needs_clarification/needs_revision/blocked 或空>"
  }
}
-->
```

## 产物

- `testspec/changes/<name>/proposal.md`（含上下文元数据）
- `testspec/changes/<name>/requirements.md`（可选；当已有 PRD/需求片段可净化时生成）
- `testspec/changes/<name>/specs/`（空目录）
- `testspec/changes/<name>/artifacts/`（空目录）
