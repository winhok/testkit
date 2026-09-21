<p align="center">
  <img src="assets/logo.svg" width="512" alt="TestKit — 面向实际软件测试的 Agent Skills">
</p>

<p align="center">
  21 个面向实际软件测试的 Agent Skills：从需求与用例设计，到 API 与跨端执行、诊断、缺陷复测和证据验收。
</p>

<p align="center">
  <a href="README.md">English</a> | 简体中文
</p>

# TestKit

TestKit 将可复用、可审查的测试流程封装为 [Agent Skills](https://agentskills.io/)，供 Claude Code、Codex 和其他兼容工具使用。它以当前需求和可追溯的执行证据为基础，连接测试设计、自动化、问题诊断、缺陷复测和验收。

## 为什么使用 TestKit

- **贯通测试流程：** 从 PRD 整理、测试分析、策略、测试点和用例评审，延伸到执行、缺陷复测与验收。
- **互补的 API 测试路径：** 用 Arazzo 表达确定性的业务流程，用 Schemathesis 执行 examples、coverage、fuzzing 和 stateful 测试。
- **Android、iOS、Web 共用证据契约：** 执行前冻结版本、环境和范围，执行后关联原始证据，避免重试或旧结果被错误计为通过。
- **适配存量工程：** 支持 OpenAPI、Swagger、YApi、Postman、历史用例、受控 pytest 资产和旧 API 报告迁移。
- **操作边界明确：** 代码扫描、写方法测试、知识库变更和问题单提交需要相应授权；凭据从环境变量读取，持久化结果执行脱敏。
- **可移植、可验证：** Skills 遵循 Agent Skills 目录约定；仓库提供契约检查、合成 eval 定义和统一测试入口。

## 快速开始

推荐安装完整插件，以保留 TestSpec 和运行测试所需的共享契约。

### Codex

```bash
codex plugin marketplace add winhok/testkit
codex plugin add testkit@testkit-marketplace
```

### Claude Code

```text
/plugin marketplace add winhok/testkit
/plugin install testkit@testkit
/reload-plugins
```

### 其他 Agent Skills 工具

包括 `api-test-automation` 在内的五个自包含 skill 可以预览后独立安装：

```bash
gh skill preview winhok/testkit api-test-automation
gh skill install winhok/testkit api-test-automation
```

TestSpec 和运行测试能力依赖共享目录，应使用完整插件安装。兼容范围、更新方法、Python 依赖和 `npx skills` 入口见[安装指南](docs/installation.md)。

安装后直接描述目标即可：

```text
根据这份 PRD 设计测试用例并导出 Excel。
导入这个 YApi 项目，执行登录后的 API 自动化测试。
在 Android、iOS 和 Web 上执行这组登录用例。
分析这段日志里请求超时的根因。
把缺陷录屏整理成包含时间戳证据的 Bug 草稿。
检查冻结范围中哪些项目仍缺少验收证据。
```

> [!NOTE]
> TestKit 提供流程、脚本和结果契约，不捆绑设备、浏览器服务、Appium driver、业务账号或目标环境。实际执行使用宿主环境中可用且已授权的工具。

## 能力概览

| 目标 | Skill | 输入与产出 |
|---|---|---|
| [需求与用例设计](docs/testspec.md) | `testspec-*` | PRD、产品回答、历史用例 → 分析、策略、测试点、Excel/XMind 用例与评审 |
| [API 自动化测试](docs/api-test-automation.md) | `api-test-automation` | OpenAPI、Swagger、YApi、Postman、pytest → 流程执行、生成式测试与规范化结果 |
| [API 工具产物](docs/generate-api-artifacts.md) | `generate-api-artifacts` | 已复核 OpenAPI → Postman Collection、Apifox 与 JMeter JMX |
| [跨端运行测试](docs/app-test.md) | `app-test` | Android、iOS、Web 目标 → 交互断言、证据与业务旅程结果 |
| [无源码 Web 分析](docs/web-app-reverse.md) | `web-app-reverse` | 无源码网站 → 实现证据与 TestSpec 设计输入 |
| [日志诊断](docs/log-analysis.md) | `log-analysis` | 日志与 trace ID → 请求链还原、字段溯源、失败或性能根因 |
| [SQL 审查](docs/sql-safety-review.md) | `sql-safety-review` | OLTP/OLAP SQL → 语义、性能、索引、事务与锁风险 |
| [Android 静态分析](docs/android-static-app-reverse.md) | `android-static-app-reverse` | 已授权 APK → 反编译、加固线索、接口与静态泄漏线索 |
| [缺陷复测](docs/defect-verification.md) | `defect-verification` | 缺陷和修复版本 → RED、GREEN、REGRESSION 判定与证据 |
| [录屏转问题单](docs/video-to-issue.md) | `video-to-issue` | 缺陷录屏 → 复现步骤、预期/实际结果与时间戳证据 |
| [测试验收](docs/test-acceptance.md) | `test-acceptance` | 冻结范围、结果与证据 → 覆盖检查、证据缺口和当前版本结论 |

每个 `skills/<skill-name>/SKILL.md` 定义触发条件、输入、输出和操作边界。运行型能力共用[执行与证据契约](skills/_test-run-shared/references/execution-contract.md)。

## 工作流如何衔接

### 从需求到已评审用例

TestSpec 以当前 PRD、产品回答和验收规则为主基线。代码和历史用例是校准证据，不能覆盖产品意图。

```text
testspec-new / testspec-update
  → testspec-analysis
  → testspec-plan（条件必需）
  → testspec-points
  → testspec-generate
  → testspec-review
  → testspec-publish

历史用例：testspec-import → PRD 对齐 → 主流程
代码证据：testspec-code-calibrate → 产品确认 → 主流程
无仓库 Web 证据：web-app-reverse → testspec-new（按需）→ 主流程
无仓库 App 证据：android-static-app-reverse → testspec-new（按需）→ 主流程
知识库：testspec-audit → lifecycle proposal → 用户确认
```

`testspec-code-calibrate` 需要显式授权，并在读取代码前明确来源身份和范围。TestSpec 使用 context schema v2；旧 change 的迁移方法见 [TestSpec 指南](docs/testspec.md)。

### 从接口定义到测试结果

```text
OpenAPI / Swagger / YApi / Postman
  → 归一化 OpenAPI
  ├─ Arazzo：登录、变量提取、业务断言、数据驱动、清理
  └─ Schemathesis：examples、coverage、fuzzing、stateful
  → 原始证据 + 规范化结果
```

存量 pytest 是受控兼容入口：仅执行 source manifest 中登记的完整 nodeid，并验证来源和配置绑定。它补充复杂 Python 或遗留场景，不替代 Arazzo 与 Schemathesis。

### 从执行到证据验收

执行前冻结来源、被测构建、环境和检查项。执行后记录尝试与原始证据，再由 `test-acceptance` 判断覆盖情况和当前构建的结论。漏测、旧证据、混合重试及未完成的清理仍会明确显示。

## 操作边界

- 代码扫描、写方法或破坏性测试、TestLib 变更和外部问题单提交都需要明确授权。
- API 密钥、密码和 Token 通过环境变量提供；持久化结果与公开 fixture 经过脱敏和隐私检查。
- fuzzing、stateful 和写方法测试只在已确认的隔离环境运行。
- Android 静态分析只处理已授权目标，不包含绕过或运行时攻击。
- 历史用例完成当前 PRD 对齐和评审后才能进入 TestLib。

## 文档与求助

- [安装与更新](docs/installation.md)
- [TestSpec](docs/testspec.md)
- [API 自动化测试](docs/api-test-automation.md)与 [API 工具产物](docs/generate-api-artifacts.md)
- [Android、iOS 与 Web 测试](docs/app-test.md)与[无源码 Web 分析](docs/web-app-reverse.md)
- [日志诊断](docs/log-analysis.md)、[SQL 审查](docs/sql-safety-review.md)与 [Android 静态分析](docs/android-static-app-reverse.md)
- [缺陷复测](docs/defect-verification.md)与[录屏转问题单](docs/video-to-issue.md)
- [测试验收](docs/test-acceptance.md)与[执行契约](skills/_test-run-shared/references/execution-contract.md)
- [开发与验证](docs/development.md)

问题和建议可提交至 [GitHub Issues](https://github.com/winhok/testkit/issues)。项目由 [winhok](https://github.com/winhok) 维护。

## 开发与贡献

安装仓库依赖后运行统一检查：

```bash
python scripts/test_all.py
```

该入口覆盖插件打包、跨 skill 契约、合成 eval 定义和单元测试。设备、浏览器或公共 API 的 live eval 需要单独配置与记录；离线检查通过不代表外部环境已验收。贡献前请阅读[开发维护指南](docs/development.md)。

## 许可证

MIT
