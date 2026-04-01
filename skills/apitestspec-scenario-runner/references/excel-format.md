# Excel/CSV 用例格式说明（与 apitestspec-composer 共享）

Runner 同时支持 **Excel (.xlsx)** 与 **CSV**，列定义一致。Skill 2 读取的格式与 Skill 1 输出必须一致。

## 列顺序与含义

| 列名 | 类型 | 说明 |
|------|------|------|
| 用例ID | 文本 | 唯一标识 |
| 用例名称 | 文本 | 用例描述 |
| 接口路径 | 文本 | API 路径，占位符用 {参数名}，如 /api/v1/users/{id} |
| 路径参数 | 文本 | 可选。JSON 对象，键为占位符名、值为字面量；需用户填写精确值，runner 不做占位符替换 |
| 请求方法 | 文本 | GET/POST/PUT/DELETE |
| 请求体/参数 | 文本 | JSON 或空（GET 等）；需填写精确 JSON/参数，不支持占位符 |
| 预期状态码 | 数字 | 如 200 |
| 预期响应校验 | 文本 | JSONPath 断言，如 $.code==200 |
| 优先级 | 文本 | P0/P1/P2 |
| 前置依赖 | 文本 | user_login / 无 |
| 依赖产出提取 | 文本 | 如 $.data.token |
| 注入方式 | 文本 | 如 Header:Authorization:Bearer {token} |
| 是否运行 | 文本 | 是/1/Y/true 执行，否/0/N/false 跳过；空视为执行 |
| 运行结果 | 文本 | 执行后由 runner 写回 PASS 或 FAIL |

## 参数约定

路径参数与请求体均需用户填写精确值，runner 不支持 __RANDOM__ 等占位符。

## 前置依赖执行

- 「前置依赖」为「无」：直接发起请求
- 「前置依赖」为 `user_login`：在 session 开始时执行登录，将 cookie/token 注入到请求
- 配置在项目根目录 `config/dependencies.yaml`，账号密码从环境变量读取

## 是否运行

- 仅当「是否运行」为 是/1/Y/true（不区分大小写）或为空时，该行用例会被执行。
- 为 否/0/N/false 时跳过，不执行且不写回运行结果。

## 运行结果写回

- 执行结束后，runner 会按「用例ID」匹配行，将「运行结果」列更新为 PASS 或 FAIL，并写回原文件（Excel 或 CSV）。

## 执行命令

```bash
python scripts/run_tests.py --csv <用例文件路径> [--base-url <url>]
```

示例（Excel 或 CSV）：

```bash
python scripts/run_tests.py -e docs/user_api_cases.xlsx --base-url http://localhost:8080 --serve
python scripts/run_tests.py -e docs/user_api_cases.csv --base-url http://localhost:8080
```

或直接指定用例文件运行 pytest：

```bash
pytest scripts/test_api.py --csv=docs/user_api_cases.xlsx --alluredir=allure-results
allure serve allure-results
```
