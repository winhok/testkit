# 目标格式说明

## Postman

使用 Postman 维护的 `openapi-to-postmanv2` 转换器处理 OpenAPI 3.0/3.1 和 Swagger 2.0。优先按 tag 建目录，并使用文档中的 example 生成请求值。OpenAPI 始终是正式源；只有用户明确要求保留手写 Collection 内容时才使用 Collection sync。

重点复核：

- OpenAPI schema 约束不会自动变成完整行为测试。
- Collection script、environment 和 secret 无法从 OpenAPI 推导。
- 服务器变量和认证方案通常需要环境值。
- 转换器可能生成示例值，不得把生成值当作已批准测试数据。

交换格式统一使用 Collection v2.1，不得提交当前环境的 secret。

## Apifox

为 Apifox 生成或保留 OpenAPI/Swagger。Apifox 的 OpenAPI 导入能够携带接口、模型和环境，比绕经 Postman 更完整。

不得声称 OpenAPI 能生成 Apifox 原生测试用例或测试套件。导入前预览结果并明确选择重复项处理方式。只有迁移现有 Postman Collection、且请求组织比 schema 保真更重要时，才走 Collection v2.1。

## JMeter

将 JMX 视为待复核脚本骨架：

- 默认将请求放入一个场景线程组；只有负载模型明确要求独立用户群时才拆分。
- 使用 JMeter property 参数化线程数、ramp time 和循环次数。
- 压测时不启用 GUI listener，使用 CLI 输出 JTL。
- 共用服务器值放入 HTTP Defaults 或变量。
- 大量数据或每用户唯一数据使用 CSV Data Set Config。
- 只添加用于识别无效 sample 的低成本断言。
- 明确建模 pacing、到达率/吞吐、请求占比、关联、setup 和 cleanup。

不得从 OpenAPI 推断流量比例。负载模型和动态数据流未复核前，不得称为真实压测方案。

## 跨目标规则

- 所有目标必须来自同一份已复核源版本。
- 在 `artifact-manifest.json` 保存源 SHA-256 和 operation 数量。
- 优先重新生成，不直接手改派生产物。
- 手写行为放在 sidecar 或工具原生文件中，并明确所有权。
- 不支持或有损能力必须显式报告，不得静默丢弃。
