# dependencies.yaml 格式说明

这是旧版兼容说明，帮助用户理解如何把历史前置依赖配置映射到新框架的 flow/vars 模型。当前推荐使用项目规格与复用 flow，而不是依赖旧版 CSV 注入逻辑。

## 文件位置

项目根目录：`config/dependencies.yaml`。

## 顶层字段

| 字段 | 必填 | 说明 |
|------|------|------|
| base_url | 否 | 占位用，实际 BASE_URL 来自环境变量或 run_tests.py --base-url |
| dependencies | 是 | 依赖名 → 依赖配置的映射 |

## 每个依赖的配置（runner 实际使用的字段）

| 字段 | 必填 | 说明 |
|------|------|------|
| url | 是 | 完整 URL，使用 `${BASE_URL}` 占位，如 `${BASE_URL}/auth/login` 或 `${BASE_URL}/api/v2/signin` |
| method | 否 | 请求方法，默认 POST |
| body | 否 | 请求体对象。值可为环境变量占位，如 `${TEST_USER}`、`${TEST_PASS}`，运行时替换 |
| extract | 是 | 从响应 JSON 中提取的键值。键名自定义（如 token、userId），值为 JSONPath，如 `$.data.token`、`$.data.accessToken`。CSV「注入方式」中用 `{token}`、`{userId}` 等占位 |

说明：`inject` 在 yaml 中可选（仅作文档），实际注入方式由 CSV 每行的「注入方式」列决定。

## 环境变量

- `BASE_URL`：接口根地址（如 `http://localhost:8080`）。
- 请求体中的占位如 `TEST_USER`、`TEST_PASS` 等需在 `config/.env` 或环境中配置，不要在 yaml 中写明文密码。
- 新依赖使用的环境变量应在 `config/.env.example` 中列出示例；`config/.env` 为本地覆盖，可不提交。

## CSV 对应关系

- 「前置依赖」列：填依赖名，如 `user_login`、`admin_login`；无依赖填「无」。
- 「依赖产出提取」列：一般填与 extract 中一致的 JSONPath（runner 当前按依赖配置的 extract 自动提取，此列多为文档或扩展用）。
- 「注入方式」列：如 `Header:Authorization:Bearer {token}`，其中 `{token}` 与 extract 的键名一致；若有 `userId` 则可用 `Header:X-User-Id:{userId}`。

## 示例 1：登录为 /auth/login

```yaml
base_url: ${BASE_URL}

dependencies:
  user_login:
    url: ${BASE_URL}/auth/login
    method: POST
    body:
      username: ${TEST_USER}
      password: ${TEST_PASS}
    extract:
      token: $.data.token
```

## 示例 2：登录为其它路径（如 /api/v2/signin）

```yaml
base_url: ${BASE_URL}

dependencies:
  user_login:
    url: ${BASE_URL}/api/v2/signin
    method: POST
    body:
      username: ${TEST_USER}
      password: ${TEST_PASS}
    extract:
      token: $.data.accessToken
```

CSV 中注入方式仍填：`Header:Authorization:Bearer {token}`。

## 示例 3：多个依赖（用户登录 + 管理员登录）

```yaml
base_url: ${BASE_URL}

dependencies:
  user_login:
    url: ${BASE_URL}/auth/login
    method: POST
    body:
      username: ${TEST_USER}
      password: ${TEST_PASS}
    extract:
      token: $.data.token

  admin_login:
    url: ${BASE_URL}/admin/login
    method: POST
    body:
      username: ${ADMIN_USER}
      password: ${ADMIN_PASS}
    extract:
      token: $.data.token
      role: $.data.role
```

CSV 中需要管理员 token 的用例：「前置依赖」填 `admin_login`，「注入方式」填 `Header:Authorization:Bearer {token}`（若需 role 可扩展为自定义头或占位）。

## 示例 4：无登录项目

不创建 `config/dependencies.yaml` 或保留空依赖即可：

```yaml
base_url: ${BASE_URL}
dependencies: {}
```

CSV 中所有用例「前置依赖」填「无」。
