---
name: android-static-app-reverse
description: "Static Android app reverse-analysis workflow for exporting APKs from ADB, handling split APKs, decompiling with JADX/apktool/Vineflower, inventorying static artifacts, detecting packers, extracting API endpoints, and producing evidence-labeled reports. Use when the user asks to reverse engineer, decompile, inspect APKs, pull installed apps, dump packages, run jadx/apktool/smali/vineflower/dex2jar, analyze /tmp APK or JADX outputs, detect Android packers/native code, extract Retrofit/OkHttp/Volley/custom HTTP endpoints, find leaked static secrets, trace Android call flows, or says '用jadx逆向', '从手机导出安装包', '提取接口', '查包名并反编译', '检测加固', '提取泄露'."
---

# Android Static App Reverse

IRON LAW: STATIC ANALYSIS ONLY. Never bypass licensing, authentication, encryption, payments, anti-cheat, or access controls; do not extract private user data or credentials.

## Workflow

Copy this checklist and check off items as you complete them:

```
Android Static App Reverse Progress:

- [ ] Step 1: Scope and safety check ⚠️ REQUIRED
  - [ ] 1.1 Identify requested apps, package IDs, or local APK folders
  - [ ] 1.2 Confirm the task is static reverse engineering only
  - [ ] 1.3 Decide output layout: timestamped safe output or explicit /tmp flat paths
- [ ] Step 2: Preflight ⛔ BLOCKING
  - [ ] 2.1 Check `jadx --version`
  - [ ] 2.2 Check optional tools only when needed; load `references/tooling-and-commands.md` for command variants, APKiD/apkleaks, and build-tools lookup
  - [ ] 2.3 If pulling from device, check `adb devices`; prefer `--serial` or ANDROID_SERIAL when multiple devices exist
  - [ ] 2.4 Resolve app labels/names to package IDs
  - [ ] 2.5 For APKs >50MB or >10 DEX files, plan to use `--parallel --jadx-timeout 600 --apkleaks-timeout 300`
  - [ ] 2.6 For Windows/PowerShell or non-POSIX shells, load `references/cross-platform.md`
- [ ] Step 3: Extract and decompile
  - [ ] 3.1 Pull all split APKs with `adb shell pm path` and `adb pull`
  - [ ] 3.2 Run JADX on device APKs or local APK/XAPK/JAR/AAR inputs
  - [ ] 3.3 Run apktool with a writable framework path when manifest/resources/smali precision matters
  - [ ] 3.4 Run dex2jar + Vineflower for secondary Java output when requested or when JADX needs cross-checking
- [ ] Step 4: Verify outputs ⚠️ REQUIRED
  - [ ] 4.1 Confirm APK/JADX directories and `sources/`
  - [ ] 4.2 For APK/XAPK, confirm `resources/AndroidManifest.xml` or document why absent
  - [ ] 4.3 If apktool ran, confirm decoded `AndroidManifest.xml`, `res/`, and `smali*/`
  - [ ] 4.4 If packer/security/coverage analysis is requested or completeness is uncertain, run APKiD; otherwise run lightweight artifact inventory or document skip reason
  - [ ] 4.5 If endpoint/secret/security analysis is requested, run apkleaks; if unavailable or timed out, confirm fallback ran
  - [ ] 4.6 Record hashes, package/version metadata, and signing/certificate status when available
  - [ ] 4.7 If JADX timed out, verify `sources/` has usable content before continuing
- [ ] Step 5: Analyze requested surface area
  - [ ] 5.1 For API/network extraction, load `references/endpoint-extraction.md`
  - [ ] 5.2 For manifest/WebView/storage/crypto/deep-link review, load `references/security-triage.md`
  - [ ] 5.3 For packer/runtime DEX/native/Unity/Flutter/RN/Cordova/Xamarin, load `references/native-packer-triage.md`
  - [ ] 5.4 For native-held static configuration, JNI-returned values, or client-side secret triage, load `references/native-config-extraction.md`
- [ ] Step 6: Report concise results with coverage and confidence labels
```

## Step 1: Scope and Safety Check

Ask:
- Is the user asking for static APK/source/resource inspection, or runtime bypass/cracking?
- Did the user provide app labels, package IDs, local APK paths, or a mix?
- Are output paths likely to overwrite existing work?

