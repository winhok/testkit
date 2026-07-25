# 大 APK 处理

APK 超过 50MB、DEX 超过 10 个、JADX/apkleaks 卡住，或需要判断部分反编译产物时读取本文件。

## 默认命令

需要这些工具时，并行运行 JADX、apktool、APKiD 和 apkleaks：

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

APK 极大且输出仍持续增长时，可以提高 `--jadx-timeout`。

## 超时规则

- apktool、APKiD、apkleaks 不依赖 JADX 输出，应使用 `--parallel`。
- JADX 使用 `--jadx-timeout 600` 或更高；它可能写完输出后仍挂起。
- apkleaks 内部会调用 JADX，多 DEX APK 使用 `--apkleaks-timeout 300` 或更高。
- JADX 超时但 `sources/` 有内容时，验证后才能标为部分成功。
- apkleaks 失败/超时且 JADX 可用时，回退到 `find_static_anchors.py`。

## 进度监控

```bash
du -sh <output>/*_jadx/sources/
find <output>/*_jadx/sources/ -name "*.java" | wc -l
```

PowerShell 等价命令见 `cross-platform.md`。文件数和目录体积超过 2 分钟不增长时，JADX 很可能停滞；确认没有写入后才能终止，再验证现有输出。

## 部分输出判断

```bash
test -d <output>/*_jadx/sources
find <output>/*_jadx/sources -name "*.java" | head
find <output> -path "*/resources/AndroidManifest.xml"
```

只有剩余产物足以支撑用户要求的分析时才能继续。反编译、manifest/resource、native 或 runtime DEX 覆盖不完整时，结论必须标为部分结果。

## apkleaks fallback

```bash
python3 <skill-dir>/scripts/find_static_anchors.py <jadx-dir>/sources \
  --urls --auth --include-namespace <app.namespace>
```

报告前脱敏凭证值，并过滤 SDK/example URL。
