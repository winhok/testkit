# Schema 驱动执行

运行测试、选择预算或处理认证前读取本文件。

## 当前自动化能力

当前运行时支持：

- OpenAPI examples、coverage、正负向生成、fuzzing 和 stateful operation chain；
- Arazzo 1.0/1.1 workflow 的登录、Token/header/body 提取、跨步骤变量和嵌套 flow；
- setup、主步骤、失败路径 cleanup、业务断言、标签与 CSV/JSON 数据驱动；
- 旧版 YAML/JSON/CSV/XLSX case project 的显式迁移；
- workflow output 安全注入 Schemathesis，或通过环境变量注入已有认证态；
- smoke、full、stateful 风险分级；
- 结构化脱敏 JSON、JUnit 和 Allure 结果。

## 运行时

使用 Schemathesis 执行 OpenAPI/Swagger example、coverage、正负向生成、fuzzing、stateful operation chain 和失败缩减。本技能不得再实现一套 property-based generator。

Wrapper 需要 `schemathesis` 或 `st` 可执行文件。缺少工具属于配置错误，未经用户授权不得安装。

## 模式策略

| 模式 | Schemathesis phase | 默认用途 |
|---|---|---|
| `smoke` | examples、coverage | PR、首次运行、共享测试环境 |
| `full` | examples、coverage、fuzzing、stateful | 隔离测试环境 |
| `stateful` | stateful | 定向诊断生产者/消费者链路 |

风险不明时从 `smoke` 开始，不得静默降级用户明确要求的 `full`。

默认 `smoke` 只让 Schemathesis 执行 GET、HEAD、OPTIONS、TRACE。需要覆盖其他方法时必须显式确认 `--allow-mutating-target`；确定性 workflow 与生成式 schema 测试分别确认，避免只因登录 POST 就放开全部生成式写操作。

## 确定性 workflow

Workflow 使用 Arazzo 1.1 文档和本技能的受限扩展：

- 标准 `inputs`、`steps`、`parameters`、`requestBody`、`successCriteria`、`outputs` 和嵌套 `workflowId`；
- JSON Pointer，以及确定性 dot/index JSONPath；
- `x-testkit-setup`、`x-testkit-cleanup`、`x-testkit-tags`；
- 旧版兼容断言 `x-testkit-contains`、`x-testkit-exists`；
- `x-testkit-continue-on-failure`、`x-testkit-aliases` 和有上限的 `x-testkit-delay-ms` 仅由迁移器生成。

不执行任意脚本、`eval`、Postman scripts 或 Python hooks。远程 sourceDescription 必须先导入本地，workflow 只读取 workflow 目录内的一个本地 OpenAPI source，不允许绝对路径、`..`、query、fragment 或经符号链接逃出该目录。cleanup 在主步骤失败或 transport error 后仍执行；cleanup 自身失败会使 workflow 失败。

响应字段缺失、提取失败或业务断言不满足，属于 workflow 失败，不得把这类被测接口问题误报成 runner 崩溃。只有配置、转换或 transport 问题才返回 exit code `2`。

`run_workflows.py` 的退出状态：

- `0`：workflow 全部通过；
- `1`：业务或响应断言失败；
- `2`：配置、转换或 transport error。

所有 CLI 参数、输入、数据集、报告目标和可静态检查的 workflow 引用都应在首个网络请求前校验。

## 认证

通过环境变量传入 secret：

```bash
API_TOKEN=... python scripts/run_api.py openapi.yaml \
  --url https://test.example.invalid \
  --header-env Authorization=API_TOKEN
```

需要 `Bearer` 等前缀时，把完整 header value 放入环境变量。规范化 command、stdout 和 stderr 都必须脱敏。

不得把 Postman script、YApi 导出、保存响应或来源 manifest 中的认证材料复制到命令。

## 环境安全

除非已有反证，否则将 fuzzing 和 stateful 视为有写入风险。必须同时满足：

- 非生产目标；
- 隔离或可丢弃测试数据；
- 已知认证身份与权限；
- 请求量可接受；
- stateful operation 有 cleanup 或 reset 策略。

无法满足时保持 `smoke` 以只读为主。

## 退出状态

- `0`：所选检查全部通过。
- `1`：出现一个或多个测试发现。
- `2`：schema、配置或执行错误。

必须保留 runner exit status，不得把执行错误改写成测试失败，也不得把测试失败改写成成功报告。

## 可选公开 live eval

DummyJSON 只用于只读认证集成 eval，默认离线套件不得运行：

```bash
export DUMMYJSON_USERNAME=emilys
export DUMMYJSON_PASSWORD=emilyspass
python skills/api-test-automation/evals/run_live_eval.py
```

Live eval 用通用 Arazzo runner 验证未认证 `401`、登录、Bearer 认证，再把声明的 token output 安全传给 Schemathesis。返回 `0` 或 `1` 都表示 eval 成功执行，其中 `1` 表示外部目标暴露测试发现；`2` 表示 eval 失败。不得对该共享公共服务执行 full、fuzzing 或 stateful。