Refuse or narrow requests for credential extraction, payment bypass, DRM/license bypass, cheating, malware modification, or exfiltrating private app data. Continue for benign static analysis, compatibility research, hook target discovery, logging/debugging, or security review of apps the user is authorized to inspect.

Confirmation gate: before using `--force`, state which directories will be replaced and get explicit user approval unless the user already asked to overwrite.

## Step 2: Preflight ⛔ BLOCKING

Run:

```bash
jadx --version
```

Load `references/tooling-and-commands.md` when selecting optional tools, resolving Android SDK build-tools outside `PATH`, or choosing APKiD/apkleaks/metadata commands.

Optional tool families: `apktool`, `vineflower`, dex2jar (`d2j-dex2jar` or `d2j-dex2jar.sh`), `aapt`/`aapt2`, `apksigner`, `apkid`, `apkleaks`, and `androguard`.

For native configuration extraction, also check binary inspection tools and load `references/native-config-extraction.md`:

```bash
command -v nm readelf objdump xxd strings
command -v llvm-readelf llvm-objdump || true  # optional LLVM fallback
```

Default mode: for plain decompile/export requests, produce APK/JADX inventory first. Run APKiD/apkleaks when the user asks for security, packer, endpoint, secret, or coverage analysis, or when static completeness is uncertain.

Tool priority for packer detection: APKiD > inventory script keyword matching; fall back to inventory only when APKiD is unavailable.

Tool priority for secret/URL leak detection: apkleaks > find_static_anchors.py regex; fall back to the bundled script only when apkleaks is unavailable or times out.

If pulling from a phone, run:

```bash
adb devices
```

ADB parsing rule: treat a device as authorized only when the whitespace-delimited second column is `device`; do not depend on a literal tab. If multiple devices exist, use `--serial <serial>` or set `ANDROID_SERIAL`.

If the bundled script's ADB preflight fails but manual `adb devices` looks usable, do not stop. Try the manual fallback:

```bash
adb -s <serial> shell pm path <package>
adb -s <serial> pull <remote-apk> <apk-dir>
```

Then run the script on the pulled local APK directory.

For app names rather than package IDs, resolve against local device package data. If an app name is ambiguous, ask for the package ID instead of guessing.

## Step 3: Extract and Decompile

Prefer bundled scripts for repeatable work:

```bash
python3 <skill-dir>/scripts/reverse_android_apps.py com.example.app --out <out-dir>
python3 <skill-dir>/scripts/reverse_android_apps.py sample=<path-to-app.apk> --out <out-dir>
python3 <skill-dir>/scripts/reverse_android_apps.py com.example.app --out <out-dir> --with-apktool --with-vineflower
python3 <skill-dir>/scripts/reverse_android_apps.py com.example.app --out <out-dir> --with-apkid --with-apkleaks
```

If `--out` is omitted, the script writes to the system temp directory (`tempfile.gettempdir()`). Load `references/tooling-and-commands.md` for full command variants such as `--serial`, `--jadx-mode fallback`, `--apktool-framework-dir`, and combined scanner runs. Use `references/cross-platform.md` for Windows/PowerShell command equivalents.

For APKs >50MB or >10 DEX files, use `--parallel`, `--jadx-timeout 600`, and `--apkleaks-timeout 300`; load `references/large-apk-handling.md` if output stalls or partial JADX output needs triage.

When editing scripts, validate syntax before delivery:

```bash
PYTHONPYCACHEPREFIX=<temp-dir>/android-static-app-reverse-pycache python3 -m py_compile scripts/reverse_android_apps.py scripts/find_static_anchors.py scripts/inventory_static_artifacts.py
```

apktool rule: always use a writable framework directory. The script defaults to `<apktool-output>/framework`; manual commands should use:

```bash
apktool d -f -p <writable-framework-dir> <apk> -o <decoded-dir>
```

JADX result tiers:
- Exit `0`: full decompilation success if `sources/` and expected resources exist.
- Exit `3`: partial decompilation errors; continue analysis when `sources/` and key resources exist.
- Missing `sources/`, missing key DEX output, or absent manifest/resources for APK work: blocking unless the user only needs non-Java artifacts.

