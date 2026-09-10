# 执行 Android、iOS 与 Web 测试

`app-test` 在当前可用且已授权的真实运行环境中执行已确认的测试目标，记录页面交互、系统行为、业务断言和证据。它支持单端检查，也支持带依赖关系的跨端业务旅程。

## 运行前准备

开始前应提供或确认：

- 被测平台、构建版本和环境。
- 账号角色、初始状态和测试数据。
- 已确认用例或局部测试目标，以及实际业务断言。
- 允许的副作用和需要清理的资源。
- 当前可用的设备、浏览器或自动化工具。

TestKit 不捆绑设备、浏览器服务、Appium driver、签名、业务账号或目标 App。工具缺失会被记录为阻塞，不会伪装成测试通过。

## 平台路线

| 平台 | 默认路线 | 关注点 |
|---|---|---|
| Web | agent-browser、Midscene 或宿主 Computer Use | 页面状态、业务 oracle、瞬时证据和回归稳定性 |
| Android | mobile-next/mobile-mcp | 设备身份、当前页面状态、定位有效性和 native/WebView 分层 |
| iOS | Appium + XCUITest + WebDriverAgent | session 生命周期、native/H5 context 和清理结果 |
| 跨端 | 按依赖步骤组织各端与 API 检查 | 前置结果、共享数据、异步状态和独立失败 |

## 执行与结果

工作流会冻结目标版本、环境、范围和断言，再执行各项检查。每个断言保留实际值、工具输出定位、目标身份和必要截图；失败后的重试不会覆盖第一次失败，无法执行的项目也保留在范围中。

典型请求：

```text
在 Android 修复版上执行登录用例，核对错误提示并保留截图证据
在 iOS 原生页和 WebView 中验证同一条支付前置流程
按这组已评审用例完成 Web 回归，并列出阻塞和未测项
```

完成后会报告各端通过、失败、阻塞和未测项，以及证据路径、重试、清理和环境限制。连接成功、HTTP 200、控件存在或单次点击都不能单独代表业务通过。

完整执行契约见 [`app-test`](../skills/app-test/SKILL.md) 和[共享执行契约](../skills/_test-run-shared/references/execution-contract.md)。无源码网站的实现侦察使用 [Web 应用逆向](web-app-reverse.md)，修复复测使用[缺陷验证](defect-verification.md)。
