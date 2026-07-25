# 可观察代码证据提取

## 目标

只提取明确授权范围内、产品可见的实现证据。不得从架构、命名或注释推导产品意图。

## 证据顺序

1. 用户可见路由、菜单、页面、命令和公开入口
2. 运行时权限检查和强制校验
3. 状态转换和持久化的可观察结果
4. 错误处理、重试、回滚和可见消息
5. 授权组件与外部参与者之间的接口
6. 注释与命名，只作低置信度 discovery hint

## 检查内容

| 信号 | 可观察证据 |
|---|---|
| route 和菜单 | 可达入口、角色可见性、导航 |
| controller/handler | 接受的动作和响应分支 |
| form 和 schema | 字段、必填性、限制、枚举标签 |
| 列表和搜索 | 列、筛选、排序、分页、空态 |
| 动作控件 | 确认、加载状态、防重复提交 |
| permission guard | 强制执行的角色/动作边界 |
| 状态逻辑 | 允许的转换和结果状态 |
| 错误分支 | 可见失败、恢复、重试、回滚 |
| feature flag | 条件可用性；绝不能假设已启用 |
| 测试 | 只能作支持证据；测试名称不是运行时行为 |

框架特定文件名只是 discovery hint，不是封闭清单。优先使用 `rg` 和仓库原生导航，避免扫描生成产物、依赖、缓存、fixture 或 vendored code。只有授权范围实际使用对应框架时才加载 `framework-locators.md`。

## 产品语言

技术 locator 放在 `evidence` 中；finding 使用可观察产品行为表述：

| 技术信号 | Finding 表述 |
|---|---|
| route 或 handler | 可达页面、命令或用户动作 |
| API/数据库字段 | 可见字段含义 |
| 原始枚举值 | 展示状态标签和允许的转换 |
| exception/status code | 可见失败与恢复行为 |
| 函数调用 | 动作与可观察结果 |

除非本身就是公开契约，否则不得把类名、API、原始枚举值、框架术语或数据库细节复制到 `intended_behavior` / `observed_behavior`。展示标签与原始值分开保存。

## 证据记录

每条正向观察记录：

- 仓库相对 `path`
- 稳定的 `symbol`，或 `route-config` 等 locator
- 可用时记录准确 `lines`
- 一条产品可见的 `observation`

使用足以支撑陈述的最小证据范围。`end-to-end` 优先覆盖可达入口、enforcement、状态影响、feedback/recovery 和外部参与者边界中的至少两层。`enforcement-layer` 需说明引用位置为何是 canonical enforcement point。

## 置信度

- `high`：在授权运行时路径中直接强制或可观察
- `medium`：多个代码信号支持，但未完全连通
- `low`：从命名、注释、部分层、flag 或不可达路径推断

低置信度证据不能单独支持 `aligned`。应使用 `unknown` 或补充证据。

## 覆盖门槛

为 finding 分配一个 `evidence_coverage`：

- `end-to-end`：授权范围从可达入口连接到可观察结果
- `enforcement-layer`：检查到的 guard、validator、状态机或 handler 本身就是 canonical enforcement point
- `scoped-search`：为 `prd-only` 搜索过的授权位置
- `partial`：孤立函数、单层、未证明调用方、依赖 flag 的路径或不完整链路

只有 `end-to-end` 或 `enforcement-layer` 能支持 `aligned` / `conflict`。单独的导出函数、方法名、save/queue 调用、route 声明或测试预期都保持 `partial`，除非已证明可达性和效果。

## 缺失规则

未找到行为不等于证明行为不存在。使用 `prd-only` 前：

1. 记录全部搜索范围
2. 若入口和 enforcement layer 均获授权，则都检查
3. 记录排除的仓库或组件
4. 不得超出授权快照范围下结论

## 冲突规则

严格区分：

- `intended`：当前 REQ/AC 或已确认产品答复
- `observed`：有直接证据支持的行为
- `inferred`：缺少完整证据的合理解释
- `unknown`：未解决的缺口或矛盾

前后端不一致时，记录双方证据并归为 `unknown` 或 `conflict`，不得选择更方便的一层。

行为受 feature flag、租户配置、环境或分支控制时，在 observation 中包含该条件。不得把单一配置推广到所有用户。

## 触发产品问题的情况

出现以下情况时登记稳定产品问题，不要猜测：

- 状态没有可观察的进入或退出路径
- 前端可见性与后端 enforcement 不一致
- 字段标签或业务含义模糊
- 授权范围内看不到外部系统结果
- feature flag 或环境条件未知
- Diff 只包含可观察路径的一部分
- canonical intent 与实现展示不同标签或结果

## 排除项

不得提取为产品事实：

- 死代码或不可达代码
- 注释掉的行为
- TODO 文本
- 仅 mock/fixture 中存在的行为
- 缺少运行时支撑的测试预期
- 范围外的依赖或生成代码行为
- 没有可观察契约的数据库或内部实现细节
