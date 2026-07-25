# 跨平台说明

在 Windows、PowerShell、非 POSIX shell，或缺少 `du/find/head/wc` 与行内环境变量语法时读取本文件。

## 输出目录

优先指定明确可写目录：

```bash
python3 <skill-dir>/scripts/reverse_android_apps.py <package-or-apk> --out <out-dir>
```

默认输出使用 Python `tempfile.gettempdir()`：

- macOS：通常是 `/var/folders/...` 或 `/private/tmp`
- Linux：通常是 `/tmp`
- Windows：通常是 `%TEMP%`

## Python 命令

使用实际存在的 launcher：

```bash
python3 <script> ...
python <script> ...
py -3 <script> ...
```

脚本启动子 Python 进程时优先使用 `sys.executable`。

## PowerShell 工具检查

```powershell
Get-Command jadx, apktool, adb -ErrorAction SilentlyContinue
Get-Command aapt, apksigner -ErrorAction SilentlyContinue
Get-Command nm, readelf, objdump, xxd, strings -ErrorAction SilentlyContinue
Get-Command llvm-readelf, llvm-objdump, llvm-nm -ErrorAction SilentlyContinue
```

检查 Windows Android SDK build-tools：

```powershell
Get-ChildItem "$env:ANDROID_HOME\build-tools" -ErrorAction SilentlyContinue
Get-ChildItem "$env:ANDROID_SDK_ROOT\build-tools" -ErrorAction SilentlyContinue
Get-ChildItem "$env:LOCALAPPDATA\Android\Sdk\build-tools" -ErrorAction SilentlyContinue
```

## PowerShell 验证等价命令

POSIX：

```bash
du -sh <output>/*_jadx/sources/
find <output> -path "*/resources/AndroidManifest.xml"
find <output>/*_jadx/sources -name "*.java" | head
```

PowerShell：

```powershell
Get-ChildItem <output> -Recurse -Directory -Filter sources
Get-ChildItem <output> -Recurse -Filter AndroidManifest.xml
Get-ChildItem <output> -Recurse -Filter *.java | Select-Object -First 20
```

## 行内环境变量

POSIX：

```bash
PYTHONPYCACHEPREFIX=<temp-dir>/android-static-app-reverse-pycache python3 -m py_compile scripts/reverse_android_apps.py scripts/find_static_anchors.py scripts/inventory_static_artifacts.py
```

PowerShell：

```powershell
$env:PYTHONPYCACHEPREFIX="$env:TEMP\android-static-app-reverse-pycache"
python -m py_compile scripts/reverse_android_apps.py scripts/find_static_anchors.py scripts/inventory_static_artifacts.py
Remove-Item Env:PYTHONPYCACHEPREFIX
```

## Native 工具 fallback

Windows 上优先使用 Git Bash/WSL 执行 GNU 风格命令；否则使用 Android NDK LLVM 工具：

```text
%ANDROID_HOME%\ndk\<version>\toolchains\llvm\prebuilt\windows-x86_64\bin
```

没有 `xxd` 时可用 PowerShell `Format-Hex` 快速检查；需要精确 offset/length 时优先使用短 Python byte-read 脚本。
