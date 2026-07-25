# Schema 驱动执行

运行测试、选择预算或处理认证前读取本文件。

## 运行时

使用 Schemathesis 执行 OpenAPI/Swagger example、coverage、正负向生成、fuzzing、stateful operation chain 和失败缩减。本技能不得再实现一套 property-based generator。

Wrapper 需要 `schemathesis` 或 `st` 可执行文件。缺少工具属于配置错误，未经用户授权不得安装。

## 模式策略

| 模式 | Schemathesis phase | 默认用途 |
|---|---|---|
| `smoke` | examples、coverage | PR、首次运行、共享测试环境 |
| `full` | examples、coverage、fuzzing、stateful | 隔离测试环境 |
| `stateful` | stateful | 定向诊断生产者/消费者链路 |

风险不明时从 `smoke` 开始，不得静默降级用户明确要求的 `full`。

## 认证

通过环境变量传入 secret：

```bash
API_TOKEN=... python scripts/run_api.py openapi.yaml \
  --url https://test.example.invalid \
  --header-env Authorization=API_TOKEN
```

需要 `Bearer` 等前缀时，把完整 header value 放入环境变量。规范化 command、stdout 和 stderr 都必须脱敏。

不得把 Postman script、YApi 导出、保存响应或来源 manifest 中的认证材料复制到命令。

## 环境安全

除非已有反证，否则将 fuzzing 和 stateful 视为有写入风险。必须同时满足：

- 非生产目标；
- 隔离或可丢弃测试数据；
- 已知认证身份与权限；
- 请求量可接受；
- stateful operation 有 cleanup 或 reset 策略。

无法满足时保持 `smoke` 以只读为主。

## 退出状态

- `0`：所选检查全部通过。
- `1`：出现一个或多个测试发现。
- `2`：schema、配置或执行错误。

必须保留 runner exit status，不得把执行错误改写成测试失败，也不得把测试失败改写成成功报告。

## 可选公开 live eval

DummyJSON 只用于只读认证集成 eval，默认离线套件不得运行：

```bash
export DUMMYJSON_USERNAME=emilys
export DUMMYJSON_PASSWORD=emilyspass
python scripts/test_all.py --only live-test-api-contracts
```

Live eval 验证未认证 `401`、登录、Bearer 认证、Schemathesis 执行和结果脱敏。Runner 返回 `0` 或 `1` 都表示 eval 成功执行，其中 `1` 表示外部目标暴露测试发现；`2` 表示 eval 失败。不得对该共享公共服务执行 full、fuzzing 或 stateful。
