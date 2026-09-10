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
testspec-new → testspec-update(可重复/可选) → testspec-analysis → testspec-plan(条件必需) → testspec-points → testspec-generate → testspec-review → testspec-publish
  创建变更       需求源口径收敛             需求深度分析        设计证明策略           提炼测试要点       生成测试用例        用例评审        用例入库(可选)
```

`testspec-new` 在有原始 PRD/需求片段时生成 `requirements.md`，作为净化后的可验收需求源。`testspec-update` 用于已有变更中的 PRD/API/UI/产品回答增删改，负责更新需求源并标记旧下游产物。`testspec-plan` 在多环境、多 runner、跨组件、非功能、真实执行、大型拆分或多证据面时必需；简单单环境纯用例设计可跳过。

testspec-publish 是可选步骤：并非所有变更都需要入库。「资产型用例」（核心主流程、长期复用）应入库沉淀；「任务型用例」（一次性验证、临时场景）可跳过。

## 智能编排指引

### 步骤跳转决策

active workflow 必须先完成 context v2 迁移，并按直接上游顺序执行。plan 是否可跳过由 `strategy_requirement` 决定，不再由下游 Skill 临时猜测。旧 change 使用 `migrate_change_context.py`；正常流程不读取旧 context schema。

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
├── requirements.md            # 可验收需求源（testspec-new，可选；testspec-update 可更新）
├── requirements-analysis.md   # 需求分析（testspec-analysis）
├── strategy.md                # 测试策略（testspec-plan，条件必需）
├── review-report.md           # 评审报告（testspec-review）
├── specs/
│   └── testpoints.md          # 测试点（testspec-points）
└── artifacts/
    ├── source-prd.md          # 需求源归档（testspec-update，可选）
    ├── api-doc.md             # 接口口径归档（testspec-update，可选）
    ├── update-log.md          # 口径更新记录（testspec-update，可选）
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
