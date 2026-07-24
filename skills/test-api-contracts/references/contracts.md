# Artifact contracts

Load this reference when writing project artifacts or interpreting results.

## API description

`openapi.yaml` contains either:

- the semantically unchanged Swagger/OpenAPI document model, potentially reserialized from
  JSON to YAML; or
- OpenAPI 3.1 normalized from YApi/Postman.

For imported API documents, do not put provenance metadata inside the OpenAPI document; use
`source-manifest.json`. A generated source-code skeleton must additionally keep operation-level
`x-source-file`, `x-source-line`, `x-source-framework`, and `x-discovery-confidence` extensions
so every heuristic route can be reviewed against its origin.

## Source manifest

Required fields:

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

Treat a non-empty `unsupported_features` list as a review gate before execution.

## Normalized run result

`run-result.json` is the machine-readable execution envelope:

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

Never write raw secret values. A reporter may consume this result but must not reinterpret the
exit status.

## Future scenario sidecar

Keep deterministic business scenarios outside OpenAPI. Reference operations by unique
`operationId` and align sequence, inputs, outputs, success criteria, and failure actions with
OpenAPI Arazzo concepts. Do not claim scenario execution support until its planner and lifecycle
tests exist.
