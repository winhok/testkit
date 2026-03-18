---
name: testspec-new
description: TestSpec 新建测试工作（流程第 1 步）- 创建测试变更目录并编写 proposal.md，关联需求文档。当用户要「新建测试」「开始测试」「创建测试变更」「建一个测试项目」或执行 testspec-new / testspec new 时使用。也适用于用户说「我要测 XXX 功能」「帮我准备测试」「有个新需求要测」的场景——如果尚无 testspec/changes/ 目录，这是流程的起点。产出 testspec/changes/<name>/ 目录结构及 proposal.md。
---

# testspec-new：新建测试工作（需求文档）

## 职责

新建一次 TestSpec 测试工作：创建变更目录并编写测试提案初稿，在 proposal 中**关联或引用需求文档**（PRD、用户故事、接口说明等），对应流程中的「需求文档」步骤。

## 确定变更名

- 从用户输入中提取被测对象（功能名、模块名、版本号等）。
- 将名称规范为短名：英文或拼音，空格与特殊字符替换为 `-`（如「用户登录」→ `user-login`，`release 2.0` → `release-2.0`）。

## 执行步骤

1. **确保根目录存在**：若项目下没有 `testspec/changes/`，直接创建（`mkdir -p testspec/changes`）。
2. **创建变更目录**：`testspec/changes/<name>/`，以及子目录 `specs/`、`artifacts/`。
3. **编写 proposal.md**：在变更目录下创建 `proposal.md`。

   模板见 `../testspec-shared/artifact-templates.md` 中的「proposal.md」小节，核心字段：
   - 被测对象（功能/模块/版本）
   - **关联需求文档**：路径或链接（PRD、用户故事、接口文档等）
   - 测试目标与原因
   - 可选：关联的 OpenSpec

4. **告知用户**：变更目录路径及下一步可执行 testspec-analysis 或 testspec-points。

## 材料评估与工具使用

在编写 proposal.md 之前，对用户提供的材料进行评估：

### 信息密度判断

- **完整 PRD**：用户提供了详细的需求文档链接或内容 → 在 proposal 中完整引用
- **简短描述**：用户只说了功能名称或一句话 → 在 proposal 中标注信息不足，建议补充
- **代码仓库**：用户指向了代码实现 → 尝试读取关键文件，从实现反推需求

### 工具自主使用

- 若用户提供了 PRD 链接 → 使用 WebFetch 获取内容，提取关键信息写入 proposal
- 若用户提到了代码路径 → 使用 Read/Glob 读取相关代码，理解功能范围
- 若用户提供了设计稿链接 → 使用 WebFetch 获取，提取交互流程

### 上下文播种

在 proposal.md 末尾，按 `context-protocol.md` 播种元数据：

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
