---
name: perfspec-generate
license: MIT
description: 根据已确认性能计划生成或适配 JMeter JMX、Locust Python、k6 JavaScript 原生测试资产，按需准备数据和清理脚本，并记录源契约与生成差异。用户要性能脚本或改造已有压测脚本时使用；仅 OpenAPI 转 JMX 使用 generate-api-artifacts，本阶段不执行脚本或造数请求。
---

# PerfSpec：测试资产

基于计划制作原生资产，不运行压测、不实际写库或调用造数 API。

读取 [计划契约](../_perfspec-shared/references/plan-contract.md) 和 [生命周期](../_perfspec-shared/references/lifecycle.md)。只读取选中工具的 [JMeter](../_perfspec-shared/references/jmeter.md)、[Locust](../_perfspec-shared/references/locust.md) 或 [k6](../_perfspec-shared/references/k6.md) 参考。

## 生成或适配

1. 核对 plan 的 ready 状态与当前源内容。已有 JMX/locustfile/k6 脚本先检查业务逻辑、负载、鉴权和副作用；保留用户修改，优先做最小适配。
2. 将每条场景、请求、业务完成 oracle、提取变量和性能阈值映射到原生脚本。缺少响应状态、关联字段或认证方式时报告 blocker，不默认 200，不降级为无鉴权，不删除难以生成的场景。
3. 保留来源身份：已复核 OpenAPI 管请求结构，已确认业务规则管成功条件，plan 管负载和 SLA。OpenAPI 推导出的脚本骨架不能自动称为完整旅程。
4. 分离环境参数与秘密；token/password 使用环境或受控秘密注入，不进入资产、manifest、CSV、命令记录或证据。脚本不访问未授权主机；重定向和第三方依赖需纳入目标范围。
5. 对 CSV/数据集明确分配粒度、跨 worker 唯一性、复用、耗尽行为和 encoding。按需生成造数与清理资产，限定本次可识别实体；仅生成不表示数据已创建。
6. 编写可复核的请求与变量流、负载映射、使用方式、依赖和人工补齐项。官方工具接口随版本变化时查询对应版本文档，不杜撰 API 或插件。
7. 做与任务相称的静态校验。JMX XML 可解析不证明 JMeter 能正确加载；Python 语法通过不证明 Locust 能运行；涉及 import、初始化或外部请求的验证移交 run。

## 产物

在 `perfspec/<spec-id>/assets/<runner>/` 写原生脚本及所需数据准备/清理资产；写 `asset-manifest.json`：

- schema_version、spec_id、plan_sha256、runner、预期版本；
- 输入 sources 与输出 files 的相对路径和 SHA-256；
- 场景/步骤 ID 到原生 selector/label 的映射；
- 数据集与依赖、unsupported_features、warnings、validation（具体检查及实际结果）。

生成新文件或经授权修改已有资产；不覆盖已有运行和报告。
脚本中的运行参数要与 plan 一致。smoke 的缩减负载作为独立 profile 记录，不能覆盖正式 profile。
仅 OpenAPI 工具导出沿用 `generate-api-artifacts`；本阶段不改变它的只生成职责。

## 交付

列实际生成资产、静态验证结果、差异和未验证项。运行命令是交接说明，实际执行交给 `perfspec-run`；无通用编译器时由宿主 agent 编写/适配原生文件，不宣称已存在自动跨工具转换器。
