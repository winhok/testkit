# Endpoint Extraction

Use this reference when the user asks for API extraction, network analysis, hook targets, request models, auth headers, or feature call flows.

## Namespace-First Search

Identify app-owned namespaces before broad grep:

```bash
rg -n "package=|android:name=" <jadx-dir>/resources/AndroidManifest.xml
rg -n "class .*Application|extends Application|@HiltAndroidApp" <jadx-dir>/sources
find <jadx-dir>/sources -maxdepth 4 -type d | head -80
```

Prioritize package roots from the manifest, Application class, and visible source tree. Run app-owned searches before global SDK inventory:

```bash
python3 <skill-dir>/scripts/find_static_anchors.py <jadx-dir>/sources \
  --include-namespace com.example.app --include-namespace com.company.product \
  --exclude-namespace okhttp3,androidx,com.google,com.facebook,com.appsflyer
```

Use global searches only after app-owned findings are summarized. Report SDK matches as informational unless app-owned code configures or consumes them.

## Retrofit/OkHttp/Volley

Search:

```bash
python3 <skill-dir>/scripts/find_static_anchors.py <jadx-dir>/sources --retrofit --include-namespace <app.namespace>
python3 <skill-dir>/scripts/find_static_anchors.py <jadx-dir>/sources --okhttp --auth --include-namespace <app.namespace>
python3 <skill-dir>/scripts/find_static_anchors.py <jadx-dir>/sources --volley --urls --include-namespace <app.namespace>
```

Trace from API interface -> service builder/client -> repository/data source -> presenter/view model/activity. Check interceptors for shared headers and request mutation.

## Non-Retrofit / Custom HTTP Managers

Do not assume Retrofit/OkHttp/Volley. Many apps use URL constant tables plus custom managers.

Run:

```bash
python3 <skill-dir>/scripts/find_static_anchors.py <jadx-dir>/sources --customhttp --urls --auth --include-namespace <app.namespace>
rg -n "public static final String .*=" <jadx-dir>/sources/<app/path>
rg -n "HttpManager|post|getUrl|getUrlNew|getUrl4FullPath" <jadx-dir>/sources/<app/path>
rg -n "TOKEN|last-login-token|deviceId|Authorization" <jadx-dir>/sources/<app/path>
```

Look for files named like `*UrlConfig.java`, `*URLConfig.java`, `*HttpManager.java`, `ApiConfig`, `HostConfig`, `ServerConfig`, or `RequestManager`.

## Quality Gates

- Do not promote a grep hit to an endpoint without method/path/base URL evidence or a clearly labeled inference.
- Redact concrete bearer tokens, API keys, cookies, private IDs, and credentials.
- Deduplicate by root cause: one endpoint family with multiple source lines is one finding.
- Cross-check confusing Java with Vineflower output or apktool smali before making a strong claim.

## Endpoint Template

```markdown
### `METHOD /path`

- **Source**: `package.Class` (file:line)
- **Base URL**: `https://api.example.com`
- **Path/query params**: `id`, `page`, `limit`
- **Headers**: auth scheme only, redact concrete secrets
- **Request body**: request model or inferred fields
- **Response type**: response model if visible
- **Called from**: `Activity -> ViewModel/Presenter -> Repository -> API`
- **Confidence**: Confirmed / Likely / Needs Dynamic Confirmation
```
