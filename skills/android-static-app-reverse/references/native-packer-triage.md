# Native, Packer, and Framework Triage

Use this reference when inventory shows native libraries, packer/protector hints, runtime-loaded DEX/JAR/APK, Unity IL2CPP, Flutter, React Native, Cordova, Xamarin, or heavy obfuscation.

## APKiD-First Packer Detection

If `apkid` is available, always run it first:

```bash
apkid <apk-file>
```

APKiD output categories:
- **compiler**: dx, d8, jack, dexlib (dexlib indicates repackaging)
- **obfuscator**: ProGuard, R8, DexGuard, Allatori, DashO, Zelix KlassMaster
- **packer**: Bangcle, Ijiami, Qihoo 360, Tencent Legu, Baidu, SecNeo, APKProtect, Nagain, LIAPP
- **anti-vm**: emulator detection, root detection
- **anti-debug**: debug detection, ptrace anti-attach
- **anti-disassembly**: opaque predicates, junk code insertion

When APKiD identifies a packer, the static APK is likely a loader. Mark coverage partial.

## Known Packer Signatures (when APKiD unavailable)

| Packer | Key indicators |
|--------|---------------|
| 360加固 (Qihoo) | `libjiagu.so`, `libjiagu_x86.so`, tiny classes.dex |
| 梆梆 (Bangcle) | `libsecexe.so`, `libsecmain.so`, `libDexHelper.so` |
| 爱加密 (Ijiami) | `libexec.so`, `libexecmain.so`, `ijiami` in assets |
| 腾讯乐固 (Legu) | `libshella-*.so`, `libBugly.so`, `tencent_stub` |
| 百度加固 | `libBaiduProtect.so`, `libbaiduprotect.so` |
| 网易易盾 | `libnesec.so`, `libNetHTProtect.so` |
| 娜迦 (Nagain) | `libchaosvmp.so`, `libddog.so`, `libfdog.so` |
| SecNeo | `libsecneo*.so`, `secneo` in assets |
| DexGuard | No obvious SO; heavy string encryption, class/method renaming beyond R8 |
| LIAPP | `liapp` markers, `libLIAPP.so` |
| AppSealing | `libcovault*.so`, `appsealing` markers |
| Promon SHIELD | `libshield.so`, runtime integrity checks |
| Arxan/Verimatrix | `libprotection.so`, code virtualization |

## Packed or Runtime-Loaded DEX

Packer/protector hints, tiny root `classes.dex`, heavy shell libraries, or runtime-loaded `.dex/.jar/.apk` assets mean the static APK may be only a loader.

Do not claim API completeness in that case. Mark coverage partial and say the next authorized step is runtime DEX dumping, then rerun JADX/apktool-style searches on dumped DEX files.

If runtime DEX dumping is explicitly authorized, hand off to a dedicated dex-dumper workflow. Wait until the app has passed splash/login/packer initialization, pull every dumped DEX, then rerun static analysis on those outputs.

## Unity IL2CPP

`libil2cpp.so` plus `assets/bin/Data/Managed/Metadata/global-metadata.dat` means Unity IL2CPP. Recommend Il2CppDumper/Cpp2IL output (`dump.cs`, `script.json`, `il2cpp.h`) before drawing conclusions from Java stubs.

## Native/JNI

Start with imports/exports, strings, JNI names, `System.loadLibrary`, `RegisterNatives`, and call sites from Java/smali.

Name unknown native functions by evidence: strings, magic constants, import calls, caller/callee context, paired calls such as alloc/free or lock/unlock, and return-value patterns.

Recover likely structs from repeated offset accesses, allocation sizes, field initialization, and caller/callee usage. Label native conclusions as inferred unless confirmed in IDA/Ghidra or runtime traces.

## Cross-Framework Signals

- Flutter: `libflutter.so`, `kernel_blob.bin`, `isolate_snapshot_data`, plugin registrants
- React Native Hermes: `libhermes.so`, `.hbc`, `index.android.bundle`
- Cordova/WebView: `assets/www`, bridge plugins, `cordova.js`
- Xamarin/Mono: `libmonodroid.so`, assemblies, managed metadata

## Dynamic Follow-Up Boundary

Keep this skill static. Recommend Frida/Unicorn/IDA follow-up only when static evidence hits loader timing, JNI, encrypted strings, custom crypto, or native algorithms that cannot be resolved statically.

If suggesting Frida later, use modern CLI form without `--no-pause`, prefer module-load-aware hooks, and do not blindly hook `.init_array`, constructors, or `JNI_OnLoad` without evidence.
