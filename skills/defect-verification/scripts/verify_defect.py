#!/usr/bin/env python3
"""Verify red/green/regression records without executing the application."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_test-run-shared" / "scripts"))
from test_run import ContractError, evaluate, inside, load, pointer, require, text, write_new


def verify(root, defect):
    require(isinstance(defect, dict), "defect must be an object")
    require(type(defect.get("schema_version")) is int and defect["schema_version"] == 1, "unsupported defect schema")
    for key in ("defect_id", "expected", "failure_signature", "conditions"):
        text(defect.get(key), key)
    phases = defect.get("phases")
    require(isinstance(phases, dict), "phases required")
    missing = [p for p in ("red", "green", "regression") if not phases.get(p)]
    if missing:
        return {"schema_version": 1, "defect_id": defect["defect_id"], "status": "incomplete", "missing_phases": missing}
    scopes, results, directories = {}, {}, {}
    for phase in ("red", "green", "regression"):
        text(phases[phase], "phase directory")
        scope_path = inside(root, phases[phase] + "/scope.json")
        directories[phase] = scope_path.parent
        scopes[phase] = load(scope_path)
        results[phase] = evaluate(root, scope_path.parent, scopes[phase]["targets"])
    red, green = scopes["red"], scopes["green"]
    require(len(set(directories.values())) == 3, "each phase needs its own execution record")
    def environments(scope):
        return {t["id"]: {k: v for k, v in t.items() if k != "build"} for t in scope["targets"]}
    require(environments(red) == environments(green), "incomparable target environments")
    require({t['id']: t for t in green["targets"]} == {t['id']: t for t in scopes["regression"]["targets"]}, "regression targets differ from GREEN")
    def oracles(scope):
        return {c['id']: (c["case_id"], c["target_id"], c["oracle"], c["binding"], c["required"], c["effect"], c["cleanup"]) for c in scope["checks"]}
    require(oracles(red) == oracles(green), "RED/GREEN oracle or binding changed")
    red_targets = {t['id']: t for t in red['targets']}
    green_targets = {t['id']: t for t in green['targets']}
    for check in red['checks']:
        if check['required']:
            target_id = check['target_id']
            require(red_targets[target_id]['build'] != green_targets[target_id]['build'], "tested target build did not change")
    def definitions(scope):
        return {s["id"]: s["sha256"] for s in scope["sources"] if s["kind"] == "runner-definition"}
    require(definitions(red) == definitions(green), "RED/GREEN execution definitions changed")
    condition_hashes = []
    for scope in scopes.values():
        matches = [s for s in scope["sources"] if s["kind"] == "dataset" and s["path"] == defect["conditions"]]
        require(len(matches) == 1, "conditions dataset must be frozen in every phase")
        condition_hashes.append(matches[0]["sha256"])
    require(len(set(condition_hashes)) == 1, "conditions changed across phases")
    matched_checks = set()
    for path in (directories["red"] / "attempts").glob("*.json"):
        attempt = load(path)
        check = next(c for c in red["checks"] if c["id"] == attempt["check_id"])
        if check["required"] and attempt["status"] == "failed" and check["binding"]["runner"] == "observation":
            raw = load(inside(root, attempt["evidence"][0]["path"]))
            observation = pointer(raw, check["binding"]["selector"])
            if observation.get("defect_signature") == defect["failure_signature"]:
                matched_checks.add(check["id"])
    red_checks = results["red"]["checks"]
    failed_checks = {key for key, item in red_checks.items() if item["required"] and item["status"] == "failed"}
    matched = bool(failed_checks) and failed_checks <= matched_checks
    red_complete = all(item["status"] in {"passed", "failed"} for item in red_checks.values() if item["required"])
    passed = (matched and red_complete and results["red"]["acceptance_status"] == "failed"
              and all(results[p]["acceptance_status"] == "passed" for p in ("green", "regression")))
    failed = any(results[p]['acceptance_status'] == 'failed' for p in ('green', 'regression'))
    return {"schema_version": 1, "defect_id": defect["defect_id"], "status": "verified" if passed else "failed" if failed else "incomplete",
            "red_signature_matched": matched, "phases": results,
            "limitations": ["Historical phase verification; current deployment identity must be checked separately."]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    try:
        result = verify(args.root, load(args.input))
        write_new(args.output, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["status"] == "verified" else 1
    except (ContractError, OSError, ValueError, KeyError, TypeError, StopIteration) as exc:
        print(json.dumps({"status": "invalid", "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
