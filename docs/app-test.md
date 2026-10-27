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
| Web | ego-lite 优先接入；Midscene 做 UI 自动化；agent-browser 辅助；Computer Use 兜底 | 页面状态、业务 oracle、瞬时证据和回归稳定性 |
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

## 已登录浏览器

按[会话接入与诊断](../skills/app-test/references/web-session.md)绑定目标会话，每轮重新验证连接、目标和认证状态。在选定环境完成登录，或通过对应连接器接入用户指定的现有标签页。持久化 Profile、同会话恢复、Windows 调用及阻塞分类见该说明。

首次使用请按[浏览器安装与就绪引导](../skills/app-test/references/browser-setup.md)选择 macOS/Windows 官方安装方案，并完成 CLI、运行时和目标会话三级检查。

## 受阻后的自动分析

会话或页面操作无法继续时，自动做一次[范围内静态诊断](../skills/app-test/references/web-blocked-analysis.md)，分析当前可读页面、已交付资源和已有脱敏记录，输出事实、假设和用户复测建议。诊断结果包含证据支持的原因和下一步。Windows 企业 SSO 现场测试由用户执行。

工具预检：`python skills/app-test/scripts/web_check.py`，输出已安装 CLI、宿主声明能力和候选路线。它不会启动浏览器，候选存在仍须验证目标会话；详见[工具 check](../skills/app-test/references/browser-setup.md)。

各工具的项目依赖、全局 CLI、Midscene Chrome Bridge 和 Computer Use 插件安装见[官方安装流程](../skills/app-test/references/tool-install.md)。agent 根据操作系统、已有项目与工具 check 结果选择对应步骤并完成安装验证。
