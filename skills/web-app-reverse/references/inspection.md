# Web 应用逆向方法与输出

优先使用宿主已有的浏览器/产物工具，并遵守其接口约束。只分析目标站点已交付或明确提供的资源。可以按已观察到的资源引用分析动态 chunk、CSS、source map；不猜测私有路径、不绕过登录、不批量探测服务端。第三方域资源记录归属与范围，不自动扩展扫描。

## 覆盖账本与全局地图

先建立覆盖账本，避免“扫了 main.js”等同于“看完网站”：记录入口 HTML、同页实际引用、导出目录已有文件、仅被引用但未提供的资源、大小限制跳过项、source map 对应关系、已知页面/角色和未触发 lazy chunk。覆盖率只能以明确清单为分母；分母未知时报告 `coverage: bounded-unknown`，不要给百分比。

按六层组织全局视野，而不是按文件逐个复述：

1. **页面层**：入口、布局区、路由、弹层、iframe、空态/错误态和角色可见面。
2. **资源层**：HTML → entry bundle/CSS → static import/dynamic chunk → worker/service worker/source map；标记 first-party/third-party 和 hash/版本线索。
3. **通信层**：HTTP、GraphQL operation、WebSocket、SSE、Beacon；相同 path 按 origin、method/transport 分开。
4. **状态层**：表单约束、客户端 store、Storage/IndexedDB/Cache、URL 参数、功能开关、角色/权限条件和生命周期。
5. **行为层**：用户动作 → 校验/分支 → 请求或本地变化 → 成功/失败/重试/回退 UI；静态材料缺少的环节留空。
6. **测试层**：从行为链生成可执行候选，写明触发数据、角色/前置条件、首选 oracle、风险和仍需确认的证据。

先按资源引用和 locator 归并，再按业务词、route、operation、状态 key 的共现聚类。框架指纹只帮助定位结构，不把压缩变量名、组件名或依赖包名当产品规则。未被当前页面使用的代码可能是 lazy chunk、共享包、旧功能或死代码，统一保留为候选。

## DOM / CSS

记录页面区块、交互控件、表单类型/约束、条件显示、角色差异、可访问性属性、空态与错误态。CSS 断点、主题、隐藏状态、层叠和动画提供布局与交互风险线索，不能据此断言隐藏功能可用。虚拟列表、Shadow DOM、iframe 和懒加载注明观察边界。

## JS / 请求 / 状态

对已知 bundle 做有界检索和必要格式化，避免将整个混淆包塞入上下文。优先定位入口/bootstrap、路由表、动态 import、请求封装、GraphQL 文档、schema/校验器、状态处理、权限守卫、功能开关和错误码映射，再追到业务模块。保留 `bundle:line`、source map source 或浏览器 Sources locator，不大段复制源码。

source map 仅在浏览器已发现、产物已提供或明确允许的公开资源范围内使用。用 bundle 摘要、`sourceMappingURL` 和 map 的 `file` 字段关联版本；关联不上就标为未验证。`sourcesContent` 能恢复模块结构但不自动代表当前线上执行路径。可选的 bundle treemap/coverage 只用于理解模块构成和本次动作触达面，unused 不等于不可达。

接口目录记录 method、path、参数名称/类型、发现位置、实际调用与否、响应结构、错误分支和关联页面；脱敏查询参数、Cookie、Authorization、响应个人信息。GraphQL 区分 operation 与 endpoint，WebSocket/SSE 区分连接、消息发送、接收及页面消费。Storage/IndexedDB/Service Worker 观察 key/schema 和生命周期，不默认导出 secret 或清空存储。

inspect_assets.py 用稳定 origin_label 区分不同服务，不输出原始域名和凭据。同一路径的不同来源不能合并。显式 axios 方法会保留 method；fetch 的 method 未解析时为 null，不默认把未知方法当 GET。

辅助脚本会列出字面量 XHR/Beacon/WebSocket/SSE、route、static/dynamic import、CSS import、worker/source map、Storage key 和 GraphQL operation。它们都是启发式 `static-candidate`：计算属性、字符串拼接、压缩改写和运行时注入可能漏报，普通业务字符串也可能误报。自动发现只遍历本地导出目录中的 HTML/JS/MJS/CSS/MAP，不跟随引用下载资源。

