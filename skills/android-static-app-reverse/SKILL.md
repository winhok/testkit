---
name: android-static-app-reverse
description: Android 应用纯静态逆向分析工作流，支持从 ADB 导出 APK、处理 split APK、使用 JADX/apktool/Vineflower 反编译、盘点静态产物、检测加固、提取 API endpoint 并生成带证据和置信度的报告。当用户要求「用 JADX 逆向」「从手机导出安装包」「查包名并反编译」「提取接口」「检测加固」「分析 APK/JADX 输出」「检查 Retrofit/OkHttp/Volley」「查找静态泄漏」「追踪 Android 调用链」时使用。
---

# Android 应用静态逆向分析

## 铁律

只做静态分析。不得绕过 license、认证、加密、支付、反作弊或访问控制；不得提取私人用户数据或凭证。

## 工作流

```text
Android 静态逆向进度：

- [ ] 步骤 1：范围与安全检查 ⚠️ 必做
  - [ ] 1.1 确认应用、包名或本地 APK 目录
  - [ ] 1.2 确认任务仅包含静态逆向
  - [ ] 1.3 选择带时间戳安全目录或明确的临时输出路径
- [ ] 步骤 2：预检 ⛔ 阻断项
  - [ ] 2.1 检查 `jadx --version`
  - [ ] 2.2 仅按需检查可选工具
  - [ ] 2.3 从设备导出时检查 `adb devices`；多设备使用 `--serial` 或 `ANDROID_SERIAL`
  - [ ] 2.4 将应用名称解析为包名
  - [ ] 2.5 APK >50MB 或 DEX >10 时启用并行和超时
  - [ ] 2.6 Windows/PowerShell 环境读取跨平台说明
- [ ] 步骤 3：导出与反编译
  - [ ] 3.1 用 `adb shell pm path` + `adb pull` 拉取全部 split APK
  - [ ] 3.2 对 APK/XAPK/JAR/AAR 运行 JADX
  - [ ] 3.3 需要精确 manifest/resource/smali 时运行 apktool
  - [ ] 3.4 需要交叉验证时运行 dex2jar + Vineflower
- [ ] 步骤 4：验证产物 ⚠️ 必做
  - [ ] 4.1 验证 APK、JADX 目录及 `sources/`
  - [ ] 4.2 APK/XAPK 验证 `resources/AndroidManifest.xml`
  - [ ] 4.3 apktool 验证 manifest、`res/` 和 `smali*/`
  - [ ] 4.4 按需运行 APKiD 或静态产物盘点
  - [ ] 4.5 API/secret/security 分析按需运行 apkleaks 及 fallback
  - [ ] 4.6 记录 hash、包/版本元数据和签名状态
- [ ] 步骤 5：分析用户要求的范围
- [ ] 步骤 6：用覆盖范围和置信度标签报告结果
```

## 步骤 1：范围与安全

确认用户要求的是 APK/source/resource 静态检查，而不是运行时绕过或破解。涉及凭证提取、支付/DRM/license 绕过、作弊、恶意修改或私人数据外传时，拒绝或收窄范围。已授权应用的兼容性研究、hook target 定位、日志调试和安全评审可以继续。

使用 `--force` 前必须列出将被替换的目录并取得明确授权；用户已明确要求覆盖时除外。

## 步骤 2：预检

```bash
jadx --version
```

选择可选工具、定位 Android SDK build-tools 或运行 APKiD/apkleaks 时读取 [tooling-and-commands.md](references/tooling-and-commands.md)。可选工具包括 `apktool`、`vineflower`、dex2jar、`aapt/aapt2`、`apksigner`、`apkid`、`apkleaks` 和 `androguard`。

提取 native 配置时读取 [native-config-extraction.md](references/native-config-extraction.md)，并检查：

```bash
command -v nm readelf objdump xxd strings
command -v llvm-readelf llvm-objdump || true
```

普通导出/反编译默认先生成 APK/JADX 盘点。用户要求安全、加固、endpoint、secret 或覆盖度分析，或完整性不确定时，再运行 APKiD/apkleaks。

