# API Spec 格式参考

## 项目配置 project.yaml

```yaml
project:
  name: my-project
  base_url: ${ENV.BASE_URL}
  vars: {}
  defaults:
    headers:
      Content-Type: application/json
  report:
    allure_results_dir: allure-results
    structured_results_file: reports/results.json
    cases_dir: cases
    flows_dir: flows
```

## Flow 配置 flows/*.yaml

```yaml
flows:
  user_auth_flow:
    steps:
      - name: login
        request:
          method: POST
          url: /auth/login
          json:
            username: ${ENV.TEST_USER}
            password: ${ENV.TEST_PASS}
        extract:
          token: $.data.token
          user_id: $.data.user.id
        validate:
          - eq: [status_code, 200]
          - exists: $.data.token
```

## 用例文件 cases/*.yaml

```yaml
cases:
  - id: user_crud_happy_path
    name: user crud happy path
    tags: [smoke, crud]
    on_failure: stop          # stop | continue
    setup:
      - use: flow:user_auth_flow
    steps:
      - name: create_user
        request:
          method: POST
          url: /api/v1/users
          headers:
            Authorization: Bearer ${vars.token}
          json:
            username: user001
            email: user001@example.com
        extract:
          created_user_id: $.data.id
        validate:
          - eq: [status_code, 200]
          - exists: $.data.id
      - name: get_user
        request:
          method: GET
          url: /api/v1/users/${vars.created_user_id}
          headers:
            Authorization: Bearer ${vars.token}
        validate:
          - eq: [status_code, 200]
    teardown: []
```

## 数据模型

### StepSpec

| 字段 | 类型 | 说明 |
|------|------|------|
| name | str? | 步骤名，也是 step_outputs 的键 |
| use | str? | 引用 flow，格式 `flow:<name>` |
| inputs | dict? | 传入 flow 的变量 |
| save_as | str? | 响应别名 |
| request | dict? | HTTP 请求（method, url, headers, json, params, data, timeout） |
| extract | dict[str,str]? | JSONPath 提取，如 `token: $.data.token` |
| validate | list[dict]? | 断言列表 |
| sleep | number? | 等待秒数 |

`request` 和 `use` 二选一，不能同时存在。`sleep` 可独立使用（无 request/use），也可与 request 搭配（先等待再请求）。

### CaseSpec

| 字段 | 类型 | 说明 |
|------|------|------|
| id | str | 唯一标识 |
| name | str | 用例名称 |
| tags | list[str] | 标签，用于过滤 |
| on_failure | "stop"\|"continue" | 失败后行为 |
| setup | list[StepSpec] | 前置步骤 |
| steps | list[StepSpec] | 主步骤 |
| teardown | list[StepSpec] | 清理步骤 |

### FlowSpec

| 字段 | 类型 | 说明 |
|------|------|------|
| name | str | flow 名称 |
| steps | list[StepSpec] | flow 步骤列表 |

### ProjectSpec

| 字段 | 类型 | 说明 |
|------|------|------|
| name | str | 项目名 |
| base_url | str | API 基础 URL，支持 `${ENV.BASE_URL}` |
| vars | dict | 项目级变量 |
| defaults | dict | 默认请求配置（如 headers） |
| report | dict | 报告配置（allure_results_dir, structured_results_file 等） |

## 模板语法

YAML 中 `${...}` 占位符在执行时动态替换：

| 前缀 | 说明 | 示例 |
|------|------|------|
| `ENV.` | 环境变量 | `${ENV.BASE_URL}` |
| `vars.` | 运行时变量（extract 提取的值） | `${vars.token}` |
| `project.` | ProjectSpec.vars 的值 | `${project.api_version}` |
| `steps.` | 已执行步骤的响应 | `${steps.login.json.data.token}` |

嵌套访问用点号：`${steps.create_user.json.data.id}`

## 断言运算符

validate 列表中每个条目支持：

| 运算符 | 格式 | 说明 |
|--------|------|------|
| eq | `{eq: [field, expected]}` | 等于 |
| ne | `{ne: [field, expected]}` | 不等于 |
| gt | `{gt: [field, expected]}` | 大于 |
| gte | `{gte: [field, expected]}` | 大于等于 |
| lt | `{lt: [field, expected]}` | 小于 |
| lte | `{lte: [field, expected]}` | 小于等于 |
| contains | `{contains: [field, substr]}` | 包含子串 |
| exists | `{exists: "$.path"}` | 字段存在且非 null |

field 支持 `status_code` 或 `$.` 开头的 JSONPath。

## JSONPath 提取

简化的 JSONPath，仅支持点号嵌套：

- `$.data.token` → `response["json"]["data"]["token"]`
- `$.data.user.id` → `response["json"]["data"]["user"]["id"]`

## Excel/CSV 列定义

导出兼容格式时使用的列。同一 case 的多行共享相同 `用例ID`，回读时按此列聚合为多步骤 case。

| 列名 | 说明 |
|------|------|
| 用例ID | 原始 case id，同 case 所有行一致 |
| 用例名称 | `case_name / step_name`，回读时 ` / ` 左侧为 case 名，右侧为步骤名 |
| 接口路径 | request.url，flow-only 行为空 |
| 路径参数 | 路径变量 |
| 请求方法 | GET/POST/PUT/DELETE 等，flow-only 行为空 |
| 请求体/参数 | request.json（JSON 字符串）或 request.raw_body |
| 预期状态码 | 从 validate 中提取的 status_code 期望值 |
| 预期响应校验 | 复合表达式，如 `$.code==200 && $.data.token`，支持 `==` `!=` `>` `>=` `<` `<=` `contains` 和裸 JSONPath（exists），`&&` 连接多条件 |
| 优先级 | P0-P3 |
| 前置依赖 | flow 引用，如 `flow:user_auth_flow`；有值且接口路径为空时回读为 `use` 步骤 |
| 依赖产出提取 | extract 表达式，格式 `key=$.path ; key2=$.path2`，分号分隔 |
| 注入方式 | 阶段标记：`setup` / `teardown` / 空值（= steps），回读时据此还原 case 的三阶段结构 |
| 是否运行 | 是/否 |
| 运行结果 | pass/fail |

## 执行流程

1. 加载 project.yaml → ProjectSpec
2. 发现 flows/ 目录 → dict[str, FlowSpec]
3. 加载 case 文件 → CaseDocument (cases + flows)
4. 对每个 CaseSpec：
   a. 构建 RuntimeContext (env + project_vars)
   b. 执行 setup 步骤
   c. 执行 steps 步骤（遇到 `use: flow:xxx` 调用 flow）
   d. 执行 teardown 步骤（无论成败）
   e. 每步：渲染模板 → 发 HTTP → 提取变量 → 执行断言
5. 汇总结果写入 JSON
