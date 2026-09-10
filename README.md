<p align="center">
  <img src="assets/logo.svg" width="512" alt="TestKit — Agent skills for practical software testing">
</p>

<p align="center">
  面向真实软件测试工作的 21 个 Agent Skills：从需求与用例设计，到 API 与跨端执行、诊断、缺陷复测和证据验收。
</p>

# TestKit

TestKit 将可复用、可审查的测试方法封装为 Agent Skills，让 Claude Code、Codex 和其他兼容 Agent Skills 的工具能够按任务加载对应流程。它以当前需求和可追溯证据为基线，覆盖测试设计、自动化执行、问题诊断与交付验收，而不是只生成一份看起来完整的测试文档。

## 为什么使用 TestKit

- **完整测试链路**：从 PRD 整理、测试分析、策略与用例生成，一直延伸到执行、缺陷复测和验收结论。
- **API 自动化双轨执行**：用 Arazzo 表达确定性业务流程，用 Schemathesis 执行 examples、coverage、fuzzing 和 stateful 测试。
- **Android、iOS、Web 共用一套证据契约**：冻结版本、环境和范围，关联实际结果与原始证据，避免重试或旧证据“洗绿”。
- **面向存量工程**：支持 OpenAPI、Swagger、YApi、Postman、历史用例、受控 pytest 资产和旧 API 报告迁移。
- **默认保守**：代码扫描、写方法测试、知识库变更和问题单提交都有显式边界；凭据通过环境变量注入，结果执行脱敏。
- **可验证、可移植**：公开 skills 遵循 Agent Skills 目录约定，仓库提供契约检查、合成 eval 和统一测试入口。

## 快速开始

推荐安装完整插件，以保留 TestSpec 和运行测试所需的共享契约。

### Codex

仓库通过 `.codex-plugin/plugin.json` 描述完整插件，并由 `.agents/plugins/marketplace.json` 提供 `testkit-marketplace` 入口：

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

### 通用 Agent Skills

`api-test-automation`、`generate-api-artifacts`、`log-analysis`、`sql-safety-review` 和 `android-static-app-reverse` 是自包含 skills，可先预览再独立安装：

```bash
gh skill preview winhok/testkit api-test-automation
gh skill install winhok/testkit api-test-automation
```

TestSpec 与运行测试能力依赖共享目录，不适合拆开安装。完整兼容范围和 `npx skills` 入口见[安装指南](docs/installation.md)。

安装后直接描述目标，不需要记 skill 名称：

```text
根据这份 PRD 设计测试用例并导出 Excel
导入这个 YApi 项目，执行登录后的 API 自动化测试
在 Android、iOS 和 Web 上执行这组登录用例
分析这段日志里请求超时的根因
把这段缺陷录屏整理成包含时间戳证据的 Bug 草稿
检查本次冻结范围是否全部执行，哪些证据仍不足以验收
```

更新、通用 Agent Skills 安装、Python 依赖和团队环境配置见[安装指南](docs/installation.md)。

> [!NOTE]
> TestKit 提供工作流、脚本和结果契约，不捆绑设备、浏览器服务、Appium driver、业务账号或目标环境。运行时会使用宿主实际可用且已授权的工具。

## 能力地图

| 目标 | Skills | 典型输入与产出 |
|---|---|---|
| [需求与用例设计](docs/testspec.md) | `testspec-*` | PRD、产品回答、历史用例 → 分析、策略、测试点、Excel/XMind 用例与评审结果 |
| [API 自动化测试](docs/api-test-automation.md) | `api-test-automation` | OpenAPI、Swagger、YApi、Postman、pytest → 工作流执行、生成式测试与规范化结果 |
| [API 工具产物](docs/generate-api-artifacts.md) | `generate-api-artifacts` | 已复核 OpenAPI → Postman Collection、Apifox 与 JMeter JMX |
| [跨端运行测试](docs/app-test.md) | `app-test` | Android、iOS、Web 目标 → 交互断言、证据和跨端旅程结果 |
| [Web 应用逆向](docs/web-app-reverse.md) | `web-app-reverse` | 无源码网站 → 实现证据、全局测试地图和 TestSpec 设计输入 |
| [日志诊断](docs/log-analysis.md) | `log-analysis` | 日志与 trace ID → 链路还原、字段溯源、失败或性能根因 |
| [SQL 审查](docs/sql-safety-review.md) | `sql-safety-review` | OLTP/OLAP SQL → 语义、性能、索引、事务和锁风险 |
| [Android 静态分析](docs/android-static-app-reverse.md) | `android-static-app-reverse` | 已授权 APK → 反编译、加固识别、接口与静态泄漏线索 |
| [缺陷复测](docs/defect-verification.md) | `defect-verification` | 缺陷与修复版本 → RED、GREEN、REGRESSION 判定和证据 |
| [录屏转问题单](docs/video-to-issue.md) | `video-to-issue` | 缺陷录屏 → 复现步骤、预期/实际结果和时间戳证据 |
| [测试验收](docs/test-acceptance.md) | `test-acceptance` | 冻结范围、结果与证据 → 覆盖检查、证据缺口和当前版本结论 |

