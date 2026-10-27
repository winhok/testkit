# Web 工具官方安装流程

核对日期：2026-10-28。按用户选定路线安装缺失项，沿用目标项目包管理器与锁文件。安装前读取下列官方入口的当前版本；安装完成后回到工具 check 和会话绑定。安装请求覆盖的普通依赖安装直接执行，GUI 授权、登录和系统权限交给用户完成；失败时报告具体命令及修复步骤。

## ego-lite：首选会话接入

官方：[macOS 快速开始](https://lite.ego.app/document/en/docs/quick-start)、[Windows 快速开始](https://lite.ego.app/document/en/docs/windows/quick-start)。

1. 从对应页面下载当前架构安装器。macOS 打开 DMG，按界面双击图标安装；Windows 运行安装器（当前为 beta）。
2. 启动应用完成 onboarding，按用户选择导入浏览器 Profile 或直接登录。导入、钥匙串和账号验证由用户处理。
3. 新终端检查 `command -v ego-browser`（macOS）或 `Get-Command ego-browser`（PowerShell），再检查当前 agent 的 skill 列表中是否有 ego-browser。已有时读取其 SKILL.md；缺失时按下节补装，重新打开 agent 后确认已加载。
4. 执行 `ego-browser skill`，完整读取当前版本指南，再运行 `ego-browser nodejs -e "console.log('ego-browser ready')"`。按指南建立或恢复同一 TaskSpace，检查目标页面登录标记。

### ego-browser skill 缺失时补装

官方[独立 skill 安装说明](https://lite.ego.app/document/en/docs/ego-browser)提供：

```bash
npx skills add github:CitroLabs/ego-lite/skills/ego-browser -g -a codex
```

`-g` 安装到用户级目录，`-a` 选择当前 agent；Claude Code 改为 `-a claude-code`，其他宿主按 [skills CLI 官方安装文档](https://github.com/vercel-labs/skills)选择 agent。先检查 `node --version`、`npx --version`，当前 skills CLI 要求 Node.js 22.20+；依现有 Node 管理方式补齐后执行。只补浏览器操作所需的 ego-browser skill，保留在 TestKit 仓库之外。

安装后确认工具返回目标 skill 路径、读取 SKILL.md，刷新 skill 列表或重新打开 agent，再按文档完成运行时检查。`ego-browser skill` 输出的是运行指南，补装使用上面的 `npx skills add`。官网示例与已装版本 API 不一致时，以本机 CLI 指南为准。

系统应用启动受宿主权限限制时，使用该宿主提供的应用执行授权流程。PowerShell 的后续脚本按 web-session.md 保存为 UTF-8 .mjs。

## Midscene：UI 自动化

官方：[Web 环境](https://midscenejs.com/platforms/web)、[Chrome Bridge](https://midscenejs.com/bridge-mode)、[创建测试项目](https://midscenejs.com/midscene-test/use)。

先读取现有 package.json、锁文件和测试配置，选择当前版本对应路线。当前官方 Node.js 要求为 `^20.19.0 || ^22.12.0 || >=24.0.0`，检查 `node -v` 和包管理器。

### 复用已登录 Chrome

1. 从官方 Chrome Bridge 页面进入 Chrome Web Store 安装扩展，由用户确认浏览器授权。
2. 在目标测试项目安装：`npm install --save-dev @midscene/web tsx`（pnpm 项目用 `pnpm add -D @midscene/web tsx`）。
3. 依照官方最小 bridge-check.ts 做无模型连接检查，使用 `AgentOverChromeBridge`，执行 `npx tsx bridge-check.ts`。扩展提示时用户允许连接；保留自己的选定标签页，不向日志打印全量标签页清单。
4. 按当前 Bridge API 选择目标标签页，建立绑定，随后配置项目模型并执行获准 UI 用例。

### 独立测试浏览器 / 现有 Playwright 项目

安装 `npm install --save-dev @midscene/web playwright`，然后 `npx playwright install chromium`。已有 Playwright Test 项目沿用其 fixture。新建测试项目可用官方 `pnpm dlx @midscene/test create my-tests --platform web --package-manager pnpm`，在选定目录生成，再按生成 README 安装浏览器及配置模型。只在需要创建项目时使用脚手架。

模型配置使用项目指定服务和安全的本地环境文件；真实模型验证和 UI 执行按任务授权进行，安装检查先使用无模型连接检查。Chrome Bridge 的扩展授权与模型配置分别检查；ego-lite 与 Midscene 的连接方式按当前工具 API 验证，使用现有 Chrome Bridge 或项目浏览器时记录对应会话。

## agent-browser：辅助探索与诊断

官方：[安装](https://agent-browser.dev/installation)、[Skills](https://agent-browser.dev/skills)。

- 默认项目依赖：`npm install agent-browser`；需要自建浏览器时执行 `npx agent-browser install` 下载 Chrome for Testing。
- 用户选择全局 CLI 时：`npm install -g agent-browser`，随后 `agent-browser install`；macOS 已用 Homebrew 管理时沿用 `brew install agent-browser`。Windows 使用 npm 路线。
- 安装检查：运行选定安装方式下的 `agent-browser --version`、`agent-browser --help`；本地依赖使用 `npx agent-browser` 前缀。按当前子命令帮助核对 Profile/CDP 参数。
- agent skill 可按官方 `npx skills add vercel-labs/agent-browser` 安装到用户指定的 agent skill 目录，保持在 TestKit 仓库之外。
- 当前 `doctor` 会自动清理过期 daemon 文件，`doctor --fix` 还会关闭会话或删除过期状态；诊断前读取当前帮助和影响，在授权覆盖这些修改时才执行。只读工具盘点使用 web_check.py。

## Computer Use：宿主兜底

官方：[Computer Use 安装与权限](https://developers.openai.com/codex/computer-use)。

在支持的 macOS/Windows 桌面宿主中打开 Plugins → Computer Use，安装/启用插件，打开 server 和 skill 开关。macOS 由用户授予屏幕录制与辅助功能权限；Windows 保持目标窗口在当前活动桌面可见。通过宿主设置检查目标应用访问权限，再以当前暴露的工具文档连接目标应用。

其他 agent 宿主沿用其实际提供的 Computer Use 集成及官方安装页；从工具清单确认 provider 后给出对应步骤。Computer Use 属于宿主插件接入，不使用 npm 安装同名包。接入后先观察目标窗口和 URL，再执行获准测试动作。
