---
name: apitestspec-composer
description: 将接口文档、OpenAPI、Markdown 接口说明、请求/响应示例转换成可执行的框架原生 API spec（YAML/JSON），并按需导出 Excel/CSV。只要用户的主要输入是 API 文档并且目标是生成可执行 case 或场景规格，都应优先使用这个 skill。当用户说"根据接口文档生成测试用例""先出一版可执行 spec""把这份 OpenAPI 转成 case"时务必使用。即使用户同时提到后续的 flow 配置或执行，当前阶段仍应先由本技能产出原生 spec 再交接。
---

# API Spec Composer

把接口文档转换成框架原生 API spec，默认产出 `YAML`，必要时再导出 `JSON`、`Excel` 或 `CSV`。

## One-line Purpose

当前阶段只负责把“接口说明”变成“可执行 spec”。

## Use This When

- 用户主要提供的是 OpenAPI、Markdown、接口表格整理稿、示例请求响应、截图转文字后的接口说明
- 用户要的是原生 `YAML` / `JSON` 规格，或先产出原生规格再导出 Excel / CSV
- 用户说“根据接口文档生成测试用例”“先出一版可执行 spec”“把这份 OpenAPI 转成 case”
- 用户一句话里同时提到“接进框架并跑一下”，但当前还没有原生 spec

## Do Not Use This When

- 用户主要输入是后端源码，目标是先盘点接口面。这属于 `apitestspec-surface-scan`
- 输入只是普通文档、README、接入说明、流程说明，而不是 API 接口文档。这不属于本技能
- 用户主要问题是登录、token、tenant、默认 headers、`project.yaml`、`flows/*.yaml`。这属于 `apitestspec-flow-configurator`
- 用户已经有可执行 spec，当前目标是运行、看 pass/fail、排查失败。这属于 `apitestspec-scenario-runner`
- 用户已经有 `allure-results` 或报告产物，当前目标是看报告。这属于 `apitestspec-result-viewer`

## Hand Off To

- 需要从源码先扫接口面：`apitestspec-surface-scan`
- spec 依赖登录流、token 注入、租户切换、默认 headers：`apitestspec-flow-configurator`
- spec 已可执行，下一步要真正跑：`apitestspec-scenario-runner`

## Suite Routing Snapshot

详见 [套件路由表](../apitestspec-shared/references/routing.md)。本 skill 对应阶段 2（有接口文档，但没有原生 spec）。如果用户一次提多个阶段，仍然先完成本阶段再交接。
## Agent Goal

目标不是写一份“测试建议”，而是把接口说明落成真正可执行的原生 spec，并控制边界，不把本 skill 扩展成 flow 配置或执行。

## Decision Matrix

### 输入材料

- 文档类输入：进入本 skill
- 源码类输入：优先转 `apitestspec-surface-scan`
- 已有 spec：通常不留在本 skill

### 允许动作

- 允许写 `docs/*.yaml`、`docs/*.json`
- 允许在用户明确要求时导出 `Excel` / `CSV`
- 不允许执行测试
- 不允许顺手写 `project.yaml` 或 `flows/*.yaml`

### 完成标志

- 原生 spec 已真实落盘
- 如用户要求，兼容格式也已导出
- 明确指出 spec 是否依赖后续 flow 配置

## Preferred Tools And Scripts

当用户需要先落一个最小 case 骨架时，优先使用：

```bash
python skills/apitestspec-composer/scripts/bootstrap_spec.py \
  --output-dir <dir> \
  --case-id <case-id> \
  --case-name <case-name>
```

脚本只产出 `cases/*.yaml`。`project.yaml`、`flows/*.yaml`、`config/.env.example` 属于 `apitestspec-flow-configurator` 阶段，不在此处生成。

导出表格只在原生 spec 已存在且用户明确要求时执行：

```bash
python skills/apitestspec-composer/scripts/doc_to_excel.py -i <spec-path> -o <excel-path>
python skills/apitestspec-composer/scripts/doc_to_csv.py -i <spec-path> -o <csv-path>
```

## Execution Workflow

1. 先确认输入材料和输出目标。
   - 文档、OpenAPI、接口说明、示例请求/响应：继续
   - 只有源码、没有文档：转 `apitestspec-surface-scan`
2. 先产出原生 spec。
   - 默认输出 `YAML`
   - 用户明确要求时才输出 `JSON`
3. 为每个接口设计最小但有覆盖度的 case。
   - 至少覆盖成功路径
   - 补关键失败路径，如缺参、鉴权失败、资源不存在、唯一性冲突
   - 不为凑数量堆重复 case
