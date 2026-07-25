# TestKit

TestKit 是一套面向软件测试工作的 Agent Skills 工具集。它覆盖产品需求文档（PRD）分析、测试用例设计、API 自动化、日志诊断、SQL 审查和 Android 静态分析，提供 Claude Code、Codex 完整插件和通用 Agent Skills 入口。

## 开始使用

先按[安装指南](docs/installation.md)加载 TestKit，然后直接描述测试目标：

```text
根据这份 PRD 设计测试用例并导出 Excel
导入这个 YApi 项目，执行登录后的 API 自动化测试
分析这段日志里请求超时的根因
检查这条 SQL 能不能在生产执行
```

Agent 会根据请求选择对应 skill。只有代码扫描、写方法测试、知识库修改等高影响操作需要额外确认。

## 安装入口

TestKit 为不同 Agent 工具提供原生插件和开放 Agent Skills 两类入口。完整步骤、更新方式和 Python 依赖见[安装指南](docs/installation.md)。

### Claude Code

仓库已经包含 `.claude-plugin/marketplace.json`，可直接安装完整 TestKit：

```text
/plugin marketplace add winhok/testkit
/plugin install testkit@testkit
/reload-plugins
```

### Codex

仓库已经包含 `.codex-plugin/plugin.json` 和 `.agents/plugins/marketplace.json`，可直接安装完整 TestKit：

```bash
codex plugin marketplace add winhok/testkit
codex plugin add testkit@testkit-marketplace
```

### 通用 Agent Skills

自包含的独立 skill 可以使用 GitHub CLI 安装：

```bash
gh skill preview winhok/testkit api-test-automation
gh skill install winhok/testkit api-test-automation
```

TestSpec 依赖 `_testspec-shared` 和其他阶段模板，不能用通用安装器拆开安装；请使用 Claude Code 或 Codex 完整插件，或者保留整个 `skills/` 目录。

## 选择测试能力

TestKit 当前包含 15 个公开 skills，按测试任务分为六组：

| 测试任务 | Skills | 适用场景 |
|---|---|---|
| [需求与用例设计](docs/testspec.md) | `testspec-*` | PRD 整理、需求分析、测试点、Excel/XMind 用例、评审和测试知识库（TestLib）入库 |
| [API 自动化测试](docs/api-test-automation.md) | `api-test-automation` | OpenAPI、Swagger、YApi、Postman 导入，登录流程、业务断言和生成式契约测试 |
| [API 工具产物](skills/generate-api-artifacts/SKILL.md) | `generate-api-artifacts` | 从已复核的 OpenAPI 生成 Postman、Apifox 和 JMeter 产物 |
| [日志诊断](skills/log-analysis/SKILL.md) | `log-analysis` | 链路还原、字段溯源、失败与性能诊断、日志查询优化 |
| [SQL 审查](skills/sql-safety-review/SKILL.md) | `sql-safety-review` | 在线事务处理（OLTP）、联机分析处理（OLAP）、DDL、DML、索引、事务和锁风险 |
| [Android 静态分析](skills/android-static-app-reverse/SKILL.md) | `android-static-app-reverse` | APK 导出、反编译、加固检测、接口提取和静态泄漏检查 |

### 从需求到测试知识库

TestSpec 以当前 PRD、产品回答和验收规则为主基线。代码和历史用例只能提供校准证据，不能覆盖产品意图。

```text
testspec-new → testspec-update → testspec-analysis → testspec-points
             → testspec-generate → testspec-review → testspec-publish

历史用例：testspec-import → PRD 对齐 → 主流程
代码证据：testspec-code-calibrate → 产品确认 → 主流程
知识库：  testspec-audit → lifecycle proposal → 用户确认
```

`testspec-code-calibrate` 禁止隐式调用。只有你明确授权代码角色、Git ref 和仓库内 scope 后，TestKit 才会读取代码证据。

### 从接口定义到自动化结果

API 自动化使用两个互补执行轨道：

1. [Arazzo workflow](https://spec.openapis.org/arazzo/latest.html) 执行登录、变量提取、业务断言、数据驱动和清理步骤
2. [Schemathesis](https://schemathesis.readthedocs.io/en/stable/) 根据 OpenAPI 执行 examples、coverage、fuzzing 和 stateful 测试

Swagger/OpenAPI、YApi 和 Postman 输入会先归一化为 OpenAPI。只有你明确要求扫描代码时，TestKit 才会从后端路由生成待复核的 OpenAPI 骨架。

## 常用请求

以下请求覆盖每组能力的主要入口：

```text
新建一个“用户登录”测试工作，整理这份 PRD
导入 legacy-cases.xlsx，并按当前需求核对旧用例
把 openapi.yaml 导出成 Postman Collection 和 JMeter JMX
分析 app.log 中 traceId=1234567890123 的完整链路
Review 这条 ClickHouse SQL 的语义和性能风险
从已连接手机导出 com.example.app，并做纯静态接口分析
```

API 自动化的 CLI、环境变量和公开登录示例见 [API 自动化指南](docs/api-test-automation.md)。

## 安全边界

TestKit 默认采用保守执行策略：

- 未经确认不扫描代码、不执行写方法测试、不修改 TestLib
- API 密钥、密码和 Token 只通过环境变量注入，运行结果执行脱敏
- fuzzing、stateful 和写方法测试只允许在已确认的隔离环境运行
- Android 能力仅执行授权范围内的静态分析，不包含破解、绕过或运行时攻击
- 历史用例先进入隔离区，完成 PRD 对齐和评审后才能进入 TestLib

## 文档

根据当前任务进入对应的操作或维护文档：

- [安装 TestKit](docs/installation.md)
- [使用 TestSpec 设计和维护测试用例](docs/testspec.md)
- [执行 API 自动化测试](docs/api-test-automation.md)
- [验证和维护仓库](docs/development.md)

每个 skill 的完整执行契约位于对应的 `skills/<skill-name>/SKILL.md`。

## 开发验证

安装 Python 依赖后运行仓库级检查：

```bash
python scripts/test_all.py
```

检查组、live eval、TestLib 维护和隐私规则见[开发维护指南](docs/development.md)。

## 仓库结构

根目录只保留插件入口、文档、示例、skills 和验证工具：

```text
testkit/
├── .agents/plugins/     # Codex marketplace
├── .codex-plugin/       # Codex 插件 manifest
├── .claude-plugin/      # Claude Code 插件 manifest
├── assets/              # 插件展示资源
├── docs/                # 用户与维护文档
├── examples/            # 可公开运行的示例
├── plugins/testkit/     # 本地 marketplace 入口
├── scripts/             # 仓库级验证脚本
├── skills/              # 15 个公开 skills 和共享契约
└── tests/               # 插件包装测试
```

## License

MIT