- 加固检测优先级：APKiD > inventory script。
- secret/URL 泄漏检测优先级：apkleaks > `find_static_anchors.py`。

从手机导出时：

```bash
adb devices
```

只有按空白分列后的第二列等于 `device` 才算已授权设备。多个设备必须使用 `--serial <serial>` 或 `ANDROID_SERIAL`。

脚本 ADB 预检失败但手动 ADB 可用时，不得直接停止：

```bash
adb -s <serial> shell pm path <package>
adb -s <serial> pull <remote-apk> <apk-dir>
```

随后对本地 APK 目录运行脚本。应用名称有歧义时询问包名，不得猜测。

## 步骤 3：导出与反编译

优先使用内置脚本：

```bash
python3 <skill-dir>/scripts/reverse_android_apps.py com.example.app --out <out-dir>
python3 <skill-dir>/scripts/reverse_android_apps.py sample=<path-to-app.apk> --out <out-dir>
python3 <skill-dir>/scripts/reverse_android_apps.py com.example.app --out <out-dir> --with-apktool --with-vineflower
python3 <skill-dir>/scripts/reverse_android_apps.py com.example.app --out <out-dir> --with-apkid --with-apkleaks
```

省略 `--out` 时写入 `tempfile.gettempdir()`。完整命令变体见 [tooling-and-commands.md](references/tooling-and-commands.md)，跨平台命令见 [cross-platform.md](references/cross-platform.md)。

APK >50MB 或 DEX >10 时使用 `--parallel --jadx-timeout 600 --apkleaks-timeout 300`；卡住或只有部分输出时读取 [large-apk-handling.md](references/large-apk-handling.md)。

修改脚本后验证语法：

```bash
PYTHONPYCACHEPREFIX=<temp-dir>/android-static-app-reverse-pycache \
  python3 -m py_compile scripts/reverse_android_apps.py \
  scripts/find_static_anchors.py scripts/inventory_static_artifacts.py
```

apktool 必须使用可写 framework 目录：

```bash
apktool d -f -p <writable-framework-dir> <apk> -o <decoded-dir>
```

JADX 结果分级：

- exit `0`：`sources/` 和预期资源存在时视为完整成功。
- exit `3`：部分反编译错误；有可用 source 和关键资源时可以继续。
- 缺少 `sources/`、关键 DEX 输出，或 APK 缺少 manifest/resource：默认阻断。

工具顺序：

1. 先用 JADX 获取可读 Java/Kotlin 等价源码。
2. 用 apktool 获取精确 manifest、resource、asset 和 smali。
3. JADX 不完整或可疑时，用 dex2jar + Vineflower 提供第二视图。
4. JADX 结果不一致时重试 `--jadx-mode simple` 或 `fallback`。
5. Java 反编译器冲突或失败时分析 smali，并把 Java 层结论标为推断。

## 步骤 4：验证产物

```bash
du -sh <output>/*_apks <output>/*_jadx
find <output> -path "*/resources/AndroidManifest.xml"
rg -n "^<manifest|package=" <output>/*_jadx/resources/AndroidManifest.xml
```

PowerShell 等价命令见 [cross-platform.md](references/cross-platform.md)。

本地 APK 元数据优先使用 build-tools：

```bash
<build-tools>/aapt dump badging <apk>
<build-tools>/apksigner verify --verbose --print-certs <apk>
```

`apksigner` 失败时报告原始错误，再用 `jarsigner -verify -verbose -certs <apk>` 补充证书主体和弱算法等证据。即使 jarsigner 能读证书，只要 apksigner 失败，仍标记为“验证不通过”。

需要加固/security/coverage 分析或完整性不明时优先 APKiD；不可用时：

```bash
python3 <skill-dir>/scripts/inventory_static_artifacts.py \
  <apk-dir-or-file> <jadx-dir> [<apktool-dir-if-present>]
```

API/secret/security 分析优先 apkleaks；不可用、失败或超时时：

```bash
python3 <skill-dir>/scripts/find_static_anchors.py <jadx-dir>/sources \
  --urls --auth --include-namespace <app.namespace>
```