每个 skill 的触发条件、输入、输出和操作边界都记录在对应的 `skills/<skill-name>/SKILL.md` 中。所有运行型能力共用[执行与证据契约](skills/_test-run-shared/references/execution-contract.md)。

## 核心工作流

### 从需求到测试知识库

TestSpec 以当前 PRD、产品回答和验收规则为主基线。代码和历史用例只提供校准证据，不能覆盖产品意图。

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
无仓库 Web 实现证据：web-app-reverse → testspec-new（按需）→ testspec-analysis → 主流程
无仓库 App 参考证据：android-static-app-reverse → testspec-new（按需）→ testspec-analysis → 主流程
无仓库 App 代码校准：android-static-app-reverse → testspec-code-calibrate（按需、显式授权）→ 产品确认 → testspec-analysis → 主流程
知识库：  testspec-audit → lifecycle proposal → 用户确认
```

`testspec-code-calibrate` 禁止隐式调用。读取源码或反编译代码前，需要明确代码角色、来源身份和 scope；非 Git 逆向快照使用 `unavailable` ref/commit，并记录与 APK 身份绑定的 `snapshot_reason`。TestSpec 当前使用 context schema v2；旧 change 的迁移步骤见 [TestSpec 指南](docs/testspec.md)。

### 从接口定义到自动化结果

```text
OpenAPI / Swagger / YApi / Postman
  → 归一化 OpenAPI
  ├─ Arazzo：登录、变量提取、业务断言、数据驱动、清理
  └─ Schemathesis：examples、coverage、fuzzing、stateful
  → 原始证据 + 规范化结果
```

存量 pytest 是受控兼容入口，只执行 source manifest 已登记的完整 nodeid，并校验来源和配置绑定；它补充复杂 Python 或遗留场景，不替代 Arazzo 与 Schemathesis。

### 从执行到证据验收

执行前冻结需求或用例来源、被测构建、环境与检查范围；执行后关联原始结果和证据，再由 `test-acceptance` 判断覆盖与结论。漏测、旧版本证据、混合重试和未满足的清理条件不会被包装为“全部通过”。

## 安全边界

- 未经明确授权，不扫描代码、不执行写方法或破坏性测试、不修改 TestLib、不提交外部 Issue。
- API 密钥、密码和 Token 只通过环境变量注入；持久化结果和公开 fixture 执行脱敏与隐私检查。
- fuzzing、stateful 和写方法测试只在已确认的隔离环境运行。
- Android 静态分析只处理已授权目标，不包含破解、绕过或运行时攻击。
- 历史用例先隔离导入，完成当前 PRD 对齐和评审后才能进入 TestLib。

## 文档

- [安装与更新](docs/installation.md)
- [TestSpec：需求分析、用例设计与知识库](docs/testspec.md)
- [API 自动化测试](docs/api-test-automation.md)
- [API 工具产物](docs/generate-api-artifacts.md)
- [Android、iOS 与 Web 运行测试](docs/app-test.md)
- [无源码 Web 应用逆向](docs/web-app-reverse.md)
- [服务端日志分析](docs/log-analysis.md)
- [SQL 安全、规范与性能审查](docs/sql-safety-review.md)
- [Android 应用静态分析](docs/android-static-app-reverse.md)
- [缺陷修复验证](docs/defect-verification.md)
- [缺陷录屏转问题单](docs/video-to-issue.md)
- [测试结果与证据验收](docs/test-acceptance.md)
- [开发、验证与发布前检查](docs/development.md)

## 开发与贡献

安装仓库依赖后运行统一检查：

```bash
python scripts/test_all.py
```

该入口覆盖插件打包、跨 skill 契约、合成 eval 定义和单元测试。真实设备、浏览器或公共 API 的 live eval 需要单独配置和记录，离线检查通过不代表外部环境已验收。

提交变更前请阅读[开发维护指南](docs/development.md)。问题与建议可通过 [GitHub Issues](https://github.com/winhok/testkit/issues) 提交；项目由 [winhok](https://github.com/winhok) 维护。

## License

MIT
