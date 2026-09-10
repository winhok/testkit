---
name: app-test
license: MIT
description: 执行 Android、iOS 与 Web 的真实运行测试，验证页面交互、系统行为和跨端业务旅程，记录实际断言与证据。用户要测试网站、操作手机应用、跑端到端用例或验证 WebView 时使用；分析网站产物发现测试点走 web-runtime-analysis，录屏转缺陷报告走 video-to-issue。
---

# 三端应用测试

根据已确认用例或局部目标，在当前可用且已授权的真实运行环境中完成操作和断言。物理设备、模拟器和桌面浏览器分别记录，不把连接成功当功能通过。

执行前读取 [共享执行契约](../_test-run-shared/references/execution-contract.md)。它依赖完整插件；缺少共享目录时提示安装完整 TestKit，不能声称证据已校验。简单局部请求使用 local scope，正式 TestSpec 请求消费当前 strategy 和用例，不重复需求采访。

## 选择运行端

- Web：读取 [web.md](references/web.md)，agent-browser 探索、Midscene 回归；不可用或无法完成目标时回退宿主 Computer Use 技能/工具，不绕过权限门禁。
- Android：读取 [android-mobile-mcp.md](references/android-mobile-mcp.md)，默认使用 mobile-next/mobile-mcp。
- iOS：读取 [ios-appium-xcuitest.md](references/ios-appium-xcuitest.md)，默认使用 Appium + XCUITest + WebDriverAgent；已有 Mobile MCP 的原生观察可复用，但不据此假定有 DOM context。
- 两端共同的版本、资源与结果记录规则：读取 [mobile.md](references/mobile.md)。
- 跨端：按 checks.depends_on 组织旅程，API 步骤使用可用的 api-test-automation；工具能力缺失只阻塞其依赖步骤。

## 执行

1. 核对目标 build/环境、角色、初始状态、断言、允许副作用和工具可用性；区分已授权与待确认动作，复用本任务已有授权。
2. 从用户指定范围建立 scope，包括无法执行项，运行 freeze。写测试定义、数据和断言必须在冻结前完成。
3. 选择宿主已有工具执行。遵守工具自身的控制方式和权限；不得假定 Appium、Mobile MCP 或某浏览器插件必然存在。没有可执行工具就记录 blocked 及需要的具体能力。
4. 每个断言保留实际值、工具输出定位、目标身份和必要截图，写 observation JSON 并 record。HTTP 200、控件存在或单次点击均不能替代业务断言。
5. 依赖步骤以实际结果驱动，异步状态使用有界轮询。失败记录原始现象后继续独立用例；保留重试历史。
6. 清理本次创建的资源，evaluate 当前范围，报告各端结果、未测项、证据路径与环境限制。

移动端交付前逐项核对：设备类型来自实际发现；定位在最近页面状态下仍有效；工具文本错误未被当成成功；native/WebView/DOM 分层判定；本次创建的会话有清理结果。没有真实设备记录时，报告只能说操作手册/协议测试已验证。

分析发现的新需求疑点交给 TestSpec；复测任务由 defect-verification 组织；报告正式验收交给 test-acceptance。禁止把测试过程自动扩展成修复业务代码。