验证每个应用的 split 数量、`sources/`、apktool manifest/res/smali、Vineflower Java 输出、加固/native/dynamic DEX/framework 信号、签名证据和 JADX exit code。

## 步骤 5：按需分析

- API、network stack、hook target、调用链 → [endpoint-extraction.md](references/endpoint-extraction.md)
- Manifest、WebView、IPC、storage、crypto、deep link → [security-triage.md](references/security-triage.md)
- 加固、runtime DEX、native/JNI、Unity、Flutter、RN、Cordova、Xamarin → [native-packer-triage.md](references/native-packer-triage.md)
- native 静态配置、JNI 返回值、client secret 分类 → [native-config-extraction.md](references/native-config-extraction.md)

每条结论记录文件路径和行号，并区分直接证据与推断。

## 步骤 6：报告

| App | Package | APK 目录 | JADX 目录 | Apktool 目录 | Vineflower 目录 | 状态 |
|---|---|---|---|---|---|---|

如有 JADX exit `3`，明确说明它表示部分反编译错误，已有 source/resource 可能仍可使用，不得夸大完整性。

API 分析附加：

- 高置信 endpoint：method/path/source/call flow
- network stack：Retrofit、OkHttp、Volley、HttpURLConnection、自定义 manager、WebView 或混合
- auth pattern：只说明 header/cookie/token 方案，值必须脱敏
- 待确认：因混淆、reflection、JNI/native、RASP 或运行时行为无法闭合的链路

置信度统一使用：

- `已确认（Confirmed）`：source-to-sink 完整且有验证证据。
- `很可能（Likely）`：静态路径充分，最多一个未解析跳点。
- `需动态确认（Needs Dynamic Confirmation）`：被混淆、reflection、JNI/native、RASP 或运行时行为阻断。

最后说明静态/动态范围、namespace/library 过滤、framework、加固信号、runtime DEX、native 状态、混淆程度、缺失工具和动态确认项。

## 反模式

- ADB 工作必须串行，不并行启动多个 daemon 命令。
- 不把 macOS `/tmp` 当成独立真实目录；通常指向 `/private/tmp`。
- split APK 存在时不得只反编译 `base.apk`。
- 单个应用 JADX exit `3` 不得导致整批停止。
- apktool 不得写入不可写的默认 framework 目录。
- 不盲信漂亮的 Java；冲突时用 smali 或第二反编译器复核。
- 第三方 SDK 命中只有被应用自身配置或使用时才能作为应用发现。
- 裸 grep 命中不得直接报告为漏洞。
- 不输出 token、Cookie、私人 ID 或凭证值。
- 不使用 Fernflower；本流程使用 Vineflower。
- 未获授权不得覆盖既有输出。
- 符合触发条件且工具可用时，不得跳过 APKiD/apkleaks。
- apkleaks 原始输出必须先去误报和脱敏。
- APKiD 的 anti-debug/anti-vm 不等于恶意应用证据。

## 交付前检查

- [ ] 未执行越权绕过、破解或私人数据请求
- [ ] 已报告必需工具和可选工具缺口
- [ ] ADB 多设备选择明确
- [ ] ADB 预检异常时已尝试或明确无需手动 fallback
- [ ] 每个目标都有 APK 目录或跳过原因
- [ ] 严肃报告包含 APK/split SHA-256
- [ ] 已记录 aapt/apksigner 元数据或签名证据缺口
- [ ] 按需运行 APKiD、apkleaks 和静态 inventory
- [ ] 每个反编译目标有可用 `sources/`，APK/XAPK 有 manifest/resource 或例外说明
- [ ] JADX exit `3` 和 timeout 已按部分结果处理
- [ ] apktool 使用可写 framework path
- [ ] API/auth 搜索优先应用 namespace 且 secret 已脱敏
- [ ] 调用链和安全结论带来源或置信度标签
- [ ] 已过滤第三方库噪音
- [ ] 已说明混淆、JNI/native、动态加载、RASP、不完整反编译和缺失工具造成的覆盖缺口
- [ ] 大 APK 使用并行和明确 timeout
- [ ] dex2jar 命令名已按安装方式验证
