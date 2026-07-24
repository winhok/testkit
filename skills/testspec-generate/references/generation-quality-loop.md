# Generation quality loop

## Contents

- Deterministic gate
- Structural review
- Consumer review
- Correction loop
- Quality properties

## Deterministic gate

Interpret `validate_testcases.py` results:

- PASS: continue
- WARN: inspect each warning and correct high-impact findings
- FAIL: correct all errors and rerun
- `coverage.pass=false`: add or repair cases for the listed TP IDs

Common corrections:

| Finding | Correction |
|---|---|
| MISSING_FIELD | Add the required executable content |
| INVALID_PRIORITY | Use P1/P2/P3 according to risk |
| DUPLICATE | Merge only true duplicates; otherwise distinguish intent |
| NAMING_FORMAT | Restore the module_feature_scenario title |

## Structural review

- TP coverage is at least 95%; list every uncovered TP.
- Functional/boundary/exception coverage follows current evidence.
- Smoke cases are P1.
- Pure P1 or pure P3 distributions trigger inspection, not quota-based rewriting.
- Title module and `feature` match.

## Consumer review

Mentally execute each case:

- Preconditions establish all required state and data.
- Steps use concrete actions and do not depend on another case's result.
- Expected results name observable, falsifiable outcomes.
- Cases are repeatable and each owns one intent.
- Similar cases are not template copies with only nouns replaced.

## Correction loop

Run at most two rounds:

1. Correct named problems only.
2. Rerun deterministic validation.
3. Re-export only after validation passes.
4. Record iteration count and correction summary in `_context`.

Do not suppress warnings, broaden scope, or invent product rules merely to satisfy metrics.

## Quality properties

The final case set must be independent, repeatable, executable, verifiable, clear, complete, and single-purpose.
