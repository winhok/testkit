# 产物契约

写项目产物或解释结果时读取本文件。

## API 描述

`openapi.yaml` 包含以下之一：

- 语义未改变的 Swagger/OpenAPI 文档模型；JSON 转 YAML 时只允许重新序列化。
- 从 YApi/Postman 规范化得到的 OpenAPI 3.1。

导入 API 文档时，不在 OpenAPI 内写来源元数据；来源信息写入 `source-manifest.json`。源码生成的骨架还必须保留 operation 级 `x-source-file`、`x-source-line`、`x-source-framework` 和 `x-discovery-confidence`，使每条启发式路由都能追溯复核。

## 来源 manifest

必需字段：

```json
{
  "schema_version": 1,
  "kind": "openapi | yapi | postman | source-code",
  "version": "source format version",
  "source": "credential-free source identifier",
  "fidelity": "lossless | high | high-with-losses | skeleton",
  "source_sha256": "hex digest",
  "warnings": [],
  "unsupported_features": [],
  "operation_count": 0
}
```

`unsupported_features` 非空时，执行前必须人工复核。

## 规范化运行结果

`run-result.json` 是机器可读执行 envelope：

```json
{
  "schema_version": 1,
  "runner": "schemathesis",
  "status": "passed | failed | error",
  "returncode": 0,
  "mode": "smoke | full | stateful",
  "schema": "/absolute/path/openapi.yaml",
  "started_at": "RFC3339 timestamp",
  "finished_at": "RFC3339 timestamp",
  "command": [],
  "stdout": "redacted runner output",
  "stderr": "redacted runner output"
}
```

不得写入原始 secret。Reporter 可以消费该结果，但不得重新解释 exit status。

## Arazzo workflow sidecar

确定性业务场景放在 OpenAPI 外部。使用唯一 `operationId` 引用 operation，并按 Arazzo 1.1 组织顺序、输入、输出和成功条件。登录、业务步骤和 cleanup 都必须显式可审查，不得藏在脚本中。

`workflow-result.json`：

```json
{
  "schema_version": 1,
  "runner": "testkit-arazzo",
  "status": "passed | failed | error",
  "summary": {"total": 1, "passed": 1, "failed": 0, "errors": 0},
  "runs": [
    {
      "workflow_id": "authenticatedUser",
      "status": "passed",
      "steps": [
        {
          "phase": "steps | setup | cleanup",
          "step_id": "login",
          "operation_id": "login",
          "status": "passed",
          "status_code": 200,
          "duration_ms": 12.3,
          "output_names": ["token"]
        }
      ]
    }
  ]
}
```

结果只记录 output 名称，不记录 output 值、request/response body 或 header。数据驱动运行增加 `dataset_index`。一体化 runner 另写 `automation-result.json`，只组合 workflow/schema 状态和子报告路径。
