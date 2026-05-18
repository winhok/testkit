---
name: testspec-new
description: TestSpec 新建测试工作（流程第 1 步）- 创建测试变更目录并编写 proposal.md，关联需求文档。当用户要「新建测试」「开始测试」「创建测试变更」「建一个测试项目」或执行 testspec-new / testspec new 时使用。也适用于用户说「我要测 XXX 功能」「帮我准备测试」「有个新需求要测」的场景——如果尚无 testspec/changes/ 目录，这是流程的起点。产出 testspec/changes/<name>/ 目录结构及 proposal.md。
---

# testspec-new：新建测试工作（需求文档）

IRON LAW: Never create a TestSpec change without a traceable requirement source or an explicit "information insufficient" marker.

```
TestSpec New Progress:

- [ ] Step 1: Identify change name ⚠️ REQUIRED
- [ ] Step 2: Assess input material ⚠️ REQUIRED
- [ ] Step 3: Create change workspace
- [ ] Step 4: Write proposal.md with collaboration checkpoint
- [ ] Step 5: Seed context metadata and report next step
```

## 职责

新建一次 TestSpec 测试工作：创建变更目录并编写测试提案初稿，在 proposal 中**关联或引用需求文档**（PRD、用户故事、接口说明等），对应流程中的「需求文档」步骤。

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

5. **告知用户**：变更目录路径及下一步可执行 testspec-analysis 或 testspec-points。

## 材料评估与工具使用

在编写 proposal.md 之前，对用户提供的材料进行评估：

### 信息密度判断

- **完整 PRD**：用户提供了详细的需求文档链接或内容 → 在 proposal 中完整引用
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
  "signals_detected": ["<从材料中发现的关键信号>"]
}
-->
```

## 产物

- `testspec/changes/<name>/proposal.md`（含上下文元数据）
- `testspec/changes/<name>/specs/`（空目录）
- `testspec/changes/<name>/artifacts/`（空目录）
