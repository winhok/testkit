#!/usr/bin/env python3
"""Search decompiled Android outputs for APIs, call-flow, and static audit anchors."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


SOURCE_SUFFIXES = {".java", ".kt", ".xml", ".smali"}


@dataclass(frozen=True)
class PatternGroup:
    name: str
    patterns: tuple[re.Pattern[str], ...]


GROUPS = {
    "retrofit": PatternGroup(
        "Retrofit annotations and params",
        (
            re.compile(r"@(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS|HTTP)\s*\(", re.I),
            re.compile(r"@(Headers|Header|HeaderMap|Query|QueryMap|Path|Body|Field|FieldMap|Part|PartMap|Url)\s*\(", re.I),
            re.compile(r"\bbaseUrl\s*\(", re.I),
        ),
    ),
    "okhttp": PatternGroup(
        "OkHttp request construction",
        (
            re.compile(r"(Request\.Builder|HttpUrl|\.newCall\s*\(|\.enqueue\s*\(|\.execute\s*\()", re.I),
            re.compile(r"(\.url\s*\(|\.addQueryParameter|\.addPathSegment|\.scheme\s*\(|\.host\s*\()", re.I),
            re.compile(r"(Interceptor|addInterceptor|addNetworkInterceptor|intercept\s*\()", re.I),
        ),
    ),
    "volley": PatternGroup(
        "Volley requests",
        (
            re.compile(r"(StringRequest|JsonObjectRequest|JsonArrayRequest|ImageRequest|RequestQueue|Volley\.newRequestQueue)", re.I),
        ),
    ),
    "urls": PatternGroup(
        "Hardcoded URLs and WebView bridges",
        (
            re.compile(r"https?://[^\"'\s)>,]+", re.I),
            re.compile(r"\b(public|private|protected)?\s*static\s+final\s+String\s+\w+\s*=", re.I),
            re.compile(r"(HttpURLConnection|HttpsURLConnection|openConnection|setRequestMethod)", re.I),
            re.compile(r"(loadUrl|evaluateJavascript|addJavascriptInterface|WebViewClient|WebChromeClient)", re.I),
        ),
    ),
    "customhttp": PatternGroup(
        "Custom HTTP managers and URL config tables",
        (
            re.compile(r"\b(public|private|protected)?\s*static\s+final\s+String\s+\w+\s*=", re.I),
            re.compile(r"(HttpManager|HttpClient|UrlConfig|URLConfig|ApiConfig|HostConfig|ServerConfig|RequestManager)", re.I),
            re.compile(r"\b(post|get|request|getUrl|getUrlNew|getUrl4FullPath)\s*\(", re.I),
        ),
    ),
    "auth": PatternGroup(
        "Auth and secret-adjacent anchors",
        (
            re.compile(r"(api[_-]?key|auth[_-]?token|bearer|authorization|x-api-key|client[_-]?secret|access[_-]?token|TOKEN|last-login-token|deviceId)", re.I),
            re.compile(r"(BASE_URL|API_URL|SERVER_URL|ENDPOINT|API_BASE|HOST_NAME)", re.I),
        ),
    ),
    "flow": PatternGroup(
        "Call-flow anchors",
        (
            re.compile(r"(onCreate|onResume|onStart|onViewCreated|setOnClickListener|onClick|OnClickListener)", re.I),
            re.compile(r"(@Module|@InstallIn|@Provides|@Binds|@Inject|@HiltAndroidApp|@AndroidEntryPoint|@Component)", re.I),
            re.compile(r"(ViewModel|Repository|Presenter|UseCase|DataSource|Service)", re.I),
        ),
    ),
    "ipc": PatternGroup(
        "IPC, intents, deep links, and exported surfaces",
        (
            re.compile(r"(getIntent\s*\(|onNewIntent|onActivityResult|getData\s*\(|getQueryParameter)", re.I),
            re.compile(r"(getStringExtra|getParcelableExtra|getSerializableExtra|putExtra|startActivity|sendBroadcast)", re.I),
            re.compile(r"(android:exported=\"true\"|intent-filter|android:scheme=|android:host=|android:autoVerify)", re.I),
            re.compile(r"(ContentProvider|content://|getContentResolver\s*\(\)\.query|rawQuery\s*\(|openFile\s*\()", re.I),
        ),
    ),
    "webview": PatternGroup(
        "WebView and JavaScript bridge sinks",
        (
            re.compile(r"(WebView|loadUrl\s*\(|loadData\s*\(|loadDataWithBaseURL\s*\(|evaluateJavascript\s*\()", re.I),
            re.compile(r"(addJavascriptInterface|setJavaScriptEnabled\s*\(\s*true|setAllowFileAccess\s*\(\s*true)", re.I),
            re.compile(r"(setAllowUniversalAccessFromFileURLs\s*\(\s*true|onReceivedSslError|handler\.proceed\s*\()", re.I),
        ),
    ),
    "crypto": PatternGroup(
        "Crypto, TLS, and certificate validation anchors",
        (
            re.compile(r"(Cipher\.getInstance|MessageDigest\.getInstance|Mac\.getInstance|SecretKeySpec|IvParameterSpec)", re.I),
            re.compile(r"(AES/ECB|DES|MD5|SHA1[^0-9]|new Random\s*\(|Math\.random\s*\()", re.I),
            re.compile(r"(X509TrustManager|checkServerTrusted|HostnameVerifier|setSSLSocketFactory|SSLContext)", re.I),
            re.compile(r"(cleartextTrafficPermitted=\"true\"|usesCleartextTraffic=\"true\"|certificates src=\"user\")", re.I),
        ),
    ),
    "storage": PatternGroup(
        "Storage and file handling anchors",
        (
            re.compile(r"(SharedPreferences|getSharedPreferences|MODE_WORLD_READABLE|MODE_WORLD_WRITEABLE)", re.I),
            re.compile(r"(openOrCreateDatabase|SQLiteDatabase|FileOutputStream|openFileOutput|FileProvider)", re.I),
            re.compile(r"(getExternalStorageDirectory|getExternalFilesDir|Environment\.EXTERNAL|fullBackupContent|allowBackup=\"true\")", re.I),
        ),
    ),
    "dynamic": PatternGroup(
        "Dynamic loading, reflection, and anti-analysis anchors",
        (
            re.compile(r"(DexClassLoader|PathClassLoader|URLClassLoader|InMemoryDexClassLoader)", re.I),
            re.compile(r"(Class\.forName|getDeclaredMethod|getMethod\s*\(|\.invoke\s*\(|Proxy\.newProxyInstance)", re.I),
            re.compile(r"(Debug\.isDebuggerConnected|waitingForDebugger|FLAG_DEBUGGABLE|frida|magisk|rootbeer|emulator)", re.I),
        ),
    ),
    "native": PatternGroup(
        "Native/JNI boundary anchors",
        (
            re.compile(r"(System\.loadLibrary|System\.load\s*\(|native\s+\w+|JNI_OnLoad|RegisterNatives)", re.I),
            re.compile(r"(libflutter\.so|libhermes\.so|libmonodroid\.so|assets/www|index\.android\.bundle)", re.I),
        ),
    ),
}


def iter_source_files(root: Path):
    if root.is_file() and root.suffix in SOURCE_SUFFIXES:
        yield root
        return
    for path in root.rglob("*"):
        if path.is_file() and path.suffix in SOURCE_SUFFIXES:
            yield path


def parse_namespaces(values: list[str]) -> list[str]:
    namespaces: list[str] = []
    for value in values:
        for item in value.split(","):
            cleaned = item.strip().strip(".")
            if cleaned:
                namespaces.append(cleaned.replace(".", "/"))
    return namespaces


def namespace_allowed(path: Path, root: Path, includes: list[str], excludes: list[str]) -> bool:
    try:
        rel = path.relative_to(root if root.is_dir() else root.parent)
    except ValueError:
        rel = path
    rel_text = rel.as_posix()
    if includes and not any(namespace in rel_text for namespace in includes):
        return False
    if excludes and any(namespace in rel_text for namespace in excludes):
        return False
    return True


def redact(line: str, group: str) -> str:
    cleaned = line.strip()
    if group != "auth":
        return cleaned[:260]

    cleaned = re.sub(r"(Bearer\s+)[A-Za-z0-9._~+/=-]{8,}", r"\1<redacted>", cleaned, flags=re.I)
    cleaned = re.sub(
        r"((api[_-]?key|auth[_-]?token|access[_-]?token|client[_-]?secret)\s*[:=]\s*[\"']?)[^\"'\s,;)]{4,}",
        r"\1<redacted>",
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(r"([A-Za-z0-9_/-]{24,})", "<redacted>", cleaned)
    return cleaned[:260]


def selected_groups(args: argparse.Namespace) -> list[str]:
    explicit = [name for name in GROUPS if getattr(args, name)]
    return explicit or list(GROUPS)


def print_markdown(results: dict[str, list[tuple[Path, int, str]]], root: Path) -> None:
    for group_name, matches in results.items():
        group = GROUPS[group_name]
        print(f"\n## {group.name}\n")
        if not matches:
            print("_No matches._")
            continue
        print("| File | Line | Match |")
        print("|---|---:|---|")
        for path, lineno, snippet in matches:
            try:
                rel = path.relative_to(root)
            except ValueError:
                rel = path
            safe_snippet = snippet.replace("|", "\\|")
            print(f"| `{rel}` | {lineno} | `{safe_snippet}` |")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Find API, call-flow, and static audit anchors in decompiled Android output.")
    parser.add_argument("source_dir", help="decompiled source/resource/smali directory, or a single .java/.kt/.xml/.smali file")
    for name in GROUPS:
        parser.add_argument(f"--{name}", action="store_true", help=f"search only {name} patterns")
    parser.add_argument("--include-namespace", action="append", default=[], help="comma-separated app-owned package namespaces to include, e.g. com.example.app,com.company.product")
    parser.add_argument("--exclude-namespace", action="append", default=[], help="comma-separated package namespaces to skip, e.g. okhttp3,androidx,com.google")
    parser.add_argument("--limit", type=int, default=200, help="max matches per group")
    args = parser.parse_args(argv)

    root = Path(args.source_dir).expanduser().resolve()
    if not root.exists():
        raise SystemExit(f"source path not found: {root}")

    groups = selected_groups(args)
    include_namespaces = parse_namespaces(args.include_namespace)
    exclude_namespaces = parse_namespaces(args.exclude_namespace)
    results: dict[str, list[tuple[Path, int, str]]] = {name: [] for name in groups}

    for path in iter_source_files(root):
        if not namespace_allowed(path, root, include_namespaces, exclude_namespaces):
            continue
        try:
            lines = path.read_text(errors="ignore").splitlines()
        except OSError:
            continue
        for lineno, line in enumerate(lines, 1):
            for group_name in groups:
                if len(results[group_name]) >= args.limit:
                    continue
                if any(pattern.search(line) for pattern in GROUPS[group_name].patterns):
                    results[group_name].append((path, lineno, redact(line, group_name)))

    print_markdown(results, root if root.is_dir() else root.parent)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
