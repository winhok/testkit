# 工具与命令

选择可选工具、定位 Android SDK build-tools、设置脚本参数或运行 APKiD/apkleaks/元数据命令时读取本文件。

## 可选工具检查

```bash
apktool --version
vineflower --help
d2j-dex2jar --help || d2j-dex2jar.sh --help
aapt dump badging <apk>
apksigner verify --print-certs <apk>
apkid --version
apkleaks --help
androguard --version
```

Homebrew 安装使用 `d2j-dex2jar`，手动安装通常使用 `d2j-dex2jar.sh`。缺少可选工具时按名称报告；剩余静态产物能满足需求时继续。任务中不得自行安装逆向工具。

## Android SDK build-tools

`aapt/aapt2/apksigner` 不在 `PATH` 不等于不可用，还要检查：

```bash
$ANDROID_HOME/build-tools
$ANDROID_SDK_ROOT/build-tools
~/Library/Android/sdk/build-tools
```

优先使用最新已安装版本及绝对路径：

```bash
~/Library/Android/sdk/build-tools/<version>/aapt dump badging <apk>
~/Library/Android/sdk/build-tools/<version>/apksigner verify --print-certs <apk>
```

Windows 还要检查 `%ANDROID_HOME%\build-tools`、`%ANDROID_SDK_ROOT%\build-tools` 和 `%LOCALAPPDATA%\Android\Sdk\build-tools`；PowerShell 使用 `Get-Command aapt, apksigner`。

## 脚本命令变体

```bash
python3 <skill-dir>/scripts/reverse_android_apps.py com.example.app --out <out-dir>
python3 <skill-dir>/scripts/reverse_android_apps.py sample=com.example.app --out <out-dir> --serial <adb-serial>
python3 <skill-dir>/scripts/reverse_android_apps.py sample=<path-to-app.apk> --out <out-dir>
python3 <skill-dir>/scripts/reverse_android_apps.py sample=<path-to-app.apk> --jadx-mode fallback --out <out-dir>
python3 <skill-dir>/scripts/reverse_android_apps.py com.example.app --out <out-dir> --with-apktool --apktool-framework-dir <writable-framework-dir>
python3 <skill-dir>/scripts/reverse_android_apps.py com.example.app --out <out-dir> --with-apktool --with-apkid --with-apkleaks --with-vineflower
python3 <skill-dir>/scripts/reverse_android_apps.py sample=<path-to-large.apk> --out <out-dir> --with-apkid --with-apkleaks --parallel --jadx-timeout 600 --apkleaks-timeout 300
```

大 APK 同时需要 apktool/APKiD/apkleaks 时使用 `--parallel`。JADX 或 apkleaks 卡住时读取 `large-apk-handling.md`。

## APKiD 与 apkleaks

APKiD 识别 compiler、obfuscator、packer 和 anti-analysis 信号；需要加固/security/coverage 分析或静态完整性不明时运行：

```bash
apkid <apk-file-or-dir>
```

apkleaks 使用维护的 pattern database 检测硬编码 URL、API key、Firebase/AWS/Google Maps/OAuth/private key 等；需要 endpoint/secret/security 分析时运行：

```bash
apkleaks -f <apk-file> -o <output>/apkleaks-report.txt
```

报告前过滤 SDK example URL、生成常量等误报，并脱敏具体凭证值。

## Native 工具 fallback

GNU `readelf/objdump` 不可用时尝试：

```bash
command -v llvm-readelf llvm-objdump llvm-nm
```

Windows 的 Android NDK LLVM 通常位于：

```text
%ANDROID_HOME%\ndk\<version>\toolchains\llvm\prebuilt\windows-x86_64\bin
```
