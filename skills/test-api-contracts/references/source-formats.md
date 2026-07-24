# P0 source formats

Load this reference when detecting, importing, or diagnosing an API source.

## Compatibility matrix

| Source | Accepted input | Import fidelity | Canonical output |
|---|---|---|---|
| Swagger/OpenAPI 2.0 | JSON/YAML file or URL | semantic-lossless | Original document model |
| OpenAPI 3.0/3.1/3.2 | JSON/YAML file or URL | semantic-lossless | Original document model |
| YApi | Native JSON export or Open API project | high | OpenAPI 3.1 |
| Postman Collection 2.1 | Collection JSON | high-with-losses | OpenAPI 3.1 |
| Backend source code | Explicit local `--code-root` only | skeleton | OpenAPI 3.1 |

HTML returned from a Swagger UI URL is not an API definition. The importer may follow a
declared `url` pointing to `/openapi.json`, `/swagger.json`, `/v2/api-docs`, or `/v3/api-docs`;
fail if no definition URL can be identified.

## OpenAPI and Swagger

Preserve the parsed input object and its version. `lossless` means no API field or semantic
version conversion; it does not promise byte-for-byte preservation because JSON input may be
serialized as YAML and formatting or key quoting may change. `source_sha256` always hashes the
original bytes. Do not upgrade Swagger 2.0 or OpenAPI 3.0 merely to standardize a version:
version conversion can change body, nullable, security, and schema semantics. Preserve external
`$ref` values and report that they still require resolution.

Reject a document without a `paths` object. Warn about duplicate `operationId` values because
scenario references require uniqueness.

## YApi

Recognize categories containing interface `list` entries and direct interface objects with
`path`, `method`, and `title`. Map:

- `req_params`, `req_query`, `req_headers` to OpenAPI parameters.
- JSON-schema `req_body_other` to request body schema.
- form/file body entries to URL-encoded or multipart schemas.
- JSON-schema `res_body` to response schema.
- category and YApi tags to OpenAPI tags.
- interface ID to `x-source-yapi-id`.

YApi commonly omits per-response status codes; default missing codes to `200` and emit a
warning. Treat pre-request, post-request, and test scripts as unsupported executable behavior.

For Open API access, call project/interface endpoints with the project token obtained from an
environment variable. Never persist request URLs containing the token.

## Postman Collection 2.1

Walk nested folders recursively. Map:

- request name to summary;
- every nested folder to tags;
- safely resolvable HTTP(S) request origins or `baseUrl` values to servers;
- URL path variables and query entries to parameters;
- raw JSON/text and form bodies to request bodies;
- saved responses to OpenAPI examples.

Do not execute or translate arbitrary pre-request/test scripts. Record scripts, unresolved
variable scope, collection/request auth, Authorization or Accept headers, GraphQL bodies, and
unsupported body modes in `unsupported_features`.

Postman examples are examples, not full schemas. Do not infer required response properties from
one saved response.

## Provenance

Compute SHA-256 from the actual imported bytes. Record:

- detected kind and version;
- original source location without credentials;
- fidelity;
- warnings and unsupported features;
- operation count.

Do not include the full source document in `source-manifest.json`; keep it in the API description
file so manifest review remains small.

## Source-code adapter

Activate source scanning only when the user explicitly asks to scan code, controllers, routers,
or endpoints. Do not fall back to scanning because an API definition is missing, and do not
auto-detect a positional directory as source code.

Scan statically without importing modules, starting servers, invoking build tools, or executing
project code. Support common literal route declarations in Spring MVC/Boot, FastAPI, Flask,
Django, Gin, `net/http`, Express, Koa, and NestJS. Treat regex/static discovery as a route
inventory, not as a recovered contract:

- Emit OpenAPI 3.1 paths and standard HTTP methods only.
- Convert common `:id` and `<int:id>` route parameters to `{id}` and mark their type as unknown.
- Use a `default` response with an explicit “not inferred” description.
- Add operation-level source file, line, framework, and heuristic-confidence extensions.
- Skip `ANY` routes and record them as unsupported instead of mapping them to `GET`.
- Record dynamic routes, DTO schemas, middleware auth, cross-file mounts, and runtime route
  composition as unsupported.

Hash supported source files by sorted relative path and bytes. Do not follow symlinks; skip
dependency, generated-output, VCS, cache, and virtual-environment directories. Enforce file-count
and byte limits, and require explicit limit increases for larger trees.
