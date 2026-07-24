---
name: test-api-contracts
description: Import, inspect, normalize, and test HTTP API definitions from Swagger/OpenAPI 2.0, OpenAPI 3.0/3.1/3.2, YApi project exports or Open API endpoints, and Postman Collection 2.1; when the user explicitly asks to scan backend source code, statically adapt discovered routes into a review-required OpenAPI skeleton. Use for requests such as “分析这份 Swagger”, “从 YApi 项目生成接口测试”, “导入 Postman collection”, “扫描这段后端代码里的接口”, “根据 OpenAPI 跑正负向或状态化测试”, “检查哪些接口不符合契约”, or an end-to-end request that starts with an API definition or explicit code scan and ends with executable results or reports.
---

# Test API Contracts

Treat one user request as one task. Complete every requested activity—inspection, import,
test selection, execution, and result summary—without exposing internal module handoffs.

## Iron law

Never silently discard source semantics. Preserve every OpenAPI/Swagger field and version
without semantic conversion; record every lossy YApi/Postman conversion in
`source-manifest.json` before generating or running tests.

## Route by intent

Do not force every request through a fixed phase pipeline:

- For analysis, inspect the source and report its operation inventory, fidelity, and risks.
- For import, inspect first, then write the canonical description and provenance manifest.
- For an explicit source-code scan, use the code adapter and review its OpenAPI skeleton.
- For execution of an existing description, validate target safety and run the selected mode.
- For end-to-end work, import and execute in the same task, then summarize the normalized result.

In every route, detect the source before mutation, review warnings and unsupported features
before execution, keep secrets in environment variables, and distinguish configuration errors
from test findings. Stop after inspection only when the user asked only for analysis.

## Source handling

Use [source-formats.md](references/source-formats.md) when detecting or converting a source.

Run inspection before editing project artifacts:

```bash
python <skill-dir>/scripts/import_api.py inspect <file-or-url>
```

Import a file, raw spec URL, or Swagger UI URL:

```bash
python <skill-dir>/scripts/import_api.py import <file-or-url> \
  --output-dir <project>/api-tests
```

Import a YApi project through its Open API:

```bash
YAPI_TOKEN=<secret> python <skill-dir>/scripts/import_api.py import \
  --yapi-base-url https://yapi.example.invalid \
  --yapi-project-id 123 \
  --output-dir <project>/api-tests
```

Scan local backend source only when the user explicitly asks to scan code:

```bash
python <skill-dir>/scripts/import_api.py inspect --code-root <backend-dir>
python <skill-dir>/scripts/import_api.py import --code-root <backend-dir> \
  --output-dir <project>/api-tests
```

Use `--code-prefix /api` to restrict discovered paths when requested. Never infer a code root,
scan the current repository by default, import application modules, or execute application code.
A plain directory passed as `SOURCE` is not a code-scan request.

Pass YApi tokens by environment variable. Never put them in commands, generated files, logs,
or assistant responses. Do not scrape YApi HTML.

The import command writes:

- `openapi.yaml`: unchanged OpenAPI/Swagger, normalized OpenAPI 3.1 for YApi/Postman, or a
  review-required OpenAPI 3.1 route skeleton for an explicit source-code scan.
- `source-manifest.json`: source hash, detected format/version, fidelity, warnings, unsupported
  features, and operation count.

Do not label YApi/Postman conversion as lossless. Label a code scan `skeleton`, preserve
operation-level source provenance, and do not invent request/response schemas, status codes, or
authentication rules. Preserve unsupported scripts as warnings; do not execute imported scripts.

## Test selection and execution

Use [execution.md](references/execution.md) before running tests or handling authentication.

Prefer schema-driven execution:

```bash
python <skill-dir>/scripts/run_api.py <project>/api-tests/openapi.yaml \
  --url <base-url> \
  --mode smoke \
  --output <project>/api-tests/reports/run-result.json
```

Modes:

- `smoke`: examples plus coverage; use for PR feedback and first contact with an environment.
- `full`: examples, coverage, fuzzing, and stateful testing; use on isolated test environments.
- `stateful`: operation chains only; require explicit confirmation when calls can create,
  mutate, or delete shared data.

Inject secrets with `--header-env HEADER=ENV_VAR`. Fail before network access when a required
variable is missing. Use `--allure-results <dir>` only when the user wants Allure artifacts.

Do not run generated negative, fuzzing, or stateful tests against production. If environment
identity is unclear, inspect and import safely, then ask for the missing target confirmation.

## Project and result contracts

Use [contracts.md](references/contracts.md) when writing project files, interpreting fidelity,
or consuming `run-result.json`.

Keep these ownership rules:

- OpenAPI/Swagger owns HTTP surface and schema.
- A scenario sidecar may add business journeys by `operationId`; it must not duplicate method,
  path, or response schema.
- Environment profiles contain non-secret settings only.
- Environment variables or a secret provider own credentials.
- JSON result data is canonical; JUnit and Allure are reporters, not alternate truth sources.

## Failure handling

Classify before recommending changes:

- `source`: unreadable input, unsupported format/version, malformed document.
- `conversion`: source feature cannot map safely to OpenAPI.
- `configuration`: missing base URL, tool, secret, or invalid option.
- `transport`: DNS, TLS, connection, or timeout failure.
- `contract`: status, content type, header, or response schema mismatch.
- `behavior`: business assertion or state transition failure.
- `cleanup`: created test state could not be removed.

Never rewrite the source contract merely to make a failing implementation pass. Show the
evidence and identify whether the contract or implementation is more likely stale.

## Delivery checklist

- State the detected input type and version.
- State whether import was lossless, high fidelity, high-with-losses, or a source-code skeleton.
- List warnings and unsupported features; never hide an empty or partial import.
- State the exact files written.
- State whether network tests actually ran and against which non-secret base URL.
- State the test mode, result path, pass/fail/error status, and actionable failure category.
- State any activity intentionally not performed.
