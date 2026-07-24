# DummyJSON authenticated API demo

This read-only example verifies a real authentication precondition:

1. `GET /auth/me` without a token returns `401`.
2. `POST /auth/login` exchanges credentials for an access token.
3. The token stays in memory and is injected as a Bearer header through an environment variable.
4. Schemathesis runs `examples,coverage` against `GET /auth/me`.
5. The normalized result redacts the access token.

DummyJSON publishes the following practice credentials in its authentication documentation:

```bash
export DUMMYJSON_USERNAME=emilys
export DUMMYJSON_PASSWORD=emilyspass

python examples/test-api-contracts/dummyjson-auth/run_authenticated_demo.py \
  --output /private/tmp/dummyjson-auth-result.json \
  --force
```

Use this target for small, read-only smoke tests. Do not run high-volume fuzzing against a
public shared service.

Schemathesis may return exit code `1` after finding a protocol defect in the public service. For
example, the shared deployment has returned `405` for unsupported methods without the required
`Allow` header. That is a valid test finding; login or runner configuration errors use exit code
`2`.
