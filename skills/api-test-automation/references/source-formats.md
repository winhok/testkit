# P0 来源格式

识别、导入或诊断 API 来源时读取本文件。

## 兼容矩阵

| 来源 | 接受输入 | 导入保真度 | 规范输出 |
|---|---|---|---|
| Swagger/OpenAPI 2.0 | JSON/YAML 文件或 URL | `lossless` | 原文档模型 |
| OpenAPI 3.0/3.1/3.2 | JSON/YAML 文件或 URL | `lossless` | 原文档模型 |
| YApi | 原生 JSON 导出或 Open API 项目 | `high` | OpenAPI 3.1 |
| Postman Collection 2.1 | Collection JSON | `high-with-losses` | OpenAPI 3.1 |
| 后端源码 | 仅显式本地 `--code-root` | `skeleton` | OpenAPI 3.1 |

Swagger UI URL 返回的 HTML 不是 API 定义。Importer 可以跟随页面声明的 `/openapi.json`、`/swagger.json`、`/v2/api-docs` 或 `/v3/api-docs`；无法识别定义 URL 时必须失败。

## OpenAPI 与 Swagger

保留解析后的输入对象和原版本。`lossless` 表示没有转换 API 字段或语义版本，不承诺字节级相同；JSON 可能序列化为 YAML，格式和 key 引号可能变化。`source_sha256` 始终基于原始字节。

不得为了统一版本而升级 Swagger 2.0 或 OpenAPI 3.0，因为 body、nullable、security 和 schema 语义可能变化。外部 `$ref` 原样保留，并提示仍需解析。缺少 `paths` 的文档必须拒绝；`operationId` 重复必须警告。

## YApi

识别包含接口 `list` 的分类，以及具有 `path`、`method`、`title` 的直接接口对象。映射：

- `req_params`、`req_query`、`req_headers` → OpenAPI parameter。
- JSON-schema `req_body_other` → request body schema。
- form/file body → URL-encoded 或 multipart schema。
- JSON-schema `res_body` → response schema。
- 分类和 YApi tag → OpenAPI tag。
- 接口 ID → `x-source-yapi-id`。

YApi 常缺少逐响应状态码；缺失时默认 `200`，同时写 warning。Pre-request、post-request 和 test script 视为不支持的可执行行为。

通过 Open API 访问时，用环境变量中的 project token 调用项目/接口 endpoint，不得持久化包含 token 的请求 URL。

## Postman Collection 2.1

递归遍历嵌套目录。映射：

- request name → summary；
- 嵌套目录 → tag；
- 可安全解析的 HTTP(S) origin 或 `baseUrl` → server；
- path variable 和 query → parameter；
- raw JSON/text 与 form body → request body；
- saved response → OpenAPI example。

不得执行或翻译任意 pre-request/test script。脚本、未解析变量 scope、collection/request auth、Authorization/Accept header、GraphQL body 和不支持的 body mode 都写入 `unsupported_features`。

Postman response 只是 example，不是完整 schema；不得从单条保存响应推断 required property。

## Provenance

按实际导入字节计算 SHA-256，并记录格式/版本、无凭证来源位置、保真度、警告、不支持能力和 operation 数量。完整源文档不得写入 `source-manifest.json`，应保留在 API 描述文件中。

## 源码 adapter

只有用户明确要求扫描代码、controller、router 或 endpoint 时才启用。缺少 API 定义时不得自动回退扫描，也不得把普通位置参数目录自动识别为源码。

静态扫描不得导入模块、启动服务、调用构建工具或执行项目代码。支持 Spring MVC/Boot、FastAPI、Flask、Django、Gin、`net/http`、Express、Koa 和 NestJS 中常见的字面量路由。Regex/静态发现只是路由清单，不是恢复后的完整契约：

- 只输出 OpenAPI 3.1 path 和标准 HTTP method。
- 常见 `:id`、`<int:id>` 转成 `{id}`，类型标为未知。
- 使用 `default` response，并明确说明未推断。
- 添加 source file、line、framework 和 heuristic confidence 扩展。
- `ANY` route 不得映射为 `GET`，只记录为不支持。
- 动态路由、DTO schema、middleware auth、跨文件 mount 和运行时组合都记录为不支持。

按排序后的相对路径和文件字节计算 hash。不得跟随 symlink；跳过依赖、生成目录、VCS、cache 和虚拟环境；强制执行文件数与字节上限，更大范围必须显式提高限制。
