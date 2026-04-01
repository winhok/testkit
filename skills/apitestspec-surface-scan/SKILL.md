---
name: apitestspec-surface-scan
description: 扫描后端源码，发现 HTTP API 接口，并将接口清单写成 Markdown 或 JSON 文档。只要用户主要输入是 Java、Go、Python、Node.js 等后端代码，并且目标是盘点接口面、扫描某个模块或服务目录、按 URL 前缀过滤接口、或先根据源码形成一份可读接口清单时，都应优先使用这个 skill。当用户说"扫一下后端接口""盘点 API""从源码里找接口"时务必使用。
---

# API Surface Scan

从后端源码中扫描 HTTP 接口定义，整理成 `Markdown` 或 `JSON` 文档，并真实落盘。

## One-line Purpose

当前阶段只负责从源码盘点接口面。

## Use This When

- 用户主要输入是后端源码，不是接口文档
- 用户要扫整个项目、某个模块、某个服务目录
- 用户要按 URL 或 URL 前缀过滤接口
- 用户要一份 endpoint inventory，后续再决定是否生成测试 spec

## Do Not Use This When

- 用户已经有稳定接口文档并要生成可执行 case。这属于 `apitestspec-composer`
- 用户主要在配登录流、token、环境变量。这属于 `apitestspec-flow-configurator`
- 用户已经有 spec，要直接执行。这属于 `apitestspec-scenario-runner`
- 用户要看已有测试结果或报告。这属于 `apitestspec-result-viewer`

## Hand Off To

- 扫描结果确认后，需要生成可执行 spec：`apitestspec-composer`

## Suite Routing Snapshot

详见 [套件路由表](../apitestspec-shared/references/routing.md)。本 skill 对应阶段 1（没有文档，只有源码）。扫描完成后不直接跳过 spec 阶段。
## Agent Goal

目标是在没有稳定接口文档时，先从代码中自动发现“能测什么”，为后续的 spec 生成提供可靠接口清单。

## Decision Matrix

### 输入材料

- 后端源码：进入本 skill
- OpenAPI / Markdown 接口文档：通常不在本 skill

### 允许动作

- 允许扫描代码并生成 `Markdown` / `JSON`
- 不允许伪造无法从源码稳定确认的接口细节
- 不允许执行测试
- 不允许直接生成业务 case

### 完成标志

- 接口清单已真实落盘
- 明确扫描范围、输出路径、数量摘要
- 明确哪些字段无法稳定推断

## Preferred Tools And Scripts

优先使用内置扫描脚本做第一轮自动发现，再结合 LLM 阅读源码补充细节：

```bash
python skills/apitestspec-surface-scan/scripts/scan_endpoints.py <dir> \
  --format md \
  --output docs/api/api-docs.md \
  [--prefix /api/admin,/api/user]
```

脚本通过正则匹配常见框架的路由注解/装饰器，覆盖 Spring、FastAPI、Flask、Django、Gin、net/http、Express、NestJS、Koa。脚本产出是初始骨架，复杂场景（嵌套路由、动态注册）仍需 LLM 补充。

## Execution Workflow

1. 明确扫描范围。
   - 整个项目
   - 指定目录
   - 指定 URL 或 URL 前缀
2. 确定输出格式。
   - 用户明确要求 `json` 或 `md` 时按要求输出
   - 未指定时默认 `md`
3. 识别技术栈和后端根目录。
   - 优先从 `backend/`、`server/`、`api/`、`services/` 等目录判断
   - 再结合 `pom.xml`、`build.gradle`、`go.mod`、`package.json`、`requirements.txt` 等特征文件
4. 扫描接口定义。
   - Java：Spring MVC / Spring Boot
   - Go：Gin、`net/http`
   - Python：FastAPI、Flask、Django
   - Node.js：Express、NestJS、Koa
5. 统一整理接口模型并落盘。
6. 如果用户下一步要生成 case，交给 `apitestspec-composer`

## Range Parsing Rules

- 用户给目录路径时，只扫描该目录
- 用户说“整个项目”时，优先扫描识别出的后端目录
- 用户给 URL 或 URL 前缀时，先完成扫描，再按 `path` 过滤
- 简单通配可按前缀理解，例如 `/api/admin*`

## Output File Rules

- 必须真实写文件，不要只在对话里展示
- 推荐输出目录：
  - Markdown：`docs/api/`
  - JSON：`docs/api-json/`
- 默认文件名可用：
  - `api-docs.md`
  - `api-docs.json`
  - 若有模块范围，可用 `api-docs-user-service.md`
- 若用户指定文件名，优先使用用户指定名称，并自动补后缀

## Unified Endpoint Model

每个 endpoint 尽量统一到这些信息：

- `service`
- `module`
- `controller`
- `operationId`
- `path`
- `method`
- `summary`
- `description`
- `tags`
- `deprecated`
- `pathParams`
- `queryParams`
- `headerParams`
- `requestBody`
- `responses`

无法可靠推断的字段可以留空或省略，但不要捏造。

## When To Stop Guessing

- 控制器、路由、DTO 扫不到时，不要硬写请求体和响应结构
- 注释和类型都不完整时，只输出能稳定确认的字段
- 不要把非 HTTP 入口误判成 API 路由

## Output Contract

回答时必须说明：

- 扫描范围
- 识别到的技术栈或服务目录
- 输出文件路径
- 接口数量或服务数量摘要
- 是否按 URL 前缀或目录做了过滤
- 哪些字段无法可靠推断，以及原因
- 当前没有做什么：没有生成 case、没有配 flow、没有执行测试

## Resources

- 扫描脚本：[scripts/scan_endpoints.py](scripts/scan_endpoints.py)
- Spec 格式参考：[../apitestspec-shared/references/spec-format.md](../apitestspec-shared/references/spec-format.md)
