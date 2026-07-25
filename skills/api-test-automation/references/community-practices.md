# 社区 / 官方实践参考

验证日期：2026-07-25

本文只整理一类组合方式：用 OpenAPI 负责接口契约，用确定性多步骤工作流覆盖登录 / preflight / cleanup 等业务路径，再用 Schemathesis 负责 examples / coverage / fuzzing / stateful property-based 验证。来源仅限官方规范、官方文档或官方仓库文档页。

## 结论先行

- 最稳妥的组合是：`OpenAPI + Arazzo(描述流程) + Schemathesis(契约/生成式执行) + 一个声明式 scenario runner(优先 Hurl，其次 Tavern；Karate / Postman 只在团队已接受脚本式运行时时使用)`。
- 如果目标是“不要任意脚本执行”，不要把登录链路、token 提取、跨步骤变量和 cleanup 藏进 Postman / Karate 的 JavaScript。把流程结构放进 Arazzo 或 repo 自己的声明式 sidecar，执行器只消费显式步骤和显式提取规则。
- Schemathesis 适合做 schema 驱动的广覆盖与状态链探索；它不是最适合承载复杂登录旅程的唯一运行时。官方文档明确把认证流、数据初始化、cleanup 这类能力放在 state machine 自定义、auth 类、fixtures / hooks 扩展点上，而不是纯 OpenAPI 本体里。

## 1. 工作流建模：Arazzo 负责“顺序与依赖”

- Arazzo 1.1.0 的目标就是表达“调用序列及其依赖关系”，并要求文档至少有一个 `workflow`。
  来源：
  <https://spec.openapis.org/arazzo/latest.html>
- Arazzo `components` 可以复用 `inputs`、`parameters`、`successActions`、`failureActions`；失败动作可带 `retryAfter`、`retryLimit`，还可引用另一个 `workflowId`。
  来源：
  <https://spec.openapis.org/arazzo/latest.html>

适合落到本技能 sidecar 的字段实践：

- 登录前置：放在 workflow 的前几个步骤，不要写成隐藏脚本。
- 响应提取：把“从哪个响应字段 / header 提取什么”写成显式输出映射。
- 成功 / 失败分支：把 401 刷新 token、503 retry、最终 cleanup 写成显式 action。
- 共享输入：把 base URL 以外的业务输入放成 workflow inputs，而不是散落在脚本变量里。

约束说明：

- Arazzo 是工作流描述规范。根据规范文本本身，它定义的是可读可机读的 workflow 描述；具体执行器仍需另选。这是基于规范职责的工程推论，不是额外能力声明。

## 2. Schema 覆盖：Schemathesis 负责 examples / coverage / fuzzing / stateful

- Schemathesis CLI 官方支持 phases：`examples`、`coverage`、`fuzzing`、`stateful`。
  来源：
  <https://schemathesis.readthedocs.io/en/stable/reference/cli/>
- 官方 stateful 指南明确：OpenAPI 关系可来自自动分析、`Location` header 推断、或手工 OpenAPI links；如果没有 producer / links，stateful phase 就没有可执行链路。
  来源：
  <https://schemathesis.readthedocs.io/en/stable/guides/stateful-testing/>
- 官方还给出标准定制入口：`setup()`、`teardown()`、`before_call()`、`after_call()`，用于每个 scenario 的初始化、收尾和逐请求改写。
  来源：
  <https://schemathesis.readthedocs.io/en/stable/guides/stateful-testing/>
- 认证有两条官方路径：直接传 `auth=` / `headers=`，或注册 `@schema.auth()` 自定义认证类；持久 session 走 `requests.Session()`。
  来源：
  <https://schemathesis.readthedocs.io/en/stable/guides/auth/>
- 扩展点官方定位也很明确：hooks、自定义 checks、数据生成策略用于“真实测试数据”“业务规则”“请求改写”等。
  来源：
  <https://schemathesis.readthedocs.io/en/stable/guides/extending/>

