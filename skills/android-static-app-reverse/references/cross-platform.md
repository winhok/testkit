# Cross-Platform Notes

Use this reference when running the Android static reverse workflow on Windows, PowerShell, non-POSIX shells, or when POSIX utilities such as `du`, `find`, `head`, `wc`, or inline environment variables are unavailable.

## Output Directories

Prefer an explicit writable output directory:

```bash
python3 <skill-dir>/scripts/reverse_android_apps.py <package-or-apk> --out <out-dir>
```

Default script output uses Python `tempfile.gettempdir()`:
- macOS commonly resolves to `/var/folders/...` or `/private/tmp`
- Linux commonly resolves to `/tmp`
- Windows commonly resolves to `%TEMP%`

## Python Command

Use whichever Python launcher exists:

```bash
python3 <script> ...
python <script> ...
py -3 <script> ...
```

Inside scripts, prefer `sys.executable` for child Python processes.

## PowerShell Tool Checks

```powershell
Get-Command jadx, apktool, adb -ErrorAction SilentlyContinue
Get-Command aapt, apksigner -ErrorAction SilentlyContinue
Get-Command nm, readelf, objdump, xxd, strings -ErrorAction SilentlyContinue
Get-Command llvm-readelf, llvm-objdump, llvm-nm -ErrorAction SilentlyContinue
```

Check Android SDK build-tools on Windows:

```powershell
Get-ChildItem "$env:ANDROID_HOME\build-tools" -ErrorAction SilentlyContinue
Get-ChildItem "$env:ANDROID_SDK_ROOT\build-tools" -ErrorAction SilentlyContinue
Get-ChildItem "$env:LOCALAPPDATA\Android\Sdk\build-tools" -ErrorAction SilentlyContinue
```

## PowerShell Verification Equivalents

POSIX:

```bash
du -sh <output>/*_jadx/sources/
find <output> -path "*/resources/AndroidManifest.xml"
find <output>/*_jadx/sources -name "*.java" | head
```

PowerShell:

```powershell
Get-ChildItem <output> -Recurse -Directory -Filter sources
Get-ChildItem <output> -Recurse -Filter AndroidManifest.xml
Get-ChildItem <output> -Recurse -Filter *.java | Select-Object -First 20
```

## Inline Environment Variables

POSIX:

```bash
PYTHONPYCACHEPREFIX=<temp-dir>/android-static-app-reverse-pycache python3 -m py_compile scripts/reverse_android_apps.py scripts/find_static_anchors.py scripts/inventory_static_artifacts.py
```

PowerShell:

```powershell
$env:PYTHONPYCACHEPREFIX="$env:TEMP\android-static-app-reverse-pycache"
python -m py_compile scripts/reverse_android_apps.py scripts/find_static_anchors.py scripts/inventory_static_artifacts.py
Remove-Item Env:PYTHONPYCACHEPREFIX
```

## Native Tool Fallbacks

On Windows, prefer Git Bash/WSL for GNU-style examples when available. Otherwise use Android NDK LLVM tools under:

```text
%ANDROID_HOME%\ndk\<version>\toolchains\llvm\prebuilt\windows-x86_64\bin
```

If `xxd` is unavailable, use PowerShell `Format-Hex` for quick inspection. For exact offsets and lengths, prefer a short Python byte-read script.