Best-practice ladder:
1. Start with JADX for readable Java/Kotlin-equivalent source.
2. Use apktool for decoded manifest, resources, assets, and smali; do not rely on JADX resources alone for manifest/resource security review.
3. Use Vineflower via dex2jar as a second Java view when JADX output is incomplete, suspicious, or heavily restructured.
4. If JADX output is inconsistent, retry with `--jadx-mode simple` or `--jadx-mode fallback`.
5. If Java decompilers disagree or fail, analyze smali and label Java-level conclusions as inferred.

## Step 4: Verify Outputs ⚠️ REQUIRED

Run:

```bash
du -sh <output>/*_apks <output>/*_jadx
find <output> -path "*/resources/AndroidManifest.xml"
rg -n "^<manifest|package=" <output>/*_jadx/resources/AndroidManifest.xml
```

For PowerShell or non-POSIX shells, load `references/cross-platform.md`.

For local APK metadata, prefer Android build-tools when available:

```bash
<build-tools>/aapt dump badging <apk>
<build-tools>/apksigner verify --verbose --print-certs <apk>
```

If `apksigner` fails, report the exact failure. Then run `jarsigner -verify -verbose -certs <apk>` as a fallback to recover JAR signer subject, weak algorithm warnings, missing v2/v3 signature hints, or "signature stripped" evidence. Label the APK as "does not verify" when `apksigner` fails even if `jarsigner` can read a certificate subject.

When packer/security/coverage analysis is requested or completeness is uncertain, use APKiD first. If APKiD is unavailable, fall back to artifact inventory:

```bash
python3 <skill-dir>/scripts/inventory_static_artifacts.py <apk-dir-or-file> <jadx-dir> [<apktool-dir-if-present>]
```

When endpoint/secret/security analysis is requested, use apkleaks first. It can hang on large multi-DEX APKs; use the script's `--apkleaks-timeout` and load `references/large-apk-handling.md` for stall triage.

If apkleaks is unavailable or failed/timed out, fall back to:

```bash
python3 <skill-dir>/scripts/find_static_anchors.py <jadx-dir>/sources --urls --auth --include-namespace <app.namespace>
```

Ask:
- Does each app have the expected split APK count?
- Does each JADX directory contain `sources/`?
- If apktool ran, does output contain decoded `AndroidManifest.xml`, `res/`, and one or more `smali*` directories?
- If Vineflower ran, does `<output>/<app>/vineflower/sources/` or `<output>/<app>_vineflower/sources/` contain Java output?
- Does APKiD or artifact inventory show packer/protector hints, runtime-loaded DEX/JAR/APK, Unity IL2CPP, Flutter, React Native Hermes, Cordova, Xamarin, or important native libraries?
- Are `aapt`/`apksigner` unavailable? If yes, state the signing/provenance gap.
- Did `jadx` return exit code 3, and if so, are usable outputs still present?

## Step 5: Analyze

Load references only for the requested analysis:
- API extraction, network stacks, hook targets, or feature tracing -> `references/endpoint-extraction.md`
- Manifest, WebView, IPC, storage, crypto, deep links, or Android config review -> `references/security-triage.md`
- Packers, runtime DEX, native/JNI, Unity IL2CPP, Flutter/RN/Cordova/Xamarin -> `references/native-packer-triage.md`
- Static configuration values returned from native methods, JNI string/int/long functions, encoded `.rodata`, or client-held secret classification -> `references/native-config-extraction.md`
- Optional tool commands, Android SDK build-tools lookup, APKiD/apkleaks command details, or script variants -> `references/tooling-and-commands.md`
- Cross-platform path, temp directory, PowerShell, or command-equivalent questions -> `references/cross-platform.md`

Record file paths and line numbers for every claim. Separate direct evidence from inference.

## Step 6: Report

Use this table:

| App | Package | APK dir | JADX dir | Apktool dir | Vineflower dir | Status |
|---|---|---|---|---|---|---|

Mention `jadx` errors plainly: "exit code 3 means partial decompilation errors; generated sources/resources may still be usable." Do not overstate completeness.

