# Large APK Handling

Use this reference when an APK is larger than 50MB, has more than 10 DEX files, JADX/apkleaks stalls, or partial decompiler output needs triage.

## Default Large APK Command

Run JADX, apktool, APKiD, and apkleaks concurrently when those tools are needed:

```bash
python3 <skill-dir>/scripts/reverse_android_apps.py com.example.app \
  --out <out-dir> \
  --with-apktool \
  --with-apkid \
  --with-apkleaks \
  --parallel \
  --jadx-timeout 600 \
  --apkleaks-timeout 300
```

Use longer `--jadx-timeout` values when the APK is extremely large and output is still growing.

## Timeout Rules

- Use `--parallel` because apktool, APKiD, and apkleaks do not depend on JADX output.
- Use `--jadx-timeout 600` or higher; JADX may finish writing output and then hang.
- Use `--apkleaks-timeout 300` or higher; apkleaks invokes JADX internally and can hang on multi-DEX APKs.
- If JADX times out but `sources/` exists with content, treat the result as partial success only after verifying the output.
- If apkleaks times out or fails and JADX output exists, fall back to `find_static_anchors.py`.

## Progress Monitoring

Check whether JADX is still producing output:

```bash
du -sh <output>/*_jadx/sources/
find <output>/*_jadx/sources/ -name "*.java" | wc -l
```

For PowerShell equivalents, load `references/cross-platform.md`.

If file count and size stop growing for more than 2 minutes, JADX is likely stalled. Kill the process only after checking that no output is being written, then verify whether existing output is usable.

## Partial Output Triage

Before continuing after a timeout, verify:

```bash
test -d <output>/*_jadx/sources
find <output>/*_jadx/sources -name "*.java" | head
find <output> -path "*/resources/AndroidManifest.xml"
```

For PowerShell equivalents, load `references/cross-platform.md`.

Continue only when the requested analysis can be supported by the remaining artifacts. Label conclusions as partial when decompilation, manifest/resources, native code, or runtime-loaded DEX coverage is incomplete.

## apkleaks Fallback

When apkleaks fails but JADX output exists:

```bash
python3 <skill-dir>/scripts/find_static_anchors.py <jadx-dir>/sources \
  --urls \
  --auth \
  --include-namespace <app.namespace>
```

Redact concrete credential values and filter SDK/example URLs before reporting.
