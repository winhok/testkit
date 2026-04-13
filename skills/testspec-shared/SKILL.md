---
name: testspec-shared
description: 内部共享资源库，不直接触发。供 testspec-new、testspec-analysis、testspec-points、testspec-generate、testspec-review、testspec-publish 等 testspec-* 技能引用的公共约定、协议、契约、策略定义和产物模板。不要在任何用户场景下直接使用这个 skill。
---

# TestSpec 共享资源

本目录不是可触发的 skill，而是 testspec 套件（new → analysis → points → generate → review → publish）的公共资源库。各 testspec-* skill 按需引用其中的文件。

## 资源清单

### 公共约定

- `common.md` — 当前变更目录定位规则、流程概览、智能编排指引（步骤跳转、回溯建议、上下文传播）、目录结构

### 协议

- `thinking-protocol.md` — 通用推理框架，替代 if-else 路由的三阶段决策协议（材料评估 → 信号分析 → 策略决策）
- `reflection-protocol.md` — 产物生成后的结构化自问自答反思迭代框架
- `context-protocol.md` — 跨 skill 上下文传播契约，通过 HTML 注释块在产物间传递元数据

### 契约

- `output-contracts.md` — 各阶段产物结构约束（requirements-analysis.md、testpoints.md、testcases.json、Excel、XMind）
- `naming-contract.md` — 测试点与用例的命名规则，确保 points ↔ generate 的模块/功能点严格对齐
- `testlib-contracts.md` — 知识库 testlib 的目录结构、文件格式和生命周期规则（testspec-publish 使用）

### 策略定义

- `analysis-modes.md` — testspec-analysis 的分析模式定义（自适应探测、信号驱动的模式选择）
- `test-type-strategies.md` — testspec-generate 的测试类型策略映射（按信号自主选择覆盖类型）
- `artifact-templates.md` — proposal.md、requirements-analysis.md 等产物的标准模板

### 脚本与测试

- `scripts/validate_testcases.py` — 测试用例 JSON 结构校验
- `scripts/validate_skill_contracts.py` — skill 契约合规校验
- `tests/test_validate_skill_contracts.py` — 契约校验脚本的单元测试
