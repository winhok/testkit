# Observed implementation draft — not canonical

> This document records behavior observed in explicitly authorized code. It is not a product-approved PRD, cannot define a test oracle, and must be confirmed through `testspec-update`.

## Snapshot

| Field | Value |
|---|---|
| Repository label | `<non-sensitive-label>` |
| Ref / commit | `<ref>` / `<commit>` |
| Authorized scope | `<repository-relative paths>` |
| Evidence role | `<reference/verification-baseline/change-evidence>` |

## Observed module boundary

Describe reachable user-facing entries and excluded scope. Do not infer product purpose that is not visible in code.

## Observed behaviors

Use draft IDs, never `REQ-*` or `AC-*`.

| Draft ID | Calibration finding | Observed behavior | Evidence | Coverage | Confidence | Product question |
|---|---|---|---|---|---|---|
| OBS-001 | CAL-001 | `<observable behavior>` | `<relative path:symbol:lines>` | `<end-to-end/enforcement-layer/partial>` | high/medium/low | Q-001 |

## Observed roles and permissions

| Actor | Enforced behavior | Evidence | Confidence |
|---|---|---|---|
| `<actor>` | `<observable permission>` | `<relative evidence>` | `<level>` |

## Observed fields, states, and errors

Record only behavior visible inside the authorized scope. Mark feature flags, environment conditions, partial layers, and uncertain mappings.

## Product confirmation required

For each `OBS-*`, ask whether the behavior is:

- intended and should become a requirement
- an implementation defect
- historical compatibility only
- obsolete or out of scope

Use stable `Q-*`. After answers arrive, run `testspec-update` to create or revise canonical `requirements.md`; do not edit this draft into a canonical document.
