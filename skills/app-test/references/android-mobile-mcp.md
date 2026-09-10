# Android：Mobile Next Mobile MCP

默认 provider 为 [mobile-next/mobile-mcp](https://github.com/mobile-next/mobile-mcp)。本操作手册依据其 README 和 src/server.ts 的工具定义核对；实际会话仍以 tools/list 暴露的名字、参数和版本为准，宿主可能加命名空间前缀。缺工具时给出缺失项，不假造 MCP 调用，不自行切换到付费云设备。

## 发现与最小准备

1. 在宿主列出 Mobile MCP 工具。基础集合：mobile_list_available_devices、mobile_list_apps、mobile_launch_app、mobile_list_elements_on_screen、mobile_take_screenshot、mobile_click_on_screen_at_coordinates。输入/滑动/录屏按本次用例再检查。
2. 调用 `mobile_list_available_devices {}`，用返回的 id/platform/type/state 选择用户指定的设备。多台候选且无法从任务确定时只询问目标设备。emulator 不标成 real；旧版 provider 的设备类型若与 ADB 证据冲突，先核实再给真机结论。
3. 在选中设备调用 `mobile_list_apps {device}`，从实际返回解析 packageName。用户给出的包名仍核对是否安装；不要根据 App 显示名猜包名。
4. `mobile_take_screenshot {device}` 和 `mobile_list_elements_on_screen {device, format:"json"}` 建立初始状态。旧版不支持 format 时按其 schema 调整。查明锁屏/系统弹窗/前台 App，设备密码或授权确认交给用户。
5. 核对 App build 与环境。Mobile MCP 的 app 列表不一定提供构建号；必要时在已授权设备上使用 `adb -s <live-serial> shell dumpsys package <resolved-package>` 读取 versionName/versionCode，再与包摘要或构建交付记录对照。版本名本身未必唯一。不要把完整 dumpsys/logcat 放入公开产物。

主机准备需要 Android Platform Tools、Node 和已配置的 Mobile MCP 服务；查看上游安装说明后，在获准配置的范围内安装/启动。连接问题用 `adb devices -l` 区分 unauthorized、offline 和多设备，始终指定 serial；不默认 kill-server、重置手机、修改全局配置或安装 APK。

选定设备后，可运行 `python <app-test>/scripts/android_preflight.py --serial <live-serial> --package <resolved-package>`，读取 ADB 状态、系统版本与已安装包版本。脚本不安装、不启动 App、不点击界面，输出不保留 serial 或包名；device-connected 不等于 Mobile MCP native session 可用，也不认证物理设备身份。ADB 可能启动主机上的默认调试服务，按当前环境权限执行。

## 工具调用映射

| 目标 | 上游工具与关键参数 |
|---|---|
| 启动已安装 App | mobile_launch_app：device、packageName |
| 读取元素 | mobile_list_elements_on_screen：device；支持时 format=json |
| 点击 | mobile_click_on_screen_at_coordinates：device、最新 ref；旧版不支持 ref 才用最新元素 bounds 的 x/y |
| 输入 | mobile_type_keys：device、text、submit（明确 false，除非提交已在本步授权内） |
| 滑动 | mobile_swipe_on_screen：device、direction；可选 x/y/distance，按实际 schema |
| 返回/主页 | mobile_press_button：device、button；BACK 仅 Android，勿用于 iOS |
| 保存截图 | mobile_save_screenshot：device、saveTo，支持时 maxSize |
| 有界录屏 | mobile_start_screen_recording：device、output、timeLimit；结束 mobile_stop_screen_recording：device |
| 崩溃与日志 | 可用时 mobile_list_crashes → mobile_get_crash；mobile_get_device_logs 按实际 schema 限范围 |

调用示意中的 device/packageName/ref 由本次发现填充，禁止原样复用示例或上次会话的值。mobile_type_keys 的上游返回文本可能回显输入，认证材料不要写进可复用计划、日志或报告；必要时由用户在设备输入。

## 观察—动作—断言

保持“当前 screen → 一个明确动作 → 新 screen → 断言”的循环。页面导航、布局变化、旋转或键盘弹出后刷新元素引用；不能把旧 ref/坐标接着用于新页面。布局没有变化时不机械重复抓全屏。定位优先唯一文本/可访问性标识，歧义先缩小到容器或截图核对。

工具返回也可能只是普通文本错误（例如 ActionableError），未必 isError=true；同时检查返回内容和实际页面变化。批量工具中的某一步失败也可能在文本内呈现，因此跨页面、跨断言和有副作用的步骤不要压成盲目 batch。点击成功只证明发送了动作；必须核对需求要求的结果和可观察状态。

登录示例：识别输入框 → 聚焦账号 → 输入非敏感测试数据（submit=false）→ 更新 screen → 聚焦密码（如需要用户输入）→ 明确点击登录 → 有界等待首页或错误提示 → 核对断言。每个环节失败保留原始现象，不通过重复点击隐藏问题。

## WebView 与故障定位

Mobile MCP 的原生元素/截图不等于 WebView DOM、Network 或 JS 可访问。若用例只要求可见 UI，可按原生证据判断该 UI；若要求 DOM/H5 断言，必须有独立可用的 inspectable context（例如现有 Appium WebView session 或已授权的调试工具）。无 context 则只阻塞该层，不把整个 App 判失败，也不修改 App 调试开关来绕过限制。

| 现象 | 先核对 | 结论边界 |
|---|---|---|
| 工具缺失 | 宿主 MCP 配置/连接状态 | provider unavailable，不是 App 缺陷 |
| 设备未列出 | USB/无线连接、ADB authorization、屏幕锁定 | device blocked |
| 元素 ref 失效 | 页面/键盘/旋转是否改变 | 重新观察，不能直接重放写操作 |
| 启动后白屏 | 前台包名、原生壳、崩溃与 H5 加载证据 | 不直接断言原生 crash |
| 录屏结束但无文件 | 返回错误、路径存在性与文件大小 | evidence incomplete，不能说录屏已留存 |

结束停止本次录屏，核对文件实际存在且非空；不停止用户已有录制，不关闭无关 App。保留设备连接、原生断言、WebView 发现、H5 断言四层结果和清理情况。安装/卸载、系统设置、云设备分配与业务写操作遵循任务已有授权，范围新增时才补确认。

来源：[工具实现](https://github.com/mobile-next/mobile-mcp/blob/main/src/server.ts)、[安装与调试 Wiki](https://github.com/mobile-next/mobile-mcp/wiki)。
