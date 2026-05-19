# Manifest, WebView, IPC, Storage, and Crypto Triage

Use this reference when the user asks for security review, exported components, WebView, deep links, storage, crypto, TLS, or Android configuration.

## Search

```bash
python3 <skill-dir>/scripts/find_static_anchors.py <jadx-dir>/sources --ipc --webview --crypto --storage --dynamic --include-namespace <app.namespace>
python3 <skill-dir>/scripts/find_static_anchors.py <apktool-dir> --ipc --webview --crypto --storage --native
```

## Manifest and Resource Checks

Review permissions, exported `activity`/`service`/`receiver`/`provider`, intent filters, backup/debuggable/network-security settings, deep links, and WebView-related components.

Check Android version-sensitive issues:
- Explicit `android:exported` on intent-filter components
- `PendingIntent` mutability flags
- Foreground-service type declarations
- Legacy external storage flags

Treat custom permissions with missing or `normal` protection as weak until proven otherwise. Signature-level permissions reduce exploitability.

## Network Security and Deep Links

For network security config, flag cleartext, `certificates src="user"` in release trust anchors, missing pinning for sensitive APIs, and debug overrides that weaken production behavior.

For deep links, document scheme/host/path, `autoVerify`, accepted query parameters, and whether handler code validates before using URLs, intents, files, or WebView sinks.

## WebView

Look for `setJavaScriptEnabled(true)`, `addJavascriptInterface`, file access, universal file URL access, mixed content, SSL error override, `loadUrl`, `loadDataWithBaseURL`, and unvalidated deep-link or intent data reaching WebView sinks.

Do not report a WebView issue from settings alone. Trace source -> validation -> sink, or label it `Needs Dynamic Confirmation`.

## Evidence Rules

- Record file paths and line numbers for every claim.
- Separate direct evidence from inference.
- Filter library noise; focus on app-owned code unless SDK configuration is the issue.
- Do not assign final severity to items blocked by obfuscation, reflection, JNI/native code, RASP, or runtime-only behavior.
