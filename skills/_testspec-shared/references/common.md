# TestSpec 公共约定

## 当前变更目录定位规则

所有 testspec-* skill 共享以下规则来确定「当前变更目录」：

1. 若用户指定了变更名 → `testspec/changes/<name>/`
2. 若未指定，检查 `testspec/changes/` 下有几个**非 archive** 子目录：
   - 仅 1 个 → 自动使用该目录
   - 多个 → 列出选项，询问用户
   - 0 个 → 提示用户先执行 testspec-new 创建变更

## 流程概览

```
testspec-new → testspec-analysis → testspec-points → testspec-generate → testspec-review → testspec-publish
  创建变更       需求深度分析         提炼测试要点       生成测试用例        用例评审        用例入库(可选)
```

每个步骤的产物是下一步骤的输入。跳步执行时（如直接从 new 到 points），中间产物按默认策略生成。

testspec-publish 是可选步骤：并非所有变更都需要入库。「资产型用例」（核心主流程、长期复用）应入库沉淀；「任务型用例」（一次性验证、临时场景）可跳过。

## 智能编排指引

### 步骤跳转决策

流程中的每个步骤不是必须顺序执行的。在进入下一步之前，评估已有材料是否足够：

- **材料充足**（信息密度高、结构清晰）：可以跳过中间步骤。例如，如果 proposal.md 中已包含详细的功能拆解和风险点，可以直接进入 testspec-points 而跳过 analysis。
- **材料不足**（信息密度低、模糊点多）：必须经过完整流程。缺少 analysis 时生成的测试点容易遗漏风险。

### 回溯建议

当下游 skill 发现上游产物质量不足时，不要默默降级。应提供选项让用户决定：

- 回到上游补充（推荐，质量最高）
- 在当前步骤尽力弥补，标注风险
- 继续执行，在 review 阶段集中处理

### 上下文传播

所有 testspec-* skill 遵循 `context-protocol.md` 进行跨 skill 上下文传播。上游 skill 在产物中播种元数据，下游 skill 在执行前读取并纳入推理。

### 推理式决策

所有 testspec-* skill 使用 `thinking-protocol.md` 进行策略决策，使用 `reflection-protocol.md` 进行产物质量反思。详见各协议文件。

## 命名契约

testspec-points 和 testspec-generate 共享命名规则，详见 `naming-contract.md`。

## 目录结构

### 变更工作区（临时，按需求/版本）

```
testspec/changes/<name>/
├── proposal.md                # 测试提案（testspec-new）
├── requirements-analysis.md   # 需求分析（testspec-analysis）
├── review-report.md           # 评审报告（testspec-review）
├── specs/
│   └── testpoints.md          # 测试点（testspec-points）
└── artifacts/
    ├── testcases.json         # 测试用例 JSON（testspec-generate）
    ├── <name>_cases.xlsx      # 测试用例 Excel（testspec-generate）
    └── <name>_cases.xmind     # 测试用例 XMind（testspec-generate）
```

### 知识库（持久，按模块/功能）

```
testspec/testlib/
├── .testlib.json              # 库配置与统计摘要
├── index.json                 # 全局索引（模块→功能→用例摘要，供上游检索）
├── log.md                     # 操作日志（顶部插入，最新在前）
├── modules/                   # 按模块组织的用例（testspec-publish）
│   ├── <module>/
│   │   └── <feature>.json     # 功能用例集（含交叉引用）
│   └── ...
└── changelog/                 # 发布变更日志（结构化 JSON）
    └── <YYYY-MM-DD>_<change-name>.json
```

知识库的详细格式契约见 `../../testspec-publish/references/testlib-contracts.md`。

### 知识库闭环

知识库不只是用例的终点，更是新变更的起点：

```
testspec-publish ──写入──→ testlib (index.json + modules/ + log.md)
                                │
testspec-analysis ←─检索──┘  （扫描 index.json 发现已有覆盖和回归风险）
testspec-points   ←─检索──┘  （参考历史覆盖 TP_ID，辅助判断复用与回归范围）
testspec-generate ←─检索──┘  （参考已有用例保持步骤/预期结果风格一致）
```
