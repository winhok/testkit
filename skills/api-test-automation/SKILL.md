---
name: api-test-automation
license: MIT
description: 基于 HTTP API 定义生成并执行自动化测试，支持 Swagger/OpenAPI 2.0、OpenAPI 3.0/3.1/3.2、YApi、Postman Collection 2.1，以及用户明确要求的后端源码静态扫描。适用于「做接口自动化测试」「从 YApi 或 Swagger 生成并运行测试」「导入 Postman Collection」「扫描后端接口」「跑 API smoke」「登录后提取 Token」「串联多接口并传递变量」「执行 setup/cleanup、数据驱动、业务断言、正负向、模糊或状态化测试」「检查接口实现与文档是否一致」以及从接口发现、导入、执行到结果归因的端到端任务。
---

# API 自动化测试

铁律：不得以“契约已导入”代替自动化执行，也不得为追求覆盖率而绕过目标环境、写操作或 secret 安全门禁。

把一次用户请求视为一个完整任务。按需完成接口发现、定义导入、测试选择、自动化执行和结果总结，不向用户暴露内部模块交接。契约驱动是实现手段，不是公开能力边界；自动化能力不得只停留在 schema 检查。

## 核心原则

不得静默丢弃来源语义。OpenAPI/Swagger 必须保留全部字段和原版本；YApi/Postman 只要有损，就必须先写入 `source-manifest.json`，再生成或执行测试。

执行采用双轨：

- Arazzo 1.1 声明式 workflow 覆盖登录、响应提取、跨步骤变量、业务断言、setup、cleanup 和数据驱动。
- Schemathesis 覆盖 examples、coverage、fuzzing 和 stateful property-based 测试。

不要把登录或 cleanup 藏在任意 Python/JavaScript 中。需要理解选型依据时读取 [community-practices.md](references/community-practices.md)。

## 执行清单

- [ ] 1. 识别用户意图、输入格式/版本和目标环境。
- [ ] 2. inspect 来源；需要写入时再 import，已有产物未经 `--force` 不覆盖。
- [ ] 3. 选择确定性 workflow、Schemathesis，或先 workflow 后 schema 的双轨执行。
- [ ] 4. 在首个网络请求前校验 secret、报告路径、operation 引用和写操作确认。
- [ ] 5. 执行所选测试；cleanup 必须覆盖失败路径。
- [ ] 6. 校验脱敏结果和退出状态，再按交付检查总结。

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

除 `import_api.py`、`run_api.py`、`run_workflows.py`、`run_automation.py`、`migrate_legacy_cases.py` 外，其余 `scripts/*.py` 都是这些入口复用的内部模块，不直接作为公共命令调用。

导入产物：

- `openapi.yaml`：原样语义保留的 OpenAPI/Swagger、从 YApi/Postman 规范化的 OpenAPI 3.1，或明确源码扫描产生的待复核 OpenAPI 3.1 路由骨架。
- `source-manifest.json`：来源 hash、格式/版本、保真度、警告、不支持能力和 operation 数量。

YApi/Postman 转换不得标为无损。源码扫描必须标为 `skeleton`，保留 operation 级来源信息，不得发明请求/响应 schema、状态码或认证规则。不支持的脚本只记录警告，不得执行。

## 自动化测试选择与执行

执行测试或处理认证前读取 [execution.md](references/execution.md)。

只做契约广覆盖时使用 Schemathesis：

```bash
python <skill-dir>/scripts/run_api.py <project>/api-tests/openapi.yaml \
  --url <base-url> \
  --mode smoke \
  --output <project>/api-tests/reports/run-result.json
```

模式：

- `smoke`：examples + coverage；未确认写入权限时只选择 GET/HEAD/OPTIONS/TRACE。
- `full`：examples + coverage + fuzzing + stateful；仅用于隔离测试环境。
- `stateful`：只跑 operation chain；可能创建、修改或删除共享数据时必须明确确认。

使用 `--header-env HEADER=ENV_VAR` 注入 secret；缺少环境变量时必须在联网前失败。只有用户需要 Allure 时才使用 `--allure-results <dir>`。

