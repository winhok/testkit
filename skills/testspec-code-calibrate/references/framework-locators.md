# 框架定位提示

只加载与授权仓库匹配的部分。这些内容仅用于发现候选，不能证明可达性或产品行为。

## 前端

### Vue

- route：`src/router/`、route record、`meta.title`
- 菜单：layout/sidebar 配置
- 字段：form-item 标签、规则、disabled/readonly 条件
- 列表：列、筛选、分页、空态
- 动作：click handler、router 导航、确认弹窗
- 权限：route guard 和权限 directive/composable

### React

- route：route object、router 创建、route component
- 菜单：导航配置
- 字段：form 标签、schema、disabled/readonly 条件
- 列表：列定义、筛选、分页、空态
- 动作：event handler、导航、确认弹窗
- 权限：受保护 route 和 authorization wrapper/hook

对两者而言，可见性不等于 enforcement。隐藏按钮只能支持一条可见性观察，直到它与运行时 enforcement layer 连通。

## 后端

### Spring

- 入口：controller mapping 和 request model
- enforcement：authorization annotation、validator、service guard
- 状态：domain/service 转换方法和持久化结果
- feedback：exception mapping 和用户可见响应契约

### NestJS 和 Node router

- 入口：controller、router、module、public handler
- enforcement：guard、pipe、schema、service check
- 状态：service/domain 转换和 repository 写入
- feedback：filter、error mapping、返回响应结构

单独的 endpoint 声明或导出 handler 仍是 `partial`；必须证明调用方、enforcement point 和可观察结果后才能声称 aligned。

## 跨层三角验证

端到端 finding 至少寻找两个不同层：

1. `entry`：可达页面、route、命令或 public handler
2. `enforcement`：权限或校验点
3. `state`：持久化或外部可观察的状态转换
4. `feedback`：可见结果、错误、重试、回滚或导航
5. `external`：与其他参与者或系统的边界

只有 `evidence_coverage=enforcement-layer` 时，才能单独使用 canonical enforcement point。前后端不一致时，同时记录双方，并按 calibration contract 将结果归为 `unknown` 或 `conflict`。
