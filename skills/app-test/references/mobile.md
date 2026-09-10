# Android / iOS 执行

发现已授权的设备与可用连接器，核对 platform、物理/模拟类型、OS、App 标识、安装版本/包摘要、语言和屏幕状态。多设备时按请求选择，目标不明确只进行发现。安装包、重置数据或更改系统设置的副作用需覆盖在任务授权中。

Android 默认 mobile-next/mobile-mcp，按 android-mobile-mcp.md 执行；iOS 默认 Appium/XCUITest/WDA，按 ios-appium-xcuitest.md 执行。用户已指定其他工具时沿用其选择并核对能否满足断言，不静默切换。已安装 CLI、设备被列出、自动化 session 可用、原生断言通过、WebView 可发现和 H5 DOM 通过是六个不同事实。

Mobile MCP 当前实现可能在首次访问部分 iOS Simulator 时安装辅助 agent；工具的 readOnlyHint 不能替代实际副作用核对。按所用版本确认准备步骤及授权，不把模拟器准备过程当成无副作用的真机检查。

按用例测试前后台切换、重启、权限拒绝/恢复、系统返回、旋转、键盘遮挡、深链、网络切换及原生/H5 跳转。只测用户目标所需组合，不默认修改设备全局设置。

进入 WebView 时记录 context、页面 URL 和关联原生步骤，按 web.md 中同样的观察规则执行；不可发现或不可调试就使用原生可见观察，记录 DOM/Network 不可见。不能为测试自行绕过 App 防护或启用未授权调试。

结束只释放本次创建的会话、录制、隧道和辅助进程。用户已有连接和 App 数据保留；清理失败登记结果及明确资源标识。

## 证据对接

操作前后记录实际时间、目标构建核验出处和 screen/context。把实际观察写成共享 observation（status、actual、basis、method=tool），selector 绑定该 JSON 对象；截图、录屏、日志只做对应断言的支持材料。工具启动或传输成功不自动生成 passed。

ios_appium_smoke.py 的 layers.native / layers.h5 可作为 observation 输入，前提是 scope 已冻结、时间匹配且设备/构建另有实际核验；not-requested 层不登记成已执行检查。先看整个报告的 status 与 cleanup，不能从一条绿色 native 记录掩盖所需 H5 阻塞或清理失败。

只读主机检查可运行 `python <app-test>/scripts/mobile_host_check.py --platform android` 或 `--platform ios`。该脚本仅检查命令位置，不枚举设备、不创建 server/session、不安装依赖，也不证明设备已连通。
