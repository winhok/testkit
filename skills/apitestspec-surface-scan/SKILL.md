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
- 允许追踪 Controller 的 import/引用链，读取仓库中的 DTO、枚举、异常处理器等关联文件来补充接口细节
- 不允许伪造**追踪后仍找不到**的接口细节
- 不允许执行测试
- 不允许直接生成业务 case

### 完成标志

- 接口清单已真实落盘
- 明确扫描范围、输出路径、数量摘要
- 仓库级扫描时，引用解析已完成或已说明哪些引用追踪后仍未解析
- 明确哪些字段无法稳定推断（区分"未追踪"和"追踪后仍未找到"）

## Preferred Tools And Scripts

优先使用内置扫描脚本做第一轮自动发现，再结合 LLM 阅读源码补充细节：

```bash
# 脚本位于本 skill 的 scripts/ 目录下，实际路径取决于安装位置
python <skill-dir>/scripts/scan_endpoints.py <dir> \
  --format md \
  --output docs/api/api-docs.md \
  [--prefix /api/admin,/api/user]
```

脚本通过正则匹配常见框架的路由注解/装饰器，覆盖 Spring、FastAPI、Flask、Django、Gin、net/http、Express、NestJS、Koa。脚本产出是初始骨架，以下场景仍需 LLM 阅读源码补充：

- 嵌套路由、动态注册、条件路由
- Spring 多路径注解（如 `@GetMapping({"/a", "/b"})`），脚本只提取第一个路径
- Flask `@app.route` 的 `methods=[]` 参数，脚本标记为 `ANY`，LLM 可读取参数补充
- Django `path()` / `re_path()` 不携带 HTTP method 信息，脚本统一标记为 `ANY`

## Workspace Scope Detection

在开始扫描之前，先判断工作区范围，因为这决定了能做多深的解析：

| 范围 | 判断依据 | 扫描深度 |
|------|---------|---------|
| **仓库级** | 工作区根目录含 `.git`、`pom.xml`、`go.mod`、`package.json` 等项目标志文件 | Phase 1 + Phase 2（引用解析） |
| **目录级** | 用户指定了一个子目录，但仓库其他部分也可访问 | Phase 1 + Phase 2（在可访问范围内追踪引用） |
| **单文件级** | 用户只提供了一个或几个文件，无法访问仓库其他部分 | 仅 Phase 1，大量字段标注"未知" |

判断方法：检查工作区根目录是否存在项目特征文件，以及 Controller 的 `import` 语句引用的类是否在工作区内能找到对应源文件。如果能找到，说明有仓库级访问能力，应该进入 Phase 2。

## Execution Workflow

### Phase 1 — 端点发现

1. 明确扫描范围。
   - 整个项目 / 指定目录 / 指定 URL 或 URL 前缀
2. 确定输出格式。
   - 用户明确要求 `json` 或 `md` 时按要求输出；未指定时默认 `md`
3. 识别技术栈和后端根目录。
   - 优先从 `backend/`、`server/`、`api/`、`services/` 等目录判断
   - 再结合 `pom.xml`、`build.gradle`、`go.mod`、`package.json`、`requirements.txt` 等特征文件
4. 先用脚本 `scan_endpoints.py` 做第一轮自动发现，产出端点骨架清单。
5. LLM 阅读源码补充脚本无法覆盖的复杂场景（嵌套路由、动态注册、条件路由）。

### Phase 2 — 引用解析（仓库级/目录级时执行）

如果工作区范围是仓库级或目录级，对 Phase 1 发现的每个 Controller/路由文件执行引用追踪：

6. 从 Controller 文件的 import/require 语句出发，定位以下关联文件：
   - **返回类型（VO/DTO）**：读取字段定义、类型、注释，填充 `responses` 和 `requestBody`
   - **响应包装类**（如 `BaseResponse`、`Result<T>`）：确认统一响应结构的字段名和含义
   - **状态码/错误码枚举**（如 `ResponseEnum`、`ErrorCode`）：提取 code-message 对照表
   - **Service 层常量**：如果 Controller 直接引用了 Service 常量（错误信息、业务状态值），追踪提取
   - **全局异常处理器**（如 `@ControllerAdvice`、`@ExceptionHandler`）：理解异常响应结构
   - **认证/鉴权配置**（如 `SecurityConfig`、拦截器、中间件）：推断接口的认证要求
7. 将追踪到的信息合并进 Unified Endpoint Model。
8. 统一整理并落盘。
9. 如果用户下一步要生成 case，交给 `apitestspec-composer`

### 引用追踪策略（按技术栈）

**Java / Spring Boot**
- `import` 语句 → 将包路径转为文件路径搜索（如 `com.foo.dto.UserVO` → `**/UserVO.java`）
- `@ControllerAdvice` 类 → grep `@ControllerAdvice` 或 `@RestControllerAdvice`
- 响应枚举 → grep Controller 中引用的枚举类名
- Security 配置 → grep `WebSecurityConfigurerAdapter`、`SecurityFilterChain`、`@EnableWebSecurity`

**Python / FastAPI / Flask / Django**
- `from ... import` 语句 → 定位 Pydantic model / dataclass / serializer
- 异常处理 → grep `@app.exception_handler`、`MIDDLEWARE`
- 认证 → grep `Depends(...)` 中的认证依赖、`@login_required`

