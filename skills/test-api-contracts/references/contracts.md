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

## 未来 scenario sidecar

确定性业务场景放在 OpenAPI 外部。使用唯一 `operationId` 引用 operation，并按 OpenAPI Arazzo 概念组织顺序、输入、输出、成功条件和失败动作。在 planner 与生命周期测试真正存在前，不得声称支持 scenario 执行。
