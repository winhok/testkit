# Test point design rules

## Contents

- Core definition
- Categories and IDs
- Priority and regression tier
- Granularity and prohibited content
- Anti-patterns

## Core definition

A test point is one independently verifiable business behavior, rule, or quality attribute. It states **what** to verify. A test case states **how** to execute; a check is the concrete assertion.

## Categories and IDs

Every point belongs to one category:

| Category | Sequence range |
|---|---:|
| Functional | 001–099 |
| Boundary | 100–199 |
| Exception | 200–299 |
| Integration | 300–399 |
| Non-Functional | 400–499 |

ID format: `TP_<MODULE>_<FEATURE>_<SEQ>`.

- MODULE is a stable 2–5 character uppercase key.
- FEATURE is a stable 2–10 character uppercase key.
- Reuse module/feature keys from TestLib when available.
- Sequence allocation is local to the current change; historical `tp_ids` are retrieval evidence, not an allocator.

## Priority and regression tier

Priority:

- P1: core business, authorization, security, money, or data safety
- P2: regular important behavior, boundary, or exception
- P3: low-frequency, peripheral, or experience-focused behavior

Regression tier:

- Smoke: shortest deploy-blocking business loop; usually the most critical P1 subset
- Full: normal complete regression coverage; default when no tier is specified
- Targeted: isolated change scope with explicit impact boundaries

Use risk signals, not quotas. Do not upgrade a point merely because a similar historical case was important.

## Granularity and prohibited content

- One point covers one business intent.
- Do not split by individual field or interface parameter.
- Split “and/simultaneously” wording only when it contains independent intents.
- Keep points stable across implementation changes.
- Do not include clicks, inputs, navigation steps, concrete data, table fields, Redis/MQ/database details, or case-form prose.

## Anti-patterns

| Anti-pattern | Correction |
|---|---|
| One point per field | Combine fields under the business validation intent |
| One point per boundary value | Keep one boundary point; generate expands concrete values |
| Action verbs such as click/input/select | Rewrite as an observable verification target |
| All points are Functional | Add only evidence-supported boundary/exception/integration coverage |
| “Verify it works” | Name the concrete behavior or quality attribute |
| One module is disproportionately sparse | Check evidence for missing categories; do not invent scope |
