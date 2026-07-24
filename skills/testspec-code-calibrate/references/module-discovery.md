# Authorized Module Discovery

Use this reference only when the user authorized repository inspection but did not provide an
unambiguous module or relative scope. Discovery identifies candidates; it does not authorize
reading every candidate.

## Gate

1. Record the authorized repository and ref.
2. Ask for or confirm permission to inspect discovery surfaces.
3. Inspect only route/menu/module registration and top-level source directories.
4. Return candidates and stop for product selection.
5. Convert the selected candidates into repository-relative `scope`.

Do not infer whole-repository authorization from repository access. If discovery surfaces
themselves are not authorized, request the missing scope instead.

## Candidate signals

Prefer signals in this order:

1. user-visible route or menu group
2. public command or application entry
3. controller/router prefix
4. registered application module
5. domain/feature directory

Merge list/detail/edit pages and related handlers under one product-visible module. Exclude
generated files, dependencies, fixtures, tests, caches, generic components, utilities, build
scripts, and CI configuration.

For a user-facing full-stack application, use the visible route/menu name as the candidate label
and backend registrations only as cross-checks. If labels disagree, report the mismatch instead
of choosing a hidden implementation name as product truth.

## Candidate output

Return a temporary table in conversation; do not persist repository paths before selection:

| Candidate label | Discovery basis | Approximate surface | Confidence |
|---|---|---:|---|
| `<safe product label>` | route/menu/controller/module | `<page/handler count>` | high/medium/low |

Mark labels inferred only from directory names as low confidence. Ask the user to select one or
more candidates. Then persist only:

- a non-sensitive repository label
- the selected repository-relative paths
- the user-selected module labels when they are safe

Never generate requirements, priorities, acceptance criteria, or test cases during discovery.
