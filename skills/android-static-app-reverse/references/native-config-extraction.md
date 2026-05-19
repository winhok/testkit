# Native Config Extraction

Use this reference when Java/Kotlin calls native methods for static configuration, SDK setup values, feature switches, or values that may be mistaken for secrets.

## Contents

- Goal
- Workflow: native entrypoints, JNI bindings, numeric constants, static data, confidence labels
- Anti-Patterns

## Goal

Recover only values the user is authorized to inspect, then classify each value:
- **Public identifier**: expected to be visible in clients; risk depends on backend restrictions.
- **Client-visible SDK configuration**: often required by third-party SDKs; protect with provider-side package/signature allowlists, quotas, and alerts.
- **Runtime credential**: derived from login/session/device state; static analysis can locate source and use sites, not recover a universal value.
- **Server secret**: should not exist in the client. If statically recoverable, report as a design issue and recommend server-side issuance.

## Workflow

### 1. Find Java/Kotlin Native Entrypoints

Search decompiled sources and smali:

```bash
rg -n "System\\.loadLibrary|external fun|native .*\\(|RegisterNatives|JNI_OnLoad" <jadx-or-smali-dir>
```

Ask:
- Which library is loaded before the native method is called?
- What is the return type: `String`, `int`, `long`, `byte[]`, or object?
- Where is the returned value used: SDK init, network signing, WebView bridge, feature flag, analytics, or login/session setup?

Do not trust method names alone. Validate every recovered value at its Java/smali call site.

### 2. Locate JNI Bindings

If symbols are present:

```bash
nm -D <library.so> | rg "Java_|JNI_OnLoad|RegisterNatives"
strings -a <library.so> | rg "Java_|JNI_OnLoad|RegisterNatives|[A-Za-z0-9_./-]{12,}"
```

If symbols are stripped, look for:
- `JNI_OnLoad` and calls that resemble `RegisterNatives`
- class, method, and signature strings near JNI registration tables
- native call sites from smali and cross-references in Ghidra/IDA/objdump

Useful fallback commands:

```bash
readelf -Ws <library.so> | rg "JNI_OnLoad|RegisterNatives"
llvm-readelf -Ws <library.so> | rg "JNI_OnLoad|RegisterNatives"
objdump -T <library.so> | rg "JNI_OnLoad|RegisterNatives"
llvm-objdump -t <library.so> | rg "JNI_OnLoad|RegisterNatives"
```

On Windows, run these through Git Bash/WSL when possible, or use the same tool names with `.exe` in PowerShell. Prefer Android NDK LLVM tools when GNU binutils are absent.

Label stripped-symbol conclusions as inferred unless a registration table or call path confirms them.

### 3. Extract Direct Numeric Constants

For simple native functions that return integer-like values, disassemble the target architecture:

```bash
objdump -d <library.so> > <output>.disasm.txt
rg -n "<symbol-or-address>|mov|movk" <output>.disasm.txt
```

On ARM64, constants may be built with `mov`/`movk`. Reconstruct the full value and convert to decimal before reporting. Confirm the Java return type and downstream use before assigning meaning.

### 4. Decode Static Data Only When Logic Is Clear

For strings or byte arrays stored in `.rodata`:

```bash
readelf -S <library.so>
readelf -sW <library.so> | rg "<symbol-or-nearby-name>"
xxd -g 1 -s <file-offset> -l <length> <library.so>
```

On Windows without `xxd`, prefer Git Bash/WSL or use PowerShell `Format-Hex`; for precise offsets, prefer Python byte reads.

Reproduce the native transform with a short script only after identifying:
- encoded byte range
- key or seed source
- transform order
- output encoding and terminator behavior

If the encoded bytes, key material, and decode routine all ship in the client, state that the value is client-recoverable obfuscation, not strong secret storage.

### 5. Separate Static Values From Runtime Values

Search use sites for session, login, account, token, signature, nonce, timestamp, or device-derived data. If the value comes from a model object, storage layer, network response, or SDK callback, report the source path and say static analysis cannot produce a universal value.

For runtime credentials, recommend short lifetime, server-side issuance, replay protection, and backend validation.

### 6. Report With Evidence

For each candidate value, include:
- recovered value, "not statically recoverable", or a redacted/partial value when the value is credential-like
- source: Java/smali call site, native symbol/function, section/offset when useful
- classification from the Goal section
- confidence: high, medium, or low
- whether it is active in the analyzed build variant
- recommended fix: server-side issuance, provider restrictions, rotation, or obfuscation-only hardening

## Anti-Patterns

- Do not stop at `strings`; trace call sites and native logic.
- Do not call public identifiers "secrets" without evidence that they authorize privileged behavior.
- Do not store target-specific field names, values, or product names in this reference.
- Do not present native obfuscation as security. If the client can decode it offline, an analyst can too.
- Do not suggest bypassing authentication, payments, licensing, anti-cheat, or authorization checks.
