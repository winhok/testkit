---
name: test-api-contracts
description: 导入、检查、规范化并测试 HTTP API 定义，支持 Swagger/OpenAPI 2.0、OpenAPI 3.0/3.1/3.2、YApi 项目导出或 Open API、Postman Collection 2.1；仅在用户明确要求时静态扫描后端源码，并生成待复核的 OpenAPI 骨架。适用于「分析 Swagger」「从 YApi 生成接口测试」「导入 Postman Collection」「扫描后端代码里的接口」「根据 OpenAPI 跑正负向、模糊或状态化测试」「检查接口是否符合契约」以及从 API 定义到可执行结果的端到端任务。
---

# API 契约测试

把一次用户请求视为一个完整任务。按需完成检查、导入、测试选择、执行和结果总结，不向用户暴露内部模块交接。

## 核心原则

不得静默丢弃来源语义。OpenAPI/Swagger 必须保留全部字段和原版本；YApi/Postman 只要有损，就必须先写入 `source-manifest.json`，再生成或执行测试。

## 按意图选择路径

不得强迫所有请求经过固定阶段：

- 纯分析：检查来源并报告 operation 清单、保真度和风险。
- 导入：先检查，再写规范化描述和来源 manifest。
- 明确源码扫描：使用源码 adapter，并复核 OpenAPI 骨架。
- 执行现有定义：先确认目标安全，再运行所选模式。
- 端到端：在同一任务中完成导入与执行，再总结规范化结果。

所有路径都必须先识别来源，再写入文件；执行前复核 warning 和 unsupported feature；secret 只放环境变量；配置错误与测试发现必须分开。只有用户要求纯分析时才停在检查阶段。

## 来源处理

识别或转换来源时读取 [source-formats.md](references/source-formats.md)。

写项目文件前先检查：

```bash
python <skill-dir>/scripts/import_api.py inspect <file-or-url>
```

导入文件、原始 spec URL 或 Swagger UI URL：

```bash
python <skill-dir>/scripts/import_api.py import <file-or-url> \
  --output-dir <project>/api-tests
```

通过 YApi Open API 导入项目：

```bash
YAPI_TOKEN=<secret> python <skill-dir>/scripts/import_api.py import \
  --yapi-base-url https://yapi.example.invalid \
  --yapi-project-id 123 \
  --output-dir <project>/api-tests
```

只有用户明确要求扫描代码时才扫描本地后端：

```bash
python <skill-dir>/scripts/import_api.py inspect --code-root <backend-dir>
python <skill-dir>/scripts/import_api.py import --code-root <backend-dir> \
  --output-dir <project>/api-tests
```

需要限制路径时使用 `--code-prefix /api`。不得推断 code root、默认扫描当前仓库、导入应用模块或执行应用代码。普通目录作为位置参数时，不得视为源码扫描请求。

YApi token 必须通过环境变量传入，不得出现在命令、产物、日志或回复中；不得抓取 YApi HTML。

导入产物：

- `openapi.yaml`：原样语义保留的 OpenAPI/Swagger、从 YApi/Postman 规范化的 OpenAPI 3.1，或明确源码扫描产生的待复核 OpenAPI 3.1 路由骨架。
- `source-manifest.json`：来源 hash、格式/版本、保真度、警告、不支持能力和 operation 数量。

YApi/Postman 转换不得标为无损。源码扫描必须标为 `skeleton`，保留 operation 级来源信息，不得发明请求/响应 schema、状态码或认证规则。不支持的脚本只记录警告，不得执行。

## 测试选择与执行

执行测试或处理认证前读取 [execution.md](references/execution.md)。

优先使用 schema 驱动执行：

```bash
python <skill-dir>/scripts/run_api.py <project>/api-tests/openapi.yaml \
  --url <base-url> \
  --mode smoke \
  --output <project>/api-tests/reports/run-result.json
```

模式：

- `smoke`：examples + coverage；用于 PR 反馈和首次接触环境。
- `full`：examples + coverage + fuzzing + stateful；仅用于隔离测试环境。
- `stateful`：只跑 operation chain；可能创建、修改或删除共享数据时必须明确确认。

使用 `--header-env HEADER=ENV_VAR` 注入 secret；缺少环境变量时必须在联网前失败。只有用户需要 Allure 时才使用 `--allure-results <dir>`。

生产环境不得运行生成式负向、fuzzing 或 stateful 测试。环境身份不明时，只做安全检查和导入，然后请求确认目标。

## 项目与结果契约

写项目文件、解释保真度或消费 `run-result.json` 时读取 [contracts.md](references/contracts.md)。

- OpenAPI/Swagger 负责 HTTP surface 和 schema。
- scenario sidecar 可按 `operationId` 增加业务旅程，但不得重复 method、path 或 response schema。
- 环境 profile 只保存非敏感配置。
- 凭证由环境变量或 secret provider 管理。
- JSON 结果是正式数据；JUnit 和 Allure 只是 reporter。

## 失败分类

推荐修改前先分类：

- `source`：输入不可读、格式/版本不支持或文档损坏。
- `conversion`：来源能力无法安全映射到 OpenAPI。
- `configuration`：缺少 base URL、工具、secret 或参数非法。
- `transport`：DNS、TLS、连接或超时。
- `contract`：状态码、content type、header 或 response schema 不匹配。
- `behavior`：业务断言或状态迁移失败。
- `cleanup`：测试状态创建后无法清理。

不得为了让实现通过而改写源契约。展示证据，并说明更可能过期的是契约还是实现。

## 交付检查

- 说明输入类型与版本。
- 说明导入是 `lossless`、`high`、`high-with-losses` 还是源码 `skeleton`。
- 列出警告和不支持能力，不得隐藏空导入或部分导入。
- 列出实际写入文件。
- 说明是否真的执行了网络测试以及非敏感 base URL。
- 说明模式、结果路径、pass/fail/error 状态和可行动失败类别。
- 说明有意未执行的活动。
