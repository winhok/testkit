# 已登录浏览器会话

安装或 CLI 不可用时先按[系统和工具安装引导](browser-setup.md)处理，再回到接入。

## 接入与绑定

用户指定工具、浏览器或标签页时沿用指定目标。默认优先 ego-lite：读取宿主 ego-browser skill，执行 `ego-browser skill` 并读到 end of guide；缺少 skill 时按[官方安装流程](tool-install.md)补装到当前 agent 的用户级目录并刷新加载。先验证真实连接及业务登录标记，再执行测试。

建立本地 session-binding.json，使用不含业务信息的别名：provider、session、page、profile（用户未指定时用 default）、target。ego 的 session 是 spaceId，page 是永久 label；其他工具使用其文档提供的稳定会话和标签页标识。target 是测试目标别名，不是 URL。绑定文件不含 Cookie、Token、密码或认证存储；URL、账号和页面正文也不写入诊断 JSON。

- ego-lite：一个目标只创建一个 TaskSpace，记录 spaceId 和 p1；后续 `taskSpace(spaceId)` 恢复同一空间。现有 Edge/Chrome 标签页通过对应连接器接入。用户指定 ego 标签页时按当前指南授权 claim/adopt；不要遍历无关标签页。Profile 仅在用户明确指定时按 `help("profiles")` 选择，绑定后持续复用。
- agent-browser：先读已安装版本和子命令帮助；仅连接用户指定且已授权的现有 CDP endpoint/标签页，或使用用户选择的专用持久化 Profile。参数以当前 CLI 帮助为准。不要默认启动调试端口、终止普通浏览器、解锁 Profile 或复制认证数据库。独立 Profile 在其中完成一次登录后持续复用。
- 宿主内置浏览器是独立环境；Computer Use 是桌面控制，二者不等于共享本地 Edge/Chrome 登录态。URL 无法通过工具安全校验时记录 blocked，不换工具规避门禁。

首次接入和每轮业务操作前：确认连接、绑定身份、当前 URL 属于获准业务目标（SSO 跳转按预期检查），再检查业务定义的已登录 UI/只读业务 oracle。观察时只返回布尔状态，不输出账号或表单值。登录表单可见且已登录 oracle 缺失时记 authentication-required；两者都不明确时记 authentication-unknown。

## 持续复用与恢复

把本轮实际观察写入 session-observation.json：绑定的五个字段、connection（connected/disconnected/start-failed/permission-blocked）、target_confirmed（布尔）、authentication（authenticated/required/unknown）。每轮重新观察，不能复用上轮 authenticated。运行：

```bash
python skills/app-test/scripts/web_session.py --binding session-binding.json --observation session-observation.json
```

最小绑定示例（所有身份字段使用字符串）：

```json
{"provider":"ego-lite","session":"16","page":"p1","profile":"default","target":"synthetic-app"}
```

本轮 observation 包含相同五个身份字段，并增加：

```json
{"connection":"connected","target_confirmed":true,"authentication":"authenticated"}
```

将两部分合并为 observation 文件，字段取值来自本轮观察。命令退出码 0 表示 ready，2 表示 blocked 或输入无效。

status=ready 后继续依赖认证的操作，并记录业务断言结果。原始工具证据在测试 observation 中关联并脱敏。

需要用户登录时在同一空间/同一 Profile handoff，用户确认后按指南恢复并重新检查；不自动输入凭证。用户接管或权限停止立即停止。断连只尝试文档允许的同会话重连；恢复失败保留绑定并阻塞，不静默新建空间、Profile 或反复换浏览器。明确更换目标时建立新绑定，旧结果保留。完成时按工具规则清理本次资源，保留用户已有会话；ego finish 只在任务完成时执行一次，等待用户登录时不 finish。

## 诊断与 Windows

| 诊断 | 所需证据与下一步 |
|---|---|
| browser-start-failed | 启动错误；页面文件不足属于环境资源问题，修复后重试原路线 |
| connection-lost | CLI/CDP/宿主连接失败；核对指定进程和 endpoint，不假定认证丢失 |
| session-mismatch | 实际绑定字段变化；恢复原会话或明确变更绑定 |
| target-unconfirmed | URL 无法确认或目标不符；恢复目标识别，不执行点击 |
| authentication-required | 登录 UI 和缺失的业务 oracle；同会话交接用户登录 |
| authentication-unknown | 缺少可靠 oracle；补业务登录标记，原因保持未确定 |
| permission-blocked | 工具权限或安全门禁；停止依赖操作，报告原始错误类别 |

SSO 回调失败、Cookie 写入/跨域限制、企业证书或扩展缺失只有相应脱敏事件/错误证据才能作为原因；否则列为待排查，不能从登录表单反推。不要导出 Cookie、认证头、storage 或包含访问令牌的 URL。

Windows 用户从 https://www.egolite.app/download 获取安装程序并完成 onboarding，在新终端执行 `Get-Command ego-browser` 和 `ego-browser skill`。PowerShell 5.1 将每轮代码保存为 UTF-8 的独立 .mjs 文件，通过 ASCII 入口执行：

```powershell
ego-browser nodejs -e "await import('file:///C:/ego-test/round-01.mjs')"
```

不要用 heredoc、Get-Content 管道或带中文的 -e 参数。浏览器由用户在同一 Profile 完成一次登录，再以两次独立 CLI 调用恢复同一 spaceId/page，完成获准导航并验证业务 oracle；用户复测时再检查浏览器重启后的登录保持。

### ego-lite 自动观察适配器

在 `ego-browser nodejs` 的本轮脚本中导入仓库内 `scripts/ego_session.mjs` 的绝对 file URL，调用 `observeSession(task, page, binding, oracle)`。oracle 提供 `origin`（获准业务 origin）、`authenticatedSelector`（已登录业务标记）、`loginSelector`（登录页标记）；选择器来自刚观察到的页面。它只读取当前指定 Page 的 URL 和两个元素可见性，返回上述 observation，不返回页面文本或 URL。将返回值写入本地 observation 文件后运行诊断脚本。连接/权限错误保留工具原始错误类别并记录对应 connection 状态；适配器不捕获并伪装成认证失败。跨域 SSO 阶段 target-unconfirmed 会阻止业务动作，用户完成登录回到业务 origin 后再观察。

执行无法继续时自动进入[局部静态诊断](web-blocked-analysis.md)，使用当前获准页面或已有脱敏产物；诊断不解除原测试阻塞。
