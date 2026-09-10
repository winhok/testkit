# 侦察方法与输出

优先使用宿主已有的浏览器/产物工具，并遵守其接口约束。只分析目标站点已交付或明确提供的资源。可以按已观察到的资源引用分析动态 chunk、CSS、source map；不猜测私有路径、不绕过登录、不批量探测服务端。第三方域资源记录归属与范围，不自动扩展扫描。

## DOM / CSS

记录页面区块、交互控件、表单类型/约束、条件显示、角色差异、可访问性属性、空态与错误态。CSS 断点、主题、隐藏状态、层叠和动画提供布局与交互风险线索，不能据此断言隐藏功能可用。虚拟列表、Shadow DOM、iframe 和懒加载注明观察边界。

## JS / 请求 / 状态

对已知 bundle 做有界检索和必要格式化，避免将整个混淆包塞入上下文。优先请求客户端、路由表、schema/校验器、状态处理和错误码映射。source map 仅在公开提供且范围内时使用；保存最小 locator，不公开整个来源源码。

接口目录记录 method、path、参数名称/类型、发现位置、实际调用与否、响应结构、错误分支和关联页面；脱敏查询参数、Cookie、Authorization、响应个人信息。GraphQL 区分 operation 与 endpoint，WebSocket/SSE 区分连接、消息发送、接收及页面消费。Storage/IndexedDB/Service Worker 观察 key/schema 和生命周期，不默认导出 secret 或清空存储。

inspect_assets.py 用稳定 origin_label 区分不同服务，不输出原始域名和凭据。同一路径的不同来源不能合并。显式 axios 方法会保留 method；fetch 的 method 未解析时为 null，不默认把未知方法当 GET。

必要交互验证限定目标和副作用：观察请求不意味着获准重放写请求。工具无法查看 Network、响应体或资源内容时说明缺口，改用可见 DOM 与用户提供的脱敏产物。

## Finding

从实现线索转换成可执行风险，而不只列接口：overflow/层叠上下文 → 容器边缘弹层；固定宽度/长字段 → 长文本和窄屏；主题覆盖 → 真实主题对比度；异步关闭/自动消失 → 动作前的时序取证；客户端校验 → 错误状态和独立副作用检查。每项附触发数据、环境、最小动作、首选 oracle 和证据缺口。CSS/JS 只能形成候选，触发后观察才升级为运行时发现。

需要交互验证时按 app-test 的 [Web 分支](../../app-test/references/web.md) 选择浏览器与断言。Network 监听应早于动作，关联请求与页面结果；没有监听到请求也可能是缓存、Service Worker 或工具盲区，不能直接断言“后端未收到”。异常分支未获故障注入权限时保留为待测，不擅自篡改响应。输出交接保留风险、条件、oracle 和未测项，不自动生成或安装整套回归平台。

建议结构：
```json
{"id":"WEB-001","classification":"static-candidate","surface":"api","locator":"assets/main.js:request-handler","observation":"发现提交入口","test_candidates":["重复提交与失败恢复"],"limitations":["当前角色未实际触发"],"authority":"reference"}
```
runtime-observed 必须有真实浏览器事件，interaction-confirmed 必须记录操作与可见结果。原始观察与“可能风险”分开。时间相近不足以证明同一请求；优先请求/业务关联标识，找不到关联就降低结论强度。