补充运行证据时限定目标和副作用：先启动 Network/console/trace 监听，再做页面加载或无副作用导航。记录 request initiator、redirect、HTTP status、transport failure、cache/Service Worker 来源和动作前后 DOM；HTTP 4xx/5xx 是有响应结果，不等于网络传输失败。分析已有请求不意味着获准重放请求。

禁用缓存、绕过 Service Worker、限速、覆盖响应和 request blocking 会改变实验条件。逆向侦察只记录现状和测试设计建议，不执行这些干预。没有监听到请求也可能是 Cache、Service Worker、页面未受控或工具盲区，不能直接断言后端未收到。

## Finding

从实现线索转换成可执行风险，而不只列接口：overflow/层叠上下文 → 容器边缘弹层；固定宽度/长字段 → 长文本和窄屏；主题覆盖 → 真实主题对比度；异步关闭/自动消失 → 动作前的时序取证；客户端校验 → 错误状态和独立副作用检查。每项附触发数据、环境、最小动作、首选 oracle 和证据缺口。CSS/JS 只能形成候选，触发后观察才升级为运行时发现。

发现需要有副作用的验证时，先保留行为链、前置条件、数据需求、oracle 和未测项，交给 TestSpec 转换为完整用例；只有用例和目标环境确认后，才由 app-test 的 [Web 分支](../../app-test/references/web.md)执行。不能把单个接口候选直接交给 app-test，也不自动生成或安装整套回归平台。

建议结构：
```json
{"id":"WEB-001","classification":"static-candidate","surface":"api","locator":"assets/main.js:42","observation":"发现提交入口","related_surfaces":["route:/profile","form:save"],"test_candidates":["重复提交与失败恢复"],"limitations":["当前角色未实际触发"],"authority":"reference"}
```
runtime-observed 必须有真实浏览器事件，interaction-confirmed 必须记录操作与可见结果。原始观察与“可能风险”分开。时间相近不足以证明同一请求；优先请求/业务关联标识，找不到关联就降低结论强度。

## 交付契约

`inspection-report.md` 或等价回复至少包含：范围与输入、覆盖账本、六层全局地图、跨文件关联后的 findings、按业务风险排序的测试候选、冲突/死代码候选、未知项和下一步最小验证。不要只输出 endpoint 列表。

需要 JSON 时输出 `inspection-map.json`：

```json
{"schema_version":1,"scope":{},"coverage":{},"maps":{"pages":[],"resources":[],"communications":[],"states":[],"behaviors":[],"test_candidates":[]},"findings":[],"unknowns":[]}
```

`coverage` 区分 `local_reference_edges`、`available_reference_edges`、`unique_local_resources` 和 `available_unique_resources`；无法解析的引用进入 `unresolved` 并给出 reason。辅助脚本生成 schema v2 的 `asset-inventory.json`，它是原始中间产物，不能直接冒充最终报告。

## TestSpec 交接

逆向报告在没有仓库时补充实现证据，与 `testspec-code-calibrate` 占据相同的上游发现位置，但二者产物不能混用：

```text
web-app-reverse → testspec-new（尚无 change 时）→ testspec-analysis
                → testspec-plan（条件必需）→ testspec-points → testspec-generate → testspec-review
```

在 TestSpec context 的 `evidence_sources` 中登记为 `type: ui`、`authority: reference`，`source_ref` 指向 `inspection-report.md` 或 `inspection-map.json`。不得写入 `_context.code_evidence`、冒充 `code-calibration.json`，或把当前实现直接变成需求和 oracle。实现与 PRD 冲突时生成稳定问题，待产品确认后由 `testspec-update` 收敛。

## 禁止捷径

- 不把 endpoint 字符串清单当成全局地图。
- 不把重复引用边当成多个唯一资源，也不在分母未知时给百分比。
- 不猜测未引用的 source map、chunk 或私有路径。
- 不把静态候选、已有运行记录和本次确认混成同一证据等级。
