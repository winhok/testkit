# 执行 API 自动化测试

需要把结果关联到测试范围与验收时，使用完整插件中的[执行与证据协议](execution.md)。先冻结 OpenAPI/workflow/pytest manifest 和目标，再运行本页原有命令，最后登记原始结果。原有命令与 result v1 保持不变；独立安装本 Skill 时不依赖新增共享目录。

执行限制：`run_api.py` 默认最多运行 300 秒，可用 `--runner-timeout` 调整；`--runner-output-limit` 默认每个输出流保留 65536 字符，截断会标记，超时写入 error/timeout 结果。runner 输出暂存到临时文件，避免全部积存在 Python 内存；临时磁盘用量仍取决于 runner 输出量与超时。workflow HTTP 响应上限为 20 MiB。

数据驱动的 `--max-runs` 是准入上限；数据行超过上限时会在发请求前报错，不再静默丢弃尾部用例。需要更多行就显式提高上限，需要子集则先生成明确的数据文件。覆盖选项不允许写回输入定义、数据集或遗留用例文件；带凭据的跨来源重定向和 HTTPS 降级会被拒绝。

`api-test-automation` 从接口定义导入开始，执行确定性业务流程和生成式契约测试，并输出脱敏的 JSON、JUnit 或 Allure 结果。它不要求你手动串联多个阶段。

## 选择输入来源

优先使用接口定义。只有你明确要求扫描代码时，TestKit 才读取后端源码。

| 输入 | 支持方式 | 保真度 |
|---|---|---|
| Swagger/OpenAPI 2.0 | JSON、YAML、文件或 URL | 无损 |
| OpenAPI 3.0、3.1、3.2 | JSON、YAML、文件或 URL | 无损 |
| YApi 项目 | JSON 导出或开放 API adapter | 高 |
| Postman Collection 2.1 | Collection adapter | 高，scripts 可能有损 |
| 后端源码 | 显式静态扫描并生成 OpenAPI 骨架 | 需人工复核 |

导入过程生成：

- `openapi.yaml`：归一化后的接口定义
- `source-manifest.json`：来源、hash、保真度、损失项和复核项

## 导入接口定义

导入 OpenAPI 文件或 URL：

```bash
python skills/api-test-automation/scripts/import_api.py import \
  openapi.yaml \
  --output-dir api-tests
```

从 YApi 开放 API 导入项目：

```bash
export YAPI_TOKEN=your_yapi_token_here

python skills/api-test-automation/scripts/import_api.py import \
  --yapi-base-url https://yapi.example.invalid \
  --yapi-project-id 1234567890123 \
  --output-dir api-tests
```

导入 Postman Collection：

```bash
python skills/api-test-automation/scripts/import_api.py import \
  collection.json \
  --output-dir api-tests
```

## 显式扫描后端代码

源码扫描只提取常见框架中的静态路由。它不会执行项目代码，也不会推断完整认证和数据传输对象（DTO）语义。

先检查扫描结果：

```bash
python skills/api-test-automation/scripts/import_api.py inspect \
  --code-root backend
```

确认范围后生成 OpenAPI 骨架：

```bash
python skills/api-test-automation/scripts/import_api.py import \
  --code-root backend \
  --code-prefix /api \
  --output-dir api-tests
```

扫描结果的保真度为 `skeleton`。执行测试前必须人工复核路径、方法、认证和 schema。

## 选择执行轨道

两个轨道解决不同问题：

