# Native、加固与跨框架排查

静态盘点出现 native library、加固信号、runtime DEX/JAR/APK、Unity IL2CPP、Flutter、React Native、Cordova、Xamarin 或重度混淆时读取本文件。

## APKiD 优先

`apkid` 可用时先运行：

```bash
apkid <apk-file>
```

关注类别：

- `compiler`：dx、d8、jack、dexlib
- `obfuscator`：ProGuard、R8、DexGuard、Allatori、DashO、Zelix
- `packer`：Bangcle、Ijiami、Qihoo 360、Tencent Legu、Baidu、SecNeo、APKProtect、Nagain、LIAPP
- `anti-vm`：模拟器/root 检测
- `anti-debug`：debug 检测、ptrace anti-attach
- `anti-disassembly`：opaque predicate、junk code

识别到 packer 时，静态 APK 很可能只是 loader，覆盖度必须标为部分。

## APKiD 不可用时的典型特征

| 加固 | 关键指标 |
|---|---|
| 360 | `libjiagu.so`、`libjiagu_x86.so`、很小的 `classes.dex` |
| 梆梆 | `libsecexe.so`、`libsecmain.so`、`libDexHelper.so` |
| 爱加密 | `libexec.so`、`libexecmain.so`、asset 中的 `ijiami` |
| 腾讯乐固 | `libshella-*.so`、`libBugly.so`、`tencent_stub` |
| 百度加固 | `libBaiduProtect.so`、`libbaiduprotect.so` |
| 网易易盾 | `libnesec.so`、`libNetHTProtect.so` |
| 娜迦 | `libchaosvmp.so`、`libddog.so`、`libfdog.so` |
| SecNeo | `libsecneo*.so`、asset 中的 `secneo` |
| DexGuard | 无明显 SO，字符串加密和重命名明显超过 R8 |
| LIAPP | `liapp` 标记、`libLIAPP.so` |
| AppSealing | `libcovault*.so`、`appsealing` 标记 |
| Promon SHIELD | `libshield.so`、运行时完整性检查 |
| Arxan/Verimatrix | `libprotection.so`、代码虚拟化 |

## Packed 或 runtime-loaded DEX

加固特征、很小的根 `classes.dex`、大量壳 SO，或 runtime 加载 `.dex/.jar/.apk` 表示当前 APK 可能只有 loader。不得声称 API 已完整提取；下一步仅可建议在授权范围内 dump runtime DEX，再对 dump 结果重跑静态分析。

明确授权 runtime DEX dump 时，交给专门 workflow；等待应用完成 splash/login/packer 初始化，拉取全部 dump DEX 后再分析。

## Unity IL2CPP

`libil2cpp.so` 加 `assets/bin/Data/Managed/Metadata/global-metadata.dat` 表示 Unity IL2CPP。先获取 Il2CppDumper/Cpp2IL 的 `dump.cs`、`script.json`、`il2cpp.h`，不得只根据 Java stub 下结论。

## Native / JNI

从 import/export、string、JNI 名称、`System.loadLibrary`、`RegisterNatives` 和 Java/smali call site 开始。未知函数只按 string、magic constant、import call、caller/callee、成对调用和返回值模式命名。

重复 offset、allocation size、field init 和上下游使用可辅助恢复 struct。未经 IDA/Ghidra 或 runtime trace 验证时，native 结论标为推断。

## 跨框架信号

- Flutter：`libflutter.so`、`kernel_blob.bin`、`isolate_snapshot_data`、plugin registrant
- React Native Hermes：`libhermes.so`、`.hbc`、`index.android.bundle`
- Cordova/WebView：`assets/www`、bridge plugin、`cordova.js`
- Xamarin/Mono：`libmonodroid.so`、assembly、managed metadata

## 动态跟进边界

本技能保持纯静态。只有证据落在 loader timing、JNI、加密字符串、自定义加密或静态不可解析算法时，才建议后续 Frida/Unicorn/IDA。

若后续建议 Frida，使用不含 `--no-pause` 的现代 CLI；优先 module-load-aware hook；没有证据时不盲目 hook `.init_array`、constructor 或 `JNI_OnLoad`。
