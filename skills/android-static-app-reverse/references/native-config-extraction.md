# Native 配置提取

Java/Kotlin 通过 native method 获取静态配置、SDK 初始化值、功能开关或疑似 secret 时读取本文件。

## 目标

只恢复用户有权检查的值，并分类：

- **公开标识符**：预期在客户端可见，风险取决于后端限制。
- **客户端可见 SDK 配置**：第三方 SDK 可能必需，应由供应商侧 package/signature allowlist、quota 和告警保护。
- **运行时凭证**：来自登录/session/device；静态分析只能定位来源和使用点，无法恢复通用值。
- **服务端 secret**：不应存在客户端。若静态可恢复，报告设计问题并建议服务端签发。

## 工作流

### 1. 定位 Java/Kotlin native 入口

```bash
rg -n "System\\.loadLibrary|external fun|native .*\\(|RegisterNatives|JNI_OnLoad" <jadx-or-smali-dir>
```

确认加载的 library、返回类型，以及返回值用于 SDK init、network signing、WebView bridge、feature flag、analytics 还是 login/session。不得只相信方法名，所有恢复值都要回到 Java/smali call site 验证。

### 2. 定位 JNI binding

有 symbol 时：

```bash
nm -D <library.so> | rg "Java_|JNI_OnLoad|RegisterNatives"
strings -a <library.so> | rg "Java_|JNI_OnLoad|RegisterNatives|[A-Za-z0-9_./-]{12,}"
```

Symbol 被 strip 时，查找 `JNI_OnLoad`、疑似 `RegisterNatives` 调用、registration table 附近的 class/method/signature 字符串，以及 smali native call site。

```bash
readelf -Ws <library.so> | rg "JNI_OnLoad|RegisterNatives"
llvm-readelf -Ws <library.so> | rg "JNI_OnLoad|RegisterNatives"
objdump -T <library.so> | rg "JNI_OnLoad|RegisterNatives"
llvm-objdump -t <library.so> | rg "JNI_OnLoad|RegisterNatives"
```

Windows 优先 Git Bash/WSL 或 Android NDK LLVM。没有 registration table 或完整调用链时，strip symbol 结论必须标为推断。

### 3. 提取直接数值常量

```bash
objdump -d <library.so> > <output>.disasm.txt
rg -n "<symbol-or-address>|mov|movk" <output>.disasm.txt
```

ARM64 常量可能由 `mov/movk` 组合。报告前重建完整值、转十进制，并确认 Java 返回类型和下游用途。

### 4. 仅在逻辑明确时解码静态数据

```bash
readelf -S <library.so>
readelf -sW <library.so> | rg "<symbol-or-nearby-name>"
xxd -g 1 -s <file-offset> -l <length> <library.so>
```

没有 `xxd` 时使用 Git Bash/WSL、PowerShell `Format-Hex` 或精确 Python byte read。只有识别出 encoded byte range、key/seed 来源、transform 顺序、输出编码和 terminator 行为后，才能用短脚本复现。

编码字节、key 和解码逻辑都随客户端发布时，应明确这是客户端可恢复混淆，不是强 secret storage。

### 5. 区分静态值与运行时值

搜索 session、login、account、token、signature、nonce、timestamp 和 device-derived 数据。值来自 model、storage、network response 或 SDK callback 时，只报告来源链，并说明静态分析无法产生通用值。

运行时凭证建议使用短生命周期、服务端签发、replay protection 和后端校验。

### 6. 带证据报告

每个候选值包括：

- 恢复值、“静态不可恢复”，或凭证类值的脱敏/部分值
- Java/smali call site、native symbol/function、必要时 section/offset
- 上述分类
- 高/中/低置信度
- 是否在当前 build variant 生效
- 服务端签发、供应商限制、轮换或仅混淆加固等建议

## 反模式

- 不停在 `strings`，必须追踪 call site 和 native 逻辑。
- 没有特权授权证据时，不把公开标识符称为 secret。
- 不把目标产品的字段名、值或产品名写入本通用 reference。
- 不把 native 混淆描述成安全存储。
- 不建议绕过认证、支付、license、反作弊或授权检查。
