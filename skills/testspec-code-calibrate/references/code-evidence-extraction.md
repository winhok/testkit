# Observable Code Evidence Extraction

## Contents

- [Goal](#goal)
- [Evidence order](#evidence-order)
- [What to inspect](#what-to-inspect)
- [Product language](#product-language)
- [Evidence record](#evidence-record)
- [Confidence](#confidence)
- [Coverage gate](#coverage-gate)
- [Absence rules](#absence-rules)
- [Conflict rules](#conflict-rules)
- [Product-question triggers](#product-question-triggers)
- [Exclusions](#exclusions)

## Goal

Extract only product-visible implementation evidence inside the explicitly authorized scope. Do not create product intent from architecture, naming, or comments.

## Evidence order

1. User-visible routes, menus, pages, commands, and public entry points
2. Runtime permission checks and enforced validation
3. State transitions and persisted observable outcomes
4. Error handling, retry, rollback, and visible messages
5. Interfaces between the scoped component and external actors
6. Comments and names only as low-confidence discovery hints

## What to inspect

| Signal | Observable evidence |
|---|---|
| routes and menus | reachable entry, role visibility, navigation |
| controllers/handlers | accepted action and response branch |
| forms and schemas | fields, requiredness, limits, enum labels |
| lists and search | columns, filters, sorting, pagination, empty states |
| action controls | confirmation, loading state, duplicate-submit protection |
| permission guards | enforced role/action boundary |
| state logic | allowed transition and resulting state |
| error branches | visible failure, recovery, retry, rollback |
| feature flags | conditional availability; never assume enabled |
| tests | supporting evidence only; a test name is not runtime behavior |

Framework-specific filenames are discovery hints, not a closed list. Prefer `rg` and repository-native navigation over scanning generated output, dependencies, caches, fixtures, or vendored code. Load `framework-locators.md` only for frameworks present in the authorized scope.

## Product language

Keep technical locators in `evidence`; write findings as observable product behavior:

| Technical signal | Finding wording |
|---|---|
| route or handler | reachable page, command, or user action |
| API/database field | visible field meaning |
| raw enum value | displayed state label and allowed transition |
| exception/status code | visible failure and recovery behavior |
| function call | action and observable outcome |

Do not copy class names, APIs, raw enum values, framework terms, or database details into
`intended_behavior` / `observed_behavior` unless they are themselves a public contract. Preserve
display labels separately from raw values.

## Evidence record

Every positive observation records:

- repository-relative `path`
- stable `symbol` or locator such as `route-config`
- exact `lines` when available
- one product-visible `observation`

Use the smallest evidence span that supports the statement. For `end-to-end`, prefer evidence
spanning two or more of reachable entry, enforcement, state effect, feedback/recovery, and an
external actor boundary. For `enforcement-layer`, state why the cited location is the canonical
enforcement point.

## Confidence

- `high`: directly enforced or observable in the authorized runtime path
- `medium`: supported by multiple code signals but not fully connected
- `low`: inferred from naming, comments, partial layers, flags, or unreachable paths

Low-confidence evidence cannot support `aligned` by itself. Use `unknown` or record additional evidence.

## Coverage gate

Assign one finding-level `evidence_coverage`:

- `end-to-end`: the authorized scope connects a reachable entry through the observable outcome
- `enforcement-layer`: the inspected guard, validator, state machine, or handler is itself the canonical enforcement point
- `scoped-search`: the authorized locations searched for a `prd-only` result
- `partial`: isolated function, single layer, unproven caller, flag-dependent path, or incomplete chain

Only `end-to-end` or `enforcement-layer` can support `aligned` / `conflict`. An exported function, method name, save call, queue call, route declaration, or test expectation alone remains `partial` unless reachability and effect are established.

## Absence rules

Failure to find behavior is not proof of absence. Before using `prd-only`:

1. record every searched scope
2. check entry point and enforcement layer when both are authorized
3. note excluded repositories/components
4. avoid claims beyond the authorized snapshot

## Conflict rules

Separate:

- `intended`: current REQ/AC or confirmed product answer
- `observed`: directly supported behavior
- `inferred`: plausible interpretation without complete evidence
- `unknown`: unresolved gap or contradiction

When frontend and backend disagree, record `unknown` or `conflict` with evidence from both; do not choose the more convenient layer.

When a feature flag, tenant configuration, environment, or branch controls behavior, include that condition in the observation. Do not generalize one configuration to all users.

## Product-question triggers

Register a stable product question rather than guessing when:

- a state has no observable entry or exit
- frontend visibility and backend enforcement disagree
- a field label or business meaning is ambiguous
- an external-system result is not visible in scope
- a feature flag or environment condition is unknown
- a Diff contains only part of the observable path
- canonical intent and implementation expose different labels or outcomes

## Exclusions

Do not extract as product truth:

- dead or unreachable code
- commented-out behavior
- TODO text
- mock/fixture-only behavior
- test expectations without runtime support
- dependency or generated-code behavior outside scope
- database or internal implementation detail with no observable contract
