# Manifest、WebView、IPC、存储与加密排查

用户要求安全评审、exported component、WebView、deep link、存储、加密、TLS 或 Android 配置时读取本文件。

## 搜索

```bash
python3 <skill-dir>/scripts/find_static_anchors.py <jadx-dir>/sources --ipc --webview --crypto --storage --dynamic --include-namespace <app.namespace>
python3 <skill-dir>/scripts/find_static_anchors.py <apktool-dir> --ipc --webview --crypto --storage --native
```

## Manifest 与资源

检查 permission、exported `activity/service/receiver/provider`、intent filter、backup/debuggable/network-security、deep link 和 WebView 组件。

关注 Android 版本相关问题：

- 有 intent filter 的组件是否显式声明 `android:exported`
- `PendingIntent` mutability flag
- foreground service type
- legacy external storage flag

自定义 permission 缺少 protection level 或为 `normal` 时，先视为弱保护；signature permission 可降低可利用性。

## 网络安全与 Deep Link

Network security config 检查明文流量、release trust anchor 中的 `certificates src="user"`、敏感 API 缺少 pinning，以及削弱生产行为的 debug override。

Deep link 记录 scheme/host/path、`autoVerify`、接受的 query 参数，以及 handler 在使用 URL、intent、文件或 WebView sink 前是否校验。

## WebView

检查 `setJavaScriptEnabled(true)`、`addJavascriptInterface`、file access、universal file URL access、mixed content、SSL error override、`loadUrl`、`loadDataWithBaseURL`，以及未经校验的 deep-link/intent 数据流入 WebView sink。

不得仅凭 setting 报告漏洞；必须追踪 source → validation → sink，否则标为“需动态确认”。

## 证据规则

- 每条结论记录文件路径和行号。
- 直接证据与推断分开。
- 过滤第三方库噪音；除非问题正是 SDK 配置，否则聚焦应用代码。
- 被混淆、reflection、JNI/native、RASP 或运行时行为阻断时，不给最终严重度。