4. 用户明确要表格时，再从原生 spec 导出 `Excel` / `CSV`
5. 最后判断下一跳。
   - 如果存在登录、token、tenant 等前置依赖，交接给 `apitestspec-flow-configurator`
   - 如果已经可执行，交接给 `apitestspec-scenario-runner`

## Auto-Detect Before Asking

- 自动判断用户是否要原生 spec 还是兼容表格
- 自动推断默认输出目录，优先 `docs/`
- 自动识别文档中的鉴权、登录、tenant、前置依赖信号
- 自动识别高价值失败路径，不默认穷举边界

## When To Stop Guessing

- 缺少请求方法、路径、关键 body 字段时，不要凭空编接口
- 响应结构不明确时，只校验能稳定判断的字段
- 用户没有给足材料时，明确列出缺口，不把 flow、环境变量、执行问题硬塞进当前阶段

## Generation Rules

### 原生规格优先

- 优先写 `YAML`，除非用户明确要求 `JSON`
- 先生成原生规格文件，再决定是否导出表格
- 表格是兼容产物，不是主编辑格式

### 示例值必须具体

- 路径参数、query、body 一律写具体字面量
- 不要使用 `__RANDOM__`、`__RANDOM_INT__`、`__DEP:依赖名:字段名__` 之类占位符
- 需要唯一示例值时，使用稳定示例，如 `user001`、`test@demo.com`、`1`

### 预期响应校验

YAML/JSON 原生 spec 和 Excel/CSV 兼容表格使用不同的校验格式。产出时必须根据目标格式选择正确写法。

#### YAML/JSON 原生格式（结构化 validate 列表）

产出 `cases/*.yaml` 或 `cases/*.json` 时使用：

```yaml
validate:
  - eq: [status_code, 200]
  - exists: $.data.token
  - gte: [$.data.total, 0]
```

支持运算符：`eq`、`ne`、`gt`、`gte`、`lt`、`lte`、`contains`、`exists`。详见 [spec-format.md](../apitestspec-shared/references/spec-format.md) 的断言运算符表。

#### Excel/CSV 表达式格式（`预期响应校验` 列）

导出 Excel/CSV 时，`预期响应校验` 列使用字符串表达式：

- 支持运算符：`==`、`!=`、`>`、`>=`、`<`、`<=`、`contains`
- 多条件 AND 使用 `&&`
- 无运算符时表示字段存在且为真
- 字符串右值优先写裸值，不必额外包引号

推荐写法：

- `$.code==200 && $.data.token && $.data.userId`
- `$.code==200 && $.data.list && $.data.total>=0`
- `$.code==404`
- `$.data.username==user001`

不推荐写法：

- `$.data.username=="user001"`

框架的 loader 会自动将表达式格式解析为结构化 validate 列表，两种格式可互转。

### 常见校验模板

以下同时展示两种格式，按当前产出目标选用：

| 场景 | YAML validate | Excel 表达式 |
|------|---------------|-------------|
| 登录成功 | `eq: [status_code, 200]` + `exists: $.data.token` | `$.code==200 && $.data.token && $.data.userId` |
| 登录失败 | `eq: [status_code, 400]` | `$.code==400` |
| 列表查询 | `eq: [status_code, 200]` + `gte: [$.data.total, 0]` | `$.code==200 && $.data.list && $.data.total>=0` |
| 详情 | `eq: [status_code, 200]` + `eq: [$.data.id, 1]` | `$.code==200 && $.data.id==1` |
| 创建 | `eq: [status_code, 200]` + `exists: $.data.id` | `$.code==200 && $.data.id && $.data.username==user001` |
| 删除 | `eq: [status_code, 200]` | `$.code==200` |

每条 case 的校验尽量控制在 1 到 3 个子条件内，保证易读、易维护，也便于 runner 定位失败原因。

## Output Contract

回答时必须说明：

- 写入了哪个原生规格文件
- 是否额外导出了 Excel / CSV
- 如果没有导出表格，要明确说“当前仅生成原生规格”
- 哪些 case 明显依赖登录流、token 注入或其他前置步骤
- 当前没有做什么：不执行测试、不改 flow、不改 `project.yaml`
- 下一步应交给哪个 skill

## Resources

- Spec 格式参考：[../apitestspec-shared/references/spec-format.md](../apitestspec-shared/references/spec-format.md)
- 完整示例项目：[../apitestspec-shared/references/example-project.md](../apitestspec-shared/references/example-project.md)
- Excel 导出脚本：[scripts/doc_to_excel.py](scripts/doc_to_excel.py)
- CSV 导出脚本：[scripts/doc_to_csv.py](scripts/doc_to_csv.py)