实践建议：

- 把确定性登录 / preflight / cleanup 放在 scenario 层。
- 把契约覆盖、负向数据、随机边界、stateful 链探索留给 Schemathesis。
- 对需要真实主数据的接口，不要硬靠随机 path 参数；用 hooks 或 setup 注入真实 ID。
- 对 OpenAPI 已能表达的 producer-consumer 关系，优先补 `links`，这样 stateful phase 可以复用。

## 3. 登录 / preflight / cleanup：三种成熟做法

### Hurl：最接近“无脚本”

- Hurl 官方支持跨请求 capture，来源可为 status、header、cookie、body、JSONPath、XPath、regex 等；捕获后的变量可在后续请求复用。
  来源：
  <https://hurl.dev/docs/capturing-response.html>
- Hurl 官方模板支持变量注入：`--variable`、`--variables-file`、环境变量 `HURL_VARIABLE_*`，以及 `[Options]` 内定义变量。
  来源：
  <https://hurl.dev/docs/templates.html>
- Hurl secrets 有 `--secret` 和 `--secrets-file`，并会在日志 / 报告中做 redaction。
  来源：
  <https://hurl.dev/docs/manual.html>
- Hurl 官方支持 HTML / JSON / JUnit / TAP 报告。
  来源：
  <https://hurl.dev/docs/running-tests.html>

适用判断：

- 要登录、提 token、串步骤、做 cleanup，但又不想开放任意脚本时，Hurl 是最贴近目标的成熟 runner。

### Tavern：YAML 场景强，但扩展依赖 pytest / Python

- Tavern 官方例子展示了多 stage 登录，响应 `save` 可把 token 从 JSON 保存到后续步骤变量。
  来源：
  <https://tavern.readthedocs.io/en/latest/examples/>
- 官方 basics 文档说明 `save` 可从 body、headers、redirect query params 提取，并支持 JMESPath。
  来源：
  <https://github.com/taverntesting/tavern/blob/master/docs/source/basics.md>
- Tavern 官方首页说明它本质上是 pytest plugin，并可使用 pytest fixtures / hooks 扩展。
  来源：
  <https://tavern.readthedocs.io/en/stable/>

适用判断：

- 团队已经是 Python / pytest 生态时，Tavern 很合适。
- 但它的高级定制天然会下沉到 Python；如果你要求“不要任意脚本执行”，应把 Tavern 用在声明式 stage / save / assert 范围内，而不是把核心流程逻辑做成自定义函数。

### Karate：功能完整，但默认接受 JS / hook / feature 复用

- Karate 官方文档把认证流、测试数据 setup、公共操作复用放到 `call` / `callonce` / `karate.callSingle()`。
  来源：
  <https://docs.karatelabs.io/reusability/calling-features/>
- 官方 hooks 文档给出 `beforeScenario`、`afterScenario`，且 `afterScenario` 在 pass / fail 路径都会执行。
  来源：
  <https://docs.karatelabs.io/advanced/hooks/>
- 官方 data-driven 文档支持 `Scenario Outline`、table、CSV / JSON / YAML 外部数据。
  来源：
  <https://docs.karatelabs.io/reusability/data-driven-tests/>
- 官方 actions 文档明确 `eval` 会执行 JavaScript，并注明“use sparingly”。
  来源：
  <https://docs.karatelabs.io/core-syntax/actions>

适用判断：

- JVM 团队、希望把 API workflow 与断言整合进一个 DSL 时，Karate 很成熟。
- 但如果本项目要坚持“无任意脚本”，Karate 只能作为可选参考，不应成为默认公共 sidecar 语义，因为它把 JS 执行当作一等扩展能力。

## 4. Postman / Newman：适合作为现成资产来源，不适合作为“无脚本”基线

- Newman 官方定位是命令行运行 Postman Collection，适合集成 CI。
  来源：
  <https://learning.postman.com/docs/reference/newman-cli/command-line-integration-with-newman>
