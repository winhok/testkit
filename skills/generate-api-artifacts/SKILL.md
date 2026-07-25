---
name: generate-api-artifacts
description: 将已复核的 OpenAPI 或 Swagger 契约转换为可导入的 API 工具产物，包括 Postman Collection v2.1、Apifox 可导入 OpenAPI 和 Apache JMeter JMX。当用户要求「OpenAPI 转 Postman」「生成 Apifox 导入文件」「把 Swagger 做成 JMeter/JMX」「生成 API 客户端集合」或从同一份接口定义同时导出多个目标格式时使用。
---

# 生成 API 工具产物

将 OpenAPI/Swagger 视为版本化源契约，将 Postman、Apifox 和 JMeter 文件视为可重新生成的派生产物。不得让生成的集合悄悄取代源契约。

## 确认输入

直接输入必须是已复核的 OpenAPI 3.0/3.1 或 Swagger 2.0 文档。

若输入是 curl、Raw HTTP、自然语言或 Markdown，先创建待复核的 OpenAPI 草稿。服务器、schema、状态码、认证规则和示例只要是推断得到的，都必须标为待确认；未知服务器不得默认成 localhost，未知成功状态码不得默认成 200。

## 保持职责单一

本技能只检查 API 定义文件并生成可移植产物，不得：

- 扫描应用源码或从仓库发现路由；
- 执行 API 请求、Postman Collection、JMX、契约测试、模糊测试或压测；
- 自动调用其他技能来获取或测试 API 定义；
- 根据实现代码推断 API 契约。

用户只提供源码或要求源码发现时，说明本技能需要 OpenAPI/Swagger 后停止。用户同时要求转换和执行时，只生成请求的产物，并说明执行不属于本技能。

## 按用途选择目标

生成前按目标读取 [targets.md](references/targets.md)：

- `postman`：用于协作、手动请求、示例和 Collection Runner。
- `apifox`：用于 API 设计和导入；输出已复核的 OpenAPI，不发明私有格式。
- `jmeter`：输出压测脚本骨架；没有负载模型时不得称为生产可用压测方案。
- 多目标：从同一份源契约一次生成，并共用同一份 manifest。

## 先检查再写入

```bash
python <skill-dir>/scripts/generate_artifacts.py inspect <openapi-or-swagger>
```

报告检测到的版本、operation 数量、未解析的服务器变量、缺少 `operationId` 的接口，以及没有明确成功响应的接口。只有用户要求纯分析时才停在检查阶段。

## 生成产物

一次生成一个或多个目标：

```bash
python <skill-dir>/scripts/generate_artifacts.py generate <openapi-or-swagger> \
  --target apifox \
  --target jmeter \
  --output-dir <project>/api-artifacts
```

Postman 使用官方 `openapi2postmanv2` 转换器；脚本不得隐式下载工具：

```bash
python <skill-dir>/scripts/generate_artifacts.py generate openapi.yaml \
  --target postman \
  --output-dir api-artifacts \
  --postman-converter openapi2postmanv2
```

JMeter 使用安全默认值，并允许在运行时覆盖负载参数：

```bash
python <skill-dir>/scripts/generate_artifacts.py generate openapi.yaml \
  --target jmeter \
  --output-dir api-artifacts \
  --base-url https://test.example.invalid \
  --threads 10 \
  --ramp-seconds 30 \
  --loops 1
```

需要时可把下面命令作为交接说明，但本技能不得执行：

```bash
jmeter -n -t api-artifacts/<name>.jmx -l api-artifacts/results.jtl \
  -Jthreads=25 -Jramp_seconds=60 -Jloops=5
```

## 保真与安全

- 不得嵌入 bearer token、Cookie、API key、密码或 client secret。
- 目标格式能够表达时，保留 path、method、参数、请求示例、描述、tag 和已声明响应码。
- 在 `artifact-manifest.json` 中记录目标格式损失和人工复核项。
- 转换时不得执行导入的 Postman pre-request/test script。
- 不得根据响应字段名发明断言。
- 不得发送网络请求或执行生成产物。
- 已有输出不得覆盖；只有用户授权后才能使用 `--force`。

## 复核目标差异

- Postman：检查集合变量、认证占位符、示例、目录分组和转换器警告。
- Apifox：预览导入结果并确认重复项策略。OpenAPI 可携带接口、模型和环境；产品原生测试套件需要另行维护。
- JMeter：检查请求顺序、动态关联、数据唯一性、pacing、吞吐模型、断言、超时和清理逻辑。Sampler 列表不等于负载模型。

## 交付检查

- 说明输入类型、版本、hash 和 operation 数量。
- 说明输入是正式契约还是待复核草稿。
- 列出请求的目标和实际写入文件。
- 汇总 `artifact-manifest.json` 中的警告与人工复核项。
- 说明实际运行了哪些本地格式转换器；不得运行 Collection、JMX 或 API 测试。
- 说明有意未生成或未执行的内容。
