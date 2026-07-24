# Schema-driven execution

Load this reference before running tests, selecting a budget, or handling authentication.

## Runtime

Use Schemathesis for OpenAPI/Swagger examples, coverage, positive/negative generation, fuzzing,
stateful operation chains, and failure shrinking. Do not implement a second property-based
generator in this skill.

The wrapper requires the `schemathesis` or `st` executable. Missing tooling is a configuration
error; do not install it without user authorization.

## Mode policy

| Mode | Schemathesis phases | Default use |
|---|---|---|
| smoke | examples, coverage | PR, first run, shared test environment |
| full | examples, coverage, fuzzing, stateful | isolated test environment |
| stateful | stateful | focused producer/consumer chain diagnosis |

Start with smoke when risk is uncertain. Do not silently downgrade a requested full run.

## Authentication

Pass secrets by environment variable:

```bash
API_TOKEN=... python scripts/run_api.py openapi.yaml \
  --url https://test.example.invalid \
  --header-env Authorization=API_TOKEN
```

If the API needs a prefix such as `Bearer`, store the complete header value in the environment
variable. Redact secret values from the normalized command, stdout, and stderr.

Never copy authentication material from a Postman script, YApi export, saved response, or source
manifest into a command.

## Environment safety

Treat fuzzing and stateful testing as mutating unless proven otherwise. Require all of:

- a non-production target;
- isolated or disposable test data;
- known authentication identity and permissions;
- acceptable request volume;
- cleanup or reset strategy for stateful operations.

Keep smoke read-mostly when these guarantees are unavailable.

## Exit status

- `0`: all selected checks passed.
- `1`: one or more test findings.
- `2`: schema, configuration, or execution error.

Preserve the runner exit status. Do not transform an execution error into a test failure or a
test failure into a successful report.

## Opt-in public live eval

Use DummyJSON only for the read-only authentication integration eval. Keep it outside the
default offline suite:

```bash
export DUMMYJSON_USERNAME=emilys
export DUMMYJSON_PASSWORD=emilyspass
python scripts/test_all.py --only live-test-api-contracts
```

The live eval verifies unauthenticated `401`, login, Bearer authentication, Schemathesis
execution, and result redaction. Treat runner return code `0` or `1` as a successfully executed
eval: `1` means the external target exposed a test finding. Treat return code `2` as an eval
failure. Never run full, fuzzing, or stateful modes against this shared public service.