- Postman 官方变量体系有 global / collection / environment 等作用域，environment 用于按环境切换。
  来源：
  <https://learning.postman.com/docs/use/send-requests/variables/variables>
- 但 Postman 官方文档也明确：跨请求依赖、变量处理、工作流跳转，依赖 pre-request / post-response JavaScript 与 `pm.execution.setNextRequest()`。
  来源：
  <https://learning.postman.com/docs/tests-and-scripts/write-scripts/pre-request-scripts>
  <https://learning.postman.com/docs/tests-and-scripts/write-scripts/test-scripts>
  <https://learning.postman.com/docs/tests-and-scripts/running-collections/building-workflows>

实践判断：

- 可导入现有 Postman collection，抽取请求样例、环境变量、断言意图。
- 不建议把它当作本技能长期的 scenario truth source；否则“流程逻辑 = JS 脚本”会和当前技能约束冲突。

## 5. 断言、数据驱动、环境与报告的拆分方式

推荐拆法：

- 结构断言、状态码、content type、response schema：交给 Schemathesis checks。
  来源：
  <https://schemathesis.readthedocs.io/en/stable/reference/cli/>
- 业务断言、登录后特定资源可见性、cleanup 成功性：交给 scenario runner。
- 数据驱动批次：
  - Hurl：变量文件 / 环境变量。
    来源：<https://hurl.dev/docs/templates.html>
  - Tavern：include / 变量格式化 / pytest 生态。
    来源：<https://github.com/taverntesting/tavern/blob/master/docs/source/basics.md>
  - Karate：`Scenario Outline`、table、CSV / JSON / YAML。
    来源：<https://docs.karatelabs.io/reusability/data-driven-tests/>
  - Postman：Collection Runner / dataset / environment。
    来源：<https://learning.postman.com/docs/tests-and-scripts/running-collections/intro-to-collection-runs>
- 报告：
  - Schemathesis：`junit`、`vcr`、`har`、`ndjson`，并支持输出脱敏。
    来源：
    <https://schemathesis.readthedocs.io/en/stable/reference/cli/>
    <https://schemathesis.readthedocs.io/en/stable/reference/configuration/>
  - Hurl：HTML / JSON / JUnit / TAP。
    来源：
    <https://hurl.dev/docs/running-tests.html>

## 6. 面向本技能的落地建议

建议默认契约：

1. `openapi.yaml`
   只放 HTTP surface、schema、examples、links。
2. `scenario sidecar`
   只放确定性业务旅程：登录、preflight、显式提取、cleanup、业务断言、可选数据集。
3. `Schemathesis`
   只负责 `smoke/full/stateful` 契约执行，不承接任意业务脚本。

推荐优先级：

1. 用 Arazzo 概念定义 sidecar 结构：workflow、inputs、step outputs、success / failure actions。
2. 若需要现成可执行声明式 runner，优先参考 Hurl 语义。
3. 若团队已深度绑定 pytest，可接受 Tavern，但要限制自定义 Python 扩展的使用面。
4. Karate / Postman / Newman 只作为兼容已有资产或迁移来源，不作为“无脚本默认方案”。

## 7. 一个可复用的判断标准

如果某方案满足以下条件，就适合作为本技能的 workflow sidecar 基线：

- 登录链路能显式建模，不靠隐藏脚本。
- 响应提取规则是声明式的，可审查。
- 跨步骤变量有清晰作用域。
- cleanup 能在失败路径也执行。
- secrets 通过环境或 secrets file 注入，并有官方 redaction 机制。
- 报告能与 CI 对接。
- 与 OpenAPI / Schemathesis 的职责边界清楚，不把 property-based 生成逻辑复制到第二套运行时里。

按这个标准，当前最贴近本技能目标的是：

- 建模层：Arazzo
- 执行层：Hurl 风格声明式 workflow
- 契约覆盖层：Schemathesis
