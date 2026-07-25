# Endpoint 提取

用户要求 API 提取、网络分析、hook target、request model、认证 header 或功能调用链时读取本文件。

## Namespace 优先搜索

广泛搜索前先识别应用自有 namespace：

```bash
rg -n "package=|android:name=" <jadx-dir>/resources/AndroidManifest.xml
rg -n "class .*Application|extends Application|@HiltAndroidApp" <jadx-dir>/sources
find <jadx-dir>/sources -maxdepth 4 -type d | head -80
```

优先使用 manifest、Application class 和源码树中的 package root：

```bash
python3 <skill-dir>/scripts/find_static_anchors.py <jadx-dir>/sources \
  --include-namespace com.example.app --include-namespace com.company.product \
  --exclude-namespace okhttp3,androidx,com.google,com.facebook,com.appsflyer
```

总结应用自有发现后才能做全局 SDK 盘点。第三方 SDK 命中默认只作信息；只有应用代码配置或使用它时才升级为应用发现。

## Retrofit / OkHttp / Volley

```bash
python3 <skill-dir>/scripts/find_static_anchors.py <jadx-dir>/sources --retrofit --include-namespace <app.namespace>
python3 <skill-dir>/scripts/find_static_anchors.py <jadx-dir>/sources --okhttp --auth --include-namespace <app.namespace>
python3 <skill-dir>/scripts/find_static_anchors.py <jadx-dir>/sources --volley --urls --include-namespace <app.namespace>
```

沿 API interface → service builder/client → repository/data source → presenter/view model/activity 追踪，并检查 interceptor 注入的共用 header 和请求改写。

## 自定义 HTTP manager

不得假设应用一定使用 Retrofit/OkHttp/Volley。URL 常量表加自定义 manager 很常见：

```bash
python3 <skill-dir>/scripts/find_static_anchors.py <jadx-dir>/sources --customhttp --urls --auth --include-namespace <app.namespace>
rg -n "public static final String .*=" <jadx-dir>/sources/<app/path>
rg -n "HttpManager|post|getUrl|getUrlNew|getUrl4FullPath" <jadx-dir>/sources/<app/path>
rg -n "TOKEN|last-login-token|deviceId|Authorization" <jadx-dir>/sources/<app/path>
```

重点检查 `*UrlConfig.java`、`*URLConfig.java`、`*HttpManager.java`、`ApiConfig`、`HostConfig`、`ServerConfig` 和 `RequestManager`。

## 质量门槛

- 缺少 method/path/base URL 证据时，不得把 grep 命中升级为 endpoint；推断必须明确标注。
- 具体 bearer token、API key、Cookie、私人 ID 和凭证必须脱敏。
- 按根因去重：同一 endpoint family 的多个来源行属于一个发现。
- Java 结果可疑时，用 Vineflower 或 apktool smali 交叉验证。

## Endpoint 模板

```markdown
### `METHOD /path`

- **来源**：`package.Class`（file:line）
- **Base URL**：`https://api.example.com`
- **Path/query 参数**：`id`、`page`、`limit`
- **Header**：只写认证方案，具体 secret 脱敏
- **Request body**：request model 或明确标注的推断字段
- **Response type**：可见时填写 response model
- **调用链**：`Activity -> ViewModel/Presenter -> Repository -> API`
- **置信度**：已确认 / 很可能 / 需动态确认
```