生产环境不得运行生成式负向、fuzzing 或 stateful 测试。环境身份不明时，只做安全检查和导入，然后请求确认目标。

确定性业务旅程使用 Arazzo sidecar：

```bash
python <skill-dir>/scripts/run_workflows.py <project>/api-tests/workflow.yaml \
  --schema <project>/api-tests/openapi.yaml \
  --url <base-url> \
  --workflow authenticatedUser \
  --input username=demo \
  --input-env password=API_PASSWORD \
  --output <project>/api-tests/reports/workflow-result.json
```

用 `--data cases.csv` 或 `--data cases.json` 批量覆盖 workflow inputs；用 `--tag` 或 `--workflow` 选择场景。setup、主步骤和 cleanup 中任何 POST/PUT/PATCH/DELETE 都必须在确认目标后加 `--allow-mutating-target`，workflow 自身不得绕过该门禁。需要 CI 报告时可加 `--junit` 或 `--allure-results`。

登录结果需要继续给 Schemathesis 使用时，执行一体化双轨命令：

```bash
python <skill-dir>/scripts/run_automation.py <project>/api-tests/workflow.yaml \
  --schema <project>/api-tests/openapi.yaml \
  --url <base-url> \
  --preflight-workflow loginAndVerify \
  --input-env username=API_USERNAME \
  --input-env password=API_PASSWORD \
  --schema-header-from-output Authorization=token \
  --header-template 'Authorization=Bearer {value}' \
  --allow-preflight-mutating-target
```

workflow 必须显式声明供 schema 阶段使用的 output。Runner 只通过临时环境变量传递 secret，结束后立即恢复环境；不得把 output 值写进报告。只有确认生成式测试也可写入目标时，才加 `--allow-schema-mutating-target`。

迁移旧版 `project.yaml + flows/ + cases/`：

```bash
python <skill-dir>/scripts/migrate_legacy_cases.py \
  --project <legacy>/project.yaml \
  --schema <project>/api-tests/openapi.yaml \
  --output <project>/api-tests/workflow.yaml \
  --manifest <project>/api-tests/legacy-migration.json
```

迁移支持 YAML、JSON、CSV、XLSX，保留 flow、setup/steps/teardown、标签、环境/项目变量、默认 header、提取和 eq/ne/数值/contains/exists 断言。遇到无法无损表达的旧语义必须以 `conversion` 错误停止，不得写部分 workflow。

面向用户的 CLI 只有 `import_api.py`、`run_api.py`、`run_workflows.py`、`run_automation.py` 和 `migrate_legacy_cases.py`；其余 `scripts/` 文件是内部模块。`agents/`、`evals/` 和 `tests/` 只供维护、评测与回归验证，不作为用户工作流入口。

## 项目与结果契约

写项目文件、解释保真度或消费 `run-result.json` 时读取 [contracts.md](references/contracts.md)。

- OpenAPI/Swagger 负责 HTTP surface 和 schema。
- Arazzo workflow 用唯一 `operationId` 引用 operation，负责确定性业务旅程。
- 环境 profile 只保存非敏感配置。
- 凭证由环境变量或 secret provider 管理。
- JSON 结果是正式数据；JUnit/Allure 只是 reporter。

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

## 禁止的捷径

- 不因发现 OpenAPI 就默认扫描源码或执行接口。
- 不执行 Postman/JavaScript/Python 任意脚本来补登录或断言。
- 不把 secret 放进命令参数、数据集、workflow、报告或回复。
- 不把配置/transport error 记成测试发现，也不把失败的 cleanup 记成通过。
- 不在未确认目标时用 `--force`、写方法、fuzzing 或 stateful 扩大影响面。

## 交付检查

- 说明输入类型与版本。
- 说明导入是 `lossless`、`high`、`high-with-losses` 还是源码 `skeleton`。
- 列出警告和不支持能力，不得隐藏空导入或部分导入。
- 列出实际写入文件。
- 说明是否真的执行了网络测试以及非敏感 base URL。
- 说明模式、结果路径、pass/fail/error 状态和可行动失败类别。
- 说明有意未执行的活动。
