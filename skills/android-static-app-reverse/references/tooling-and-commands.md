# Tooling and Commands

Use this reference when choosing optional tools, resolving Android SDK build-tools, selecting script flags, or running APKiD/apkleaks/metadata commands. Keep the main `SKILL.md` focused on workflow decisions; use this file for command detail.

## Optional Tool Checks

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

Use `d2j-dex2jar` for brew installs and `d2j-dex2jar.sh` for manual installs. Report missing optional tools by name and continue with the best available static output when that still satisfies the request. Do not install reverse-engineering tools during the task.

## Android SDK Build-Tools Lookup

Do not report `aapt`, `aapt2`, or `apksigner` unavailable just because they are not in `PATH`. Check:

```bash
$ANDROID_HOME/build-tools
$ANDROID_SDK_ROOT/build-tools
~/Library/Android/sdk/build-tools
```

Prefer the newest installed build-tools version and run tools by absolute path:

```bash
~/Library/Android/sdk/build-tools/<version>/aapt dump badging <apk>
~/Library/Android/sdk/build-tools/<version>/apksigner verify --print-certs <apk>
```

On Windows, also check `%ANDROID_HOME%\build-tools`, `%ANDROID_SDK_ROOT%\build-tools`, and `%LOCALAPPDATA%\Android\Sdk\build-tools`; in PowerShell prefer `Get-Command aapt, apksigner`.

## Script Command Variants

```bash
python3 <skill-dir>/scripts/reverse_android_apps.py com.example.app --out <out-dir>
python3 <skill-dir>/scripts/reverse_android_apps.py sample=com.example.app --out <out-dir> --serial <adb-serial>
python3 <skill-dir>/scripts/reverse_android_apps.py sample=<path-to-app.apk> --out <out-dir>
python3 <skill-dir>/scripts/reverse_android_apps.py sample=<path-to-app.apk> --jadx-mode fallback --out <out-dir>
python3 <skill-dir>/scripts/reverse_android_apps.py com.example.app --out <out-dir> --with-apktool --apktool-framework-dir <writable-framework-dir>
python3 <skill-dir>/scripts/reverse_android_apps.py com.example.app --out <out-dir> --with-apktool --with-apkid --with-apkleaks --with-vineflower
python3 <skill-dir>/scripts/reverse_android_apps.py sample=<path-to-large.apk> --out <out-dir> --with-apkid --with-apkleaks --parallel --jadx-timeout 600 --apkleaks-timeout 300
```

Use `--parallel` for large APKs when apktool/APKiD/apkleaks are needed; those tools do not depend on JADX output. Load `large-apk-handling.md` when JADX or apkleaks stalls.

## APKiD and apkleaks

APKiD identifies compiler fingerprints such as dx/d8, obfuscators such as ProGuard/R8/DexGuard, packers such as Bangcle/Ijiami/Qihoo/Tencent Legu/SecNeo, and anti-analysis hints. Run it for packer/security/coverage analysis or when static completeness is uncertain:

```bash
apkid <apk-file-or-dir>
```

apkleaks detects hardcoded URLs, API keys, Firebase URLs, AWS keys, Google Maps keys, OAuth secrets, private keys, and custom regex patterns using a maintained pattern database. Run it for endpoint/secret/security analysis:

```bash
apkleaks -f <apk-file> -o <output>/apkleaks-report.txt
```

Filter false positives before reporting, especially SDK example URLs and generated constants. Redact concrete credential values.

## Native Tool Fallbacks

If GNU `readelf` or `objdump` is unavailable, try LLVM equivalents:

```bash
command -v llvm-readelf llvm-objdump llvm-nm
```

On Windows, Android NDK LLVM tools are commonly under:

```text
%ANDROID_HOME%\ndk\<version>\toolchains\llvm\prebuilt\windows-x86_64\bin
```