| 轨道 | 适合验证 |
|---|---|
| [Arazzo workflow](https://spec.openapis.org/arazzo/latest.html) | 登录、跨接口依赖、变量提取、业务断言、数据驱动、setup 和 cleanup |
| [Schemathesis](https://schemathesis.readthedocs.io/en/stable/) | OpenAPI examples、覆盖缺口、负向输入、fuzzing 和状态化行为 |

已有 pytest 接口测试、专有签名或复杂 Python 后置验证走受控兼容入口。pytest 是存量资产和复杂场景的 escape hatch，不替换上述两个默认轨道。

`run_automation.py` 可以先执行登录 workflow，再把捕获的 Token 注入 Schemathesis。

## 执行 schema 测试

对确认的测试环境执行只读 smoke：

```bash
python skills/api-test-automation/scripts/run_api.py \
  api-tests/openapi.yaml \
  --url https://api-test.example.invalid \
  --mode smoke
```

`full` 和 `stateful` 模式可能生成写方法请求。只在隔离环境中确认后启用：

```bash
python skills/api-test-automation/scripts/run_api.py \
  api-tests/openapi.yaml \
  --url https://api-test.example.invalid \
  --mode full \
  --allow-mutating-target
```

## 执行业务 workflow

workflow 可以描述登录、Token 提取、跨步骤参数和清理操作：

```bash
export API_PASSWORD=your_api_password_here

python skills/api-test-automation/scripts/run_workflows.py \
  api-tests/workflow.yaml \
  --schema api-tests/openapi.yaml \
  --url https://api-test.example.invalid \
  --workflow authenticatedUser \
  --input username=demo \
  --input-env password=API_PASSWORD \
  --allow-mutating-target
```

用 `--data cases.csv` 或 `--data cases.json` 执行数据驱动场景。每个顶层 workflow 和数据行使用独立的 Cookie 会话。

## 串联两个执行轨道

先运行登录 workflow，再把输出作为 Schemathesis Header：

```bash
export API_PASSWORD=your_api_password_here

python skills/api-test-automation/scripts/run_automation.py \
  api-tests/workflow.yaml \
  --schema api-tests/openapi.yaml \
  --url https://api-test.example.invalid \
  --preflight-workflow authenticatedUser \
  --input username=demo \
  --input-env password=API_PASSWORD \
  --schema-header-from-output Authorization=token \
  --header-template "Authorization=Bearer {value}" \
  --allow-preflight-mutating-target
```

workflow 输出只在进程内传递。规范化报告不会保存密码、Token 或 workflow output 值。

## 迁移旧版 API 用例

旧版 project、flow 和 YAML、JSON、CSV、XLSX case 可以显式迁移：

```bash
python skills/api-test-automation/scripts/migrate_legacy_cases.py \
  --project legacy/project.yaml \
  --schema api-tests/openapi.yaml \
  --output api-tests/workflow.yaml
```

迁移器会保留可映射的 setup、steps、teardown、变量、提取和断言。`flows_dir` 和 `cases_dir` 必须位于 legacy project 目录内；无法明确映射或超出项目目录的输入会终止迁移，不会静默丢弃。

## 运行已有 pytest 资产

pytest collection 会加载 Python 测试和 `conftest.py`，不是安全静态扫描。必须显式限定项目根目录与 selector：

```bash
python skills/api-test-automation/scripts/pytest_compat.py collect ./service \
  --selector tests/api \
  --output api-tests/pytest-source-manifest.json
```

复核 manifest 后，选择其中的完整 nodeid 执行：

```bash
python skills/api-test-automation/scripts/pytest_compat.py run ./service \
  --manifest api-tests/pytest-source-manifest.json \
  --nodeid 'tests/api/test_users.py::test_get_user[active]' \
  --junit api-tests/reports/pytest-junit.xml \
  --output api-tests/reports/pytest-run-result.json
```

默认禁用第三方 pytest plugin 的安装包自动发现，并忽略环境中的 `PYTEST_ADDOPTS`、`PYTEST_PLUGINS`；项目 `conftest.py` 仍会加载并纳入指纹。源码、`conftest.py`、pytest 配置或 pytest 版本变化会使 manifest 失效；未知 nodeid、零选择、损坏 JUnit 和非测试类退出码都以配置错误关闭。需要脱敏环境值时重复传入 `--secret-env ENV_NAME`。

## 生成持续集成报告

workflow runner 支持以下持续集成（CI）报告：

- JSON：默认规范化结果
- JUnit：使用 `--junit result.xml`
- Allure：使用 `--allure-results fresh-allure-results`

Allure 目录必须为空。`--force` 不会清理或混合已有 Allure 文件。

## 运行公开登录示例

DummyJSON 示例执行“未登录请求、登录、Token 提取、鉴权请求、schema smoke”：

```bash
export DUMMYJSON_USERNAME=emilys
export DUMMYJSON_PASSWORD=emilyspass

python examples/api-test-automation/dummyjson-auth/run_authenticated_demo.py \
  --output /private/tmp/dummyjson-auth-result.json \
  --force
```

该目标是共享公共服务。只运行小规模只读测试，不对其执行 fuzzing 或 stateful 测试。

## 遵守执行边界

执行接口测试前检查以下安全边界：

- 基础 URL 不包含用户名、密码、query 或 fragment
- Secret 只通过环境变量注入
- 未确认目标时不执行 POST、PUT、PATCH 或 DELETE
- 不把源码扫描骨架当成完整接口契约
- workflow 只能读取其所在目录内的本地 OpenAPI source
- 不允许报告覆盖 workflow 或 schema 输入
- 不向 Schemathesis 透传可绕过安全门禁或写入任意报告的参数
- 不把 pytest collection 称为静态扫描，也不执行 manifest 之外的 nodeid

完整输入、执行和结果契约位于 `skills/api-test-automation/references/`。
