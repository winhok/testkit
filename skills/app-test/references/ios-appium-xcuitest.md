# iOS：Appium / XCUITest / WebDriverAgent

默认使用已运行的 Appium + XCUITest driver，通过 WDA 连接本次选定的设备。已有 Mobile MCP 可以承担其实际支持的原生观察/交互，但不能由此假定具备 WebView DOM。需要 H5 DOM 时按本手册建立可检视 context。

## 准备与阻塞定位

1. 查当前 Xcode 路径和版本（xcode-select -p、xcodebuild -version），以及 `appium --version`、`appium driver list --installed`。XCUITest driver 与 Appium/Xcode/iOS 的兼容性按当前官方要求核对，不能只检测命令存在。
2. 用当前 Xcode Devices 或可用设备发现工具取得真实 UDID、设备类型、iOS 版本、锁定/信任状态。Simulator 可用于模拟测试，但不得记录成真机。多个设备不能仅用 deviceName 模糊选择。
3. 核对实际 bundleId、已安装 build 与交付包摘要。需要安装、设备信任、Developer Mode、签名配置或 Apple 账号操作时，复用已有明确授权；系统密码与设备确认由用户处理。不要在报告中保存 UDID、签名身份或账号。
4. 用 Appium `/status` 验证服务可响应，但 ready 不等于设备/WDA/目标 App 可运行。session 创建失败按错误类别区分签名、设备、driver、端口和 bundle 配置；不要默认把它记为产品 Bug。

## WDA 与服务生命周期

优先复用用户已运行且允许使用的 WDA/Appium。没有 WDA 时，按照官方 real-device provisioning 流程准备；不能猜 team ID，不能自动改变现有签名。仅在获准后使用本次发现的值构建/签名 WDA。需要 RemoteXPC tunnel 时按当前 driver 指引与设备版本判断，不把所有 iOS 都固定要求特权隧道。

新建隔离 Appium 环境时，在当前任务的临时目录设置 Appium 的 `APPIUM_HOME`，不改用户全局 driver/plugin 清单。目录必须先创建；命令存在但 home 缺失仍可能启动失败。按当前 CLI 帮助安装获准版本的 xcuitest driver；记录本次 server/WDA/tunnel 的进程与端口，退出只清理本次创建的资源。

## 会话配置

W3C 请求为 POST `<server>/session`，body 使用 capabilities.alwaysMatch。以下是语义模板，值由本次发现填入：

```json
{
  "platformName": "iOS",
  "appium:automationName": "XCUITest",
  "appium:udid": "<live-udid>",
  "appium:bundleId": "<installed-bundle-id>",
  "appium:webDriverAgentUrl": "<existing-wda-url>",
  "appium:noReset": true,
  "appium:fullReset": false,
  "appium:shouldTerminateApp": false,
  "appium:forceAppLaunch": false,
  "appium:autoAcceptAlerts": false,
  "appium:autoDismissAlerts": false,
  "appium:newCommandTimeout": 60
}
```

默认保留已有 App 数据和状态，不开启 fullReset、自动接受权限框、重装 App 或强制重启。WebDriverAgentUrl 指向已运行 WDA 可避免 session 隐式构建/安装 helper；如果选择其他 WDA 启动模式，明确其安装与签名影响后按对应指南执行。Appium server 未设 base-path 时使用根路径；已有服务配置了 /wd/hub 时显式提供该路径，不轮番猜 URL。

## 原生操作与 H5

优先 accessibility id，其次可维护的 iOS predicate/class chain。元素查找必须唯一；动作后重新读取实际属性/可见状态，不复用 stale element。输入、点击和手势分别使用当前 Appium driver 的 W3C/execute API，不推测 Android BACK 在 iOS 可用。

对已到达的页面，可用本 Skill 的 `scripts/ios_appium_smoke.py`：先 --check 验证配置，再 --execute 连接已有服务，核对原生元素及可选 H5 DOM。它只做 smoke，不负责安装 WDA、签名、业务流程导航或操作系统配置。能力 JSON 保存在私有临时位置，输出不记录 UDID/bundleId。

helper 按 Appium 3 的命名空间接口实现，已核对当前 Appium 3.7.0 路由。使用已有 server 前确认不会因 session override 终止其他人的会话；目标设备应由本任务独占。`/appium/sessions` 需要服务器允许 session_discovery，不能为查询会话自行开启 insecure feature；无法确认时使用获准的新隔离 server。

```sh
python <app-test>/scripts/ios_appium_smoke.py --capabilities <private-caps.json> --server <local-appium-url> --native-id <expected-accessibility-id> --check
python <app-test>/scripts/ios_appium_smoke.py --capabilities <private-caps.json> --server <local-appium-url> --native-id <expected-accessibility-id> --execute --output <new-smoke.json>
```

要验证 H5，再加 `--webview-selector <css>`；多个 WebView 时提供由当前 GET contexts 发现的 `--webview-context <name>`，不能选第一个凑结果。

手动完整流程：GET `/session/<id>/appium/contexts` → 筛选目标 WEBVIEW → POST `/session/<id>/appium/context` 切换 → 确认 URL/title/DOM 对应目标页面 → 执行明确的 DOM 断言 → 按后续步骤切回 NATIVE_APP。旧版本接口先核对其协议文档，不盲目重试多个路径。Web Inspector、App 的 inspectability、前台页面和实际是否含 WebView 分别核对；只有 NATIVE_APP 说明未发现 Web context，不能说明 H5 已通过。

## 错误与清理

| 错误类别 | 下一步 |
|---|---|
| session not created / WDA 不可达 | 核对 driver、签名、已运行 WDA URL、设备信任/锁定、端口；不要直接重建签名或重装 |
| no such element | 核对当前 context、页面和定位器；有界重新观察后保留失败证据 |
| stale element reference | 当前页面重新定位，再判断原动作是否已经生效 |
| 多个/零个 WebView | 记录发现结果，明确目标或 inspectability；不猜 context |
| 创建 session 超时且无 ID | 不盲目重试；先查服务器是否已创建残留 session |
| 删除 session 失败 | cleanup=failed，整体不能报告完整通过 |

无论断言成功/失败，都在 finally 中删除本次创建的 session；切换过 WebView 时先尝试恢复原生。用户已有 server/WDA/tunnel 不归本次 smoke 所有，不能直接关闭。清理失败保留单独状态，不覆盖原始断言结果。

来源：[设备准备](https://appium.github.io/appium-xcuitest-driver/latest/getting-started/device-setup/)、[Capabilities](https://appium.github.io/appium-xcuitest-driver/latest/reference/capabilities/)、[Hybrid Apps](https://appium.github.io/appium-xcuitest-driver/latest/guides/hybrid/)、[WDA 启动方式](https://appium.github.io/appium-xcuitest-driver/latest/guides/run-preinstalled-wda/)、[WebDriver API](https://appium.io/docs/en/latest/reference/api/webdriver/)。
