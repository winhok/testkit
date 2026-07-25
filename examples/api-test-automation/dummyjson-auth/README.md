# DummyJSON authenticated API demo

This opt-in example runs the generic automation pipeline against a public practice API:

1. `GET /auth/me` without a token is rejected (`401`, or `403` at the public edge).
2. `POST /auth/login` exchanges credentials for an access token.
3. The Arazzo workflow captures the token and reuses it for authenticated `GET /auth/me`.
4. The token stays in memory and seeds Schemathesis through a temporary environment variable.
5. Schemathesis runs `examples,coverage` against safe HTTP methods only.
6. Workflow, schema, and combined JSON results never contain the raw token or password.

DummyJSON publishes the following practice credentials in its authentication documentation:

```bash
export DUMMYJSON_USERNAME=emilys
export DUMMYJSON_PASSWORD=emilyspass

python examples/api-test-automation/dummyjson-auth/run_authenticated_demo.py \
  --output /private/tmp/dummyjson-auth-result.json \
  --force
```

Use this target for small, read-only smoke tests. Do not run high-volume fuzzing against a
public shared service.

Schemathesis may return exit code `1` after finding a protocol defect in the public service. For
example, the shared deployment has returned `405` for unsupported methods without the required
`Allow` header. That is a valid test finding; login or runner configuration errors use exit code
`2`.
