# 浏览器工具安装与就绪引导

接入失败时先确认用户的操作系统和已选工具，给出对应的一条安装/恢复路径；已可用则直接预检，避免重复安装。用户指定现有浏览器时先检查对应连接器，通过对应连接器选择该标签页。安装系统应用、浏览器数据导入和企业 SSO 登录由用户完成；TestKit 不下载未知安装包、不复制个人认证数据、不自动关闭系统安全检查。

## 只读工具 check

执行前先运行（Windows 可将 python 换为 py 或当前 Python 命令）：

```bash
python skills/app-test/scripts/web_check.py
```

检查 PATH 上 ego-browser、agent-browser、Node.js 和 Python 命令是否存在，不启动程序、不扫描 Profile、不输出安装路径。宿主 MCP/Computer Use 不一定有 CLI，先按当前工具清单发现其文档，再显式声明，例如：

```bash
python skills/app-test/scripts/web_check.py --host-tool browser-connector --host-tool computer-use
```

只有确实暴露相应能力时才声明；已有 Midscene 项目可声明 `--host-tool midscene-project`。宿主 MCP 和 Midscene 版本从当前工具清单及项目依赖读取。退出码 0 仅表示有候选路线（preflight-required），2 表示没有候选路线（blocked）。尊重用户指定工具；候选列表按 ego-lite、Midscene、agent-browser、Computer Use 的分工排序（browser-connector 提供指定标签页接入），不能据此切换用户已选会话。

有候选路线后再读对应 CLI/宿主文档，验证运行时、连接、指定标签页和认证状态；只有 web_session.py 基于新鲜观察返回 ready 才执行依赖步骤。CLI 缺失按以下安装方案引导，运行时失败按实际错误诊断。

## ego-lite 官方安装

官方统一入口：[ego-lite 下载页](https://lite.ego.app/)。从页面 Download 选择当前系统提供的安装包；发布渠道、beta 标识和支持架构以当前官方页面/安装器为准，不固定 CDN 安装包地址。宿主已有 ego-browser skill 时先读其安装参考，按当前官方方案引导；不要把 macOS 安装脚本用于 Windows。

| 系统 | 引导用户完成 | 安装后检查 |
|---|---|---|
| macOS | 官网选择匹配 Apple Silicon / Intel 的安装包，打开官方安装器，安装并启动 ego-lite，完成 onboarding。数据导入为用户可选项；企业证书/SSO 可能仍需重新认证 | 新终端执行 `command -v ego-browser`；若未找到，检查 `~/.local/bin` 是否已加入 PATH，并重新打开终端 |
| Windows | 官网选择 Windows 安装程序（若标为 beta，明确告知 beta），运行并启动 ego-lite，完成 onboarding。没有 Windows 安装选项时如实报告当前入口不可用，不猜下载地址 | 打开新的 PowerShell 执行 `Get-Command ego-browser`；旧终端/宿主可能未获得更新后的 PATH，需要重启相应进程 |

两端检查当前 agent 已加载 ego-browser skill；缺失时按[官方补装步骤](tool-install.md#ego-browser-skill-缺失时补装)安装并重新加载。随后执行：

```text
ego-browser skill
ego-browser nodejs -e "console.log('ego-browser ready')"
```

指南必须完整输出到 end of guide；runtime 打印 ready 后继续 TaskSpace/Page 预检。发现旧版 CLI 不支持 skill 时，按宿主安装指南和已有授权处理升级，不直接覆盖用户安装。

安装或 onboarding 需要用户操作时，给出当前步骤并等待完成；恢复后在原测试目标中继续能力检查。安全系统或组织策略阻止安装时报告具体阻碍，不能建议关闭防护。若用户希望使用现有登录态，在所选 ego Profile 内打开目标业务页面验证登录标记。

## 其他已选工具

具体依赖安装、Chrome Bridge 和宿主插件步骤见[官方安装流程](tool-install.md)。

- agent-browser：按该项目官方入口 https://github.com/vercel-labs/agent-browser 和本机 `--help` 核对安装、平台和版本。使用专用持久化 Profile/CDP 前先明确用户选择；工具缺失时按选定安装范围执行官方安装步骤。
- 宿主浏览器连接器 / Computer Use：按已暴露工具文档检查支持平台、浏览器连接、授权和 URL 识别。缺少连接器应说明需要哪项能力，不能用安装浏览器代替连接能力。
- Midscene UI 自动化：沿用项目锁定版本、AI fixture 和安装方式，执行语义操作、视觉断言与回归；先核对选定会话的接入能力。

安装后统一回到 [会话接入与诊断](web-session.md)，完成绑定、认证检查和连续导航验证。只在当前路线确实不可用且不存在权限阻断时提出另一条路线，说明其登录环境不同；用户选定后持续复用。
