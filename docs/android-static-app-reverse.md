# Android 应用静态分析

`android-static-app-reverse` 用于已授权 Android 应用的纯静态分析：从设备导出 APK、处理 split APK、反编译代码与资源、识别加固和 native 信号、提取接口线索，并生成带来源和置信度的报告。

## 输入与工具

输入可以是包名、本地 APK/XAPK、JAR/AAR，或已有 JADX/apktool 产物。核心工具是 JADX；从设备导出时需要 ADB。按目标可选用 apktool、Vineflower、APKiD、apkleaks、aapt/aapt2 和 apksigner。

从设备分析前会确认设备状态和 serial，并使用 `adb shell pm path` 导出全部 split APK。不会只处理 `base.apk` 后宣称覆盖完整。

## 典型流程

```bash
python skills/android-static-app-reverse/scripts/reverse_android_apps.py \
  com.example.app \
  --out analysis-output
```

需要资源/smali、交叉反编译、加固或泄漏线索时再启用对应工具：

```bash
python skills/android-static-app-reverse/scripts/reverse_android_apps.py \
  sample=app.apk \
  --out analysis-output \
  --with-apktool \
  --with-vineflower \
  --with-apkid \
  --with-apkleaks
```

## 可以得到什么

- APK/split、版本、签名和 SHA-256 清单。
- JADX、apktool、Vineflower 等产物的完整性状态。
- Retrofit、OkHttp、Volley、自定义网络层或 WebView 的接口线索。
- Manifest、deep link、IPC、storage、crypto、native/JNI 和动态加载风险线索。
- 按 `已确认`、`很可能`、`需动态确认` 标记的结论及来源定位。

## 安全与覆盖边界

本能力只做静态分析，不绕过 license、认证、加密、支付、反作弊或访问控制，不提取私人用户数据和凭据。裸字符串命中、第三方 SDK、漂亮的反编译 Java 或 APKiD 的 anti-debug 信号都不能单独证明漏洞或恶意行为。混淆、JNI、运行时 DEX、RASP 和缺失工具造成的覆盖缺口会明确报告。

## 接入 TestSpec

默认情况下，逆向报告只作为 `authority: reference` 的实现证据：按需先由 `testspec-new` 建立 PRD-first 上下文，再交给 `testspec-analysis` 扩展风险、边界和候选测试面。静态线索不能覆盖产品需求，也不能冒充运行证据。

当目标是用反编译代码对照 PRD 或恢复遗留行为时，可以改走 `testspec-code-calibrate`，但必须由用户显式调用或明确要求代码校准，`android-static-app-reverse` 不会自动触发。校准前还需确认代码角色、安全来源标签和相对 scope，并冻结以下来源身份：

- APK、全部 split APK 的 SHA-256，以及包名和版本。
- 反编译工具、模式、退出状态和已验证的输出范围。
- 混淆、JNI/native、动态加载、RASP、缺失资源和不完整反编译造成的覆盖缺口。

反编译目录不是 Git checkout 时，校准 source 的 `ref` 和 `commit` 使用 `unavailable`，`snapshot_reason` 记录其来自哪个已冻结 APK 快照。所有证据路径相对于已授权的反编译输出根目录；反编译推断保持 `inferred` 或 `unknown`。

完整执行契约、工具安装和跨平台命令见 [`android-static-app-reverse`](../skills/android-static-app-reverse/SKILL.md)。需要操作真实应用并断言业务行为时使用[跨端运行测试](app-test.md)。