If API analysis was requested, add:
- **High-confidence endpoints**: method/path/source/call flow
- **Network stack**: Retrofit, OkHttp, Volley, HttpURLConnection, custom HttpManager, WebView, or mixed
- **Auth pattern**: header/cookie/token scheme only, values redacted
- **Open questions**: obfuscated or unresolved flows that need runtime logs or focused tracing

Classify findings as:
- **Confirmed**: full source-to-sink trace and validation evidence
- **Likely**: strong static path with at most one unresolved hop
- **Needs Dynamic Confirmation**: plausible hit blocked by obfuscation, reflection, JNI/native code, RASP, or runtime-only behavior

Add a coverage statement: static scope, dynamic scope, app namespace/library filtering, frameworks detected, packer/protector indicators, runtime-loaded DEX status, native code status, obfuscation level, missing tools, and findings needing runtime confirmation.

## Anti-Patterns

- Do not run multiple `adb` daemon-starting commands in parallel; serialize ADB work.
- Do not assume `/tmp` means a real directory on macOS; note that it usually points to `/private/tmp`.
- Do not stop at script ADB preflight failure when manual `adb shell pm path` and `adb pull` can recover.
- Do not decompile only `base.apk` when split APKs exist.
- Do not stop the whole batch just because `jadx` exits 3 for one app.
- Do not let apktool write to a non-writable default framework directory in sandboxed runs.
- Do not trust pretty Java blindly; cross-check decompiler disagreements with smali or a second decompiler.
- Do not report third-party SDK/library matches as app findings unless app-owned code configures or consumes them.
- Do not report bare grep hits as vulnerabilities; validate reachability and sanitization first.
- Do not dump auth token values, cookies, private IDs, or credentials from source hits.
- Do not use Fernflower; Vineflower replaces it for this workflow.
- Do not overwrite prior reverse output unless the user approved it.
- Do not skip APKiD for packer/security/coverage analysis when it is available.
- Do not skip apkleaks for endpoint/secret/security analysis when it is available.
- Do not report apkleaks raw output without filtering false positives and redacting secrets.
- Do not treat APKiD "anti-debug" or "anti-vm" findings as proof the app is malicious.

## Pre-Delivery Checklist

- [ ] No unsupported bypass/cracking/private-data request was performed
- [ ] Required tools and optional missing-tool gaps are reported
- [ ] ADB device selection used whitespace-column parsing, `--serial`, or ANDROID_SERIAL when relevant
- [ ] Manual `adb shell pm path` + `adb pull` fallback was attempted or explicitly not needed after ADB preflight trouble
- [ ] Each requested app has an APK directory or a documented reason it was skipped
- [ ] APK/split SHA-256 hashes are captured for serious reports
- [ ] `aapt`/`apksigner` metadata is captured from PATH or Android SDK build-tools, or the signing/provenance gap is explicitly stated
- [ ] If `apksigner` failed, exact failure text is reported and `jarsigner` fallback was used when available
- [ ] APKiD was run when packer/security/coverage analysis was requested or completeness was uncertain; otherwise the skip reason is stated
- [ ] apkleaks was run when endpoint/secret/security analysis was requested; otherwise the skip reason is stated
- [ ] Each decompiled target has `sources/`; APK/XAPK targets also have manifest/resources or a documented exception
- [ ] JADX exit code `3` is labeled as partial success only when usable outputs exist
- [ ] JADX timeout (if triggered) is documented; output usability was verified before continuing
- [ ] Apktool used a writable framework path and its output/status is reported if used
- [ ] Static artifact inventory was run or explicitly skipped with reason
- [ ] API/auth search results prioritize app-owned namespaces and redact concrete secret values
- [ ] Call-flow/security claims cite source files or are labeled `Confirmed`, `Likely`, or `Needs Dynamic Confirmation`
- [ ] Third-party library noise was filtered or explicitly called out as informational
- [ ] Coverage gaps are documented for obfuscation, JNI/native code, dynamic loading, RASP, incomplete decompilation, and missing tools
- [ ] For large APKs (>50MB), `--parallel` plus `--jadx-timeout`/`--apkleaks-timeout` were used to avoid indefinite hangs
- [ ] dex2jar command name was verified (`d2j-dex2jar` for brew, `d2j-dex2jar.sh` for manual install)
