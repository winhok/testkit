# Change-Diff Calibration

Use this reference only for `mode=change-diff`.

## Contents

- Snapshot selection
- Safe collection
- Candidate retrieval
- Semantic trace
- Classification mapping
- Reporting and freshness

## Snapshot selection

Require explicit:

- repository access and repository-relative scope
- non-sensitive repository label
- actual base and head refs for local Git execution
- safe base/head labels stored in artifacts, such as `production`, `test`, or `requirement`
- comparison mode

Choose:

| Question | Comparison |
|---|---|
| What accumulated changes exist on test versus production? | `production...test` |
| What did a requirement branch add since it diverged? | `production...requirement` |
| What remains to merge from requirement into test? | `test...requirement` |
| What is staged locally? | staged |
| What does the authorized worktree add over a base? | worktree |

Use three-dot by default for branch intent. Use two-dot only when the user explicitly requests
tip-to-tip comparison. Never silently fall back between them. Never run `git fetch`, checkout,
merge, rebase, pull, or push as part of calibration.

## Safe collection

Write `<change>/artifacts/change-snapshot.json`:

```bash
python "<skill-dir>/scripts/collect_change_snapshot.py" \
  --repo-root "<authorized-local-repo>" \
  --repository-label "<safe-label>" \
  --base-ref "<actual-local-ref>" \
  --head-ref "<actual-local-ref>" \
  --base-label "<safe-role-label>" \
  --head-label "<safe-role-label>" \
  --scope "<repository-relative-scope>" \
  --output "<change>/artifacts/change-snapshot.json"

python "<skill-dir>/scripts/validate_change_snapshot.py" \
  --input "<change>/artifacts/change-snapshot.json"
```

The collector persists commit identities, merge-base, timestamps, dirty state, file statistics,
relative paths, numeric hunk ranges, and a SHA-256 of the transient Diff. It never persists the
actual refs, repository root, remote, raw Diff, changed lines, or snippets.

Do not overwrite an existing snapshot unless the user explicitly authorizes replacement. Use a
fresh snapshot if HEAD, index, worktree state, scope, or canonical revision changes.

## Candidate retrieval

Build candidate links from current canonical `REQ-*` / `AC-*` and, when available, current
TestSpec-native test points or cases. Historical imported cases may be secondary search hints
only.

Candidate hints may use:

- field and visible-label tokens
- route or command concepts
- state and action vocabulary
- safe relative path proximity
- changed numeric hunk ranges

Record `candidate_strategy=keyword-hints-only`. A token hit never establishes alignment,
conflict, implementation, priority, or test success. Read the corresponding transient hunk and
connected runtime path before creating a finding.

## Semantic trace

Assign every change-diff finding one `change_trace_status`:

| Status | Meaning |
|---|---|
| `matched` | changed evidence supports a canonical behavior or an observed code-only behavior |
| `partial` | relevant changes exist but the observable path is incomplete |
| `not-observed` | the canonical behavior was not seen in this Diff; this is not global absence |
| `deviation` | changed evidence contradicts canonical intent |
| `unknown` | scope, parsing, configuration, or contradictory evidence prevents a conclusion |

Every `matched` or `deviation` finding includes at least one `source=diff` evidence item.
Supporting unchanged code uses `source=snapshot`. Label evidence layers as `entry`,
`enforcement`, `state`, `feedback`, or `external`.

Record changed paths that cannot be mapped under `change_trace.unmapped_changes`; this is a
review-focus list, not proof that requirements are missing.

## Classification mapping

Map trace status into the existing calibration contract:

| Trace status | Allowed classification |
|---|---|
| `matched` | `aligned` or `code-only` |
| `deviation` | `conflict` |
| `partial` | `unknown` |
| `not-observed` | `unknown` |
| `unknown` | `unknown` |

Never emit `prd-only` from Diff absence. `prd-only` requires a comparison-mode scoped search of
the relevant implementation, not merely lack of a changed hunk.

Use medium/low confidence for `partial` and `not-observed`. Apply the existing
`end-to-end/enforcement-layer/partial` evidence gate. For `end-to-end` change findings, provide
at least two distinct evidence layers.

## Reporting and freshness

Validate JSON and render a snippet-free report:

```bash
python "<skill-dir>/scripts/validate_code_calibration.py" \
  --input "<change>/artifacts/code-calibration.json" \
  --canonical "<change>/requirements.md" \
  --snapshot "<change>/artifacts/change-snapshot.json"

python "<skill-dir>/scripts/render_code_calibration.py" \
  --input "<change>/artifacts/code-calibration.json" \
  --output "<change>/artifacts/code-calibration.md"
```

In conversation, report safe product-language finding summaries, counts, safe labels, warnings,
unresolved `Q-*`, and artifact paths. Do not paste raw code, Diff content, private refs, or
snippets. A summary must keep `not-observed` and `unknown` qualifiers instead of rewriting them
as missing implementation.