**Go / Gin / net/http**
- handler 函数签名中的 struct 类型 → 搜索 struct 定义
- 中间件 → grep `Use()`、`HandlerFunc` 链

**Node.js / Express / NestJS / Koa**
- `import`/`require` 语句 → 定位 DTO class、interface、type
- NestJS `@UseGuards`、`@UseInterceptors` → 搜索 Guard/Interceptor 定义
- 全局中间件 → grep `app.use`、`APP_FILTER`

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

## Phase 1 Output Example

脚本 `scan_endpoints.py` 产出的初始骨架格式如下：

```markdown
# API Surface Scan

扫描范围: `/path/to/backend`

共发现 **12** 个 HTTP 端点。

## spring (8 endpoints)

| Method | Path | File | Line |
|--------|------|------|------|
| GET | `/api/auth/game-coin-box/list` | `controller/outer/GameCoinTreasureBoxController.java` | 35 |
| GET | `/api/auth/game-coin-box/records` | `controller/outer/GameCoinTreasureBoxController.java` | 52 |
| POST | `/api/auth/game-coin-box/claim/{boxId}` | `controller/outer/GameCoinTreasureBoxController.java` | 78 |

## fastapi (4 endpoints)

| Method | Path | File | Line |
|--------|------|------|------|
| GET | `/api/users/me` | `routers/user.py` | 12 |
| POST | `/api/users/register` | `routers/user.py` | 28 |
```

这是 Phase 1 的原始骨架。LLM 在此基础上：
- 补充 `summary`、`description`、`tags` 等字段（从注释和方法命名推断）
- 进入 Phase 2 追踪引用填充 `requestBody`、`responses` 等详细结构

## When To Stop Guessing

克制规则取决于工作区范围——有仓库访问能力时应该先追踪引用再判断能不能填，而不是一律标"未知"。

### 仓库级/目录级

- 先追踪 import 链查找 DTO、枚举、异常处理器等关联文件
- 追踪后找到源码定义的字段：直接填入，标注来源文件
- 追踪后源文件存在但内容不足以确认的字段：填入推测值并标注 `[推测]`
- 追踪后找不到对应源文件（可能在外部依赖或未提交代码中）：标注"未追踪到源文件"

### 单文件级

- 控制器、路由、DTO 扫不到时，不要硬写请求体和响应结构
- 注释和类型都不完整时，只输出能稳定确认的字段

### 通用

- 不要把非 HTTP 入口误判成 API 路由
- 不要伪造枚举值、状态码、常量——要么从源码中提取，要么标注未知
- 追踪深度建议控制在 3 层以内（Controller → Service → DTO/Enum），避免无限递归

## Reference Resolution Output Example

下面展示同一个接口在"仅 Phase 1"和"Phase 1 + Phase 2"下的输出差异：

**Phase 1（端点发现，单文件级）：**

```markdown
| 字段 | 值 |
|---|---|
| **path** | `/api/auth/game-coin-box/claim/{boxId}` |
| **method** | `POST` |
| **controller** | `GameCoinTreasureBoxController` |

### 响应
结构未知（`BaseResponse<ClaimResultVO>` 的具体字段无法从当前文件推断）。
```

**Phase 1 + Phase 2（引用解析，仓库级）：**

```markdown
| 字段 | 值 |
|---|---|
| **path** | `/api/auth/game-coin-box/claim/{boxId}` |
| **method** | `POST` |
| **controller** | `GameCoinTreasureBoxController` |

### 响应（成功 — 来源：`ClaimResultVO.java`）
| 字段 | 类型 | 说明 |
|---|---|---|
| `boxId` | String | 宝箱 ID |
| `claimedAmount` | BigDecimal | 领取金额 |

### 响应包装（来源：`BaseResponse.java`）
| 字段 | 类型 | 说明 |
|---|---|---|
| `resultCode` | int | 状态码，成功=200 |
| `message` | String | 提示信息 |
| `time` | String | 时间戳 |
| `traceId` | String | 链路追踪 ID |

### 错误码（来源：`ResponseEnum.java`）
| code | message |
|---|---|
| 200 | SUCCESS |
| -1 | FAIL |
| 401 | UNAUTHORIZED |

### 业务异常（来源：`GameCoinTreasureBoxService.java`）
- `NO_GOLD_REWARD_AVAILABLE_MESSAGE` = `"No gold reward available"`
```

关键区别：Phase 2 的每个补充字段都标注了来源文件，方便用户验证和后续维护。

## Output Contract

回答时必须说明：

- 扫描范围
- 工作区范围判定结果（仓库级 / 目录级 / 单文件级）
- 识别到的技术栈或服务目录
- 输出文件路径
- 接口数量或服务数量摘要
- 是否按 URL 前缀或目录做了过滤
- 引用解析情况：追踪了哪些关联文件，解析了哪些字段
- 哪些字段无法可靠推断，以及原因（区分"未追踪"和"追踪后未找到"）
- 当前没有做什么：没有生成 case、没有配 flow、没有执行测试

## Resources

- 扫描脚本：[scripts/scan_endpoints.py](scripts/scan_endpoints.py)
- Spec 格式参考：[../apitestspec-shared/references/spec-format.md](../apitestspec-shared/references/spec-format.md)
