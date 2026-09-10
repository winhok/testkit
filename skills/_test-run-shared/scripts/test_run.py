#!/usr/bin/env python3
"""Freeze test scope, record observations, evaluate evidence, and migrate legacy reports.

This tool never executes business operations. Runtime tools remain responsible for
execution; hashes detect changes, not authenticity of external observations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


class ContractError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ContractError(message)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def load(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, f"duplicate JSON key: {key}")
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=unique)


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def inside(root, name):
    require(isinstance(name, str) and name and "\\" not in name, "invalid relative path")
    path = Path(name)
    require(not path.is_absolute() and ".." not in path.parts, "path must stay inside root")
    resolved = (Path(root) / path).resolve()
    require(resolved.is_relative_to(Path(root).resolve()), "symlink escapes root")
    require(resolved.is_file(), f"missing file: {name}")
    return resolved


def stamp(value):
    require(isinstance(value, str), "timestamp must be a string")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(result.tzinfo is not None, "timestamp must include timezone")
    return result


def text(value, label):
    require(isinstance(value, str) and bool(value.strip()), f"{label} must be nonempty")


def ids(items, label):
    require(isinstance(items, list) and bool(items), f"{label} must be nonempty")
    result = {}
    for item in items:
        require(isinstance(item, dict), f"{label} item must be an object")
        key = item.get("id")
        require(isinstance(key, str) and re.fullmatch(r"[A-Za-z0-9_-]+", key), f"invalid {label} id")
        require(key not in result, f"duplicate {label} id: {key}")
        result[key] = item
    return result


def validate_scope(scope, root, *, verify_sources=True):
    require(isinstance(scope, dict), "scope must be an object")
    require(scope.get("schema_version") == 1 and scope.get("kind") == "test-scope", "unsupported scope")
    text(scope.get("run_id"), "run_id")
    require(scope.get("mode") in {"local", "acceptance"}, "mode must be local or acceptance")
    sources = ids(scope.get("sources"), "sources")
    for source in sources.values():
        require(source.get("kind") in {"requirements", "cases", "strategy", "local-check", "runner-definition", "dataset"}, "invalid source kind")
        require(re.fullmatch(r"[0-9a-f]{64}", source.get("sha256", "")), "source hash required")
        if verify_sources:
            require(digest(inside(root, source["path"])) == source["sha256"], "source content changed")
    targets = ids(scope.get("targets"), "targets")
    for target in targets.values():
        text(target.get("build"), "target build anchor")
        text(target.get("environment"), "target environment")
        require(target.get("platform") in {"api", "web", "android", "ios"}, "invalid platform")
    capabilities = ids(scope.get("capabilities"), "capabilities")
    for cap in capabilities.values():
        require(cap.get("target_id") in targets, "unknown capability target")
        require(cap.get("availability") in {"unknown", "available", "limited", "unavailable"}, "invalid availability")
        require(cap.get("authorization") in {"unknown", "granted", "denied"}, "invalid authorization")
        text(cap.get("scope"), "capability scope")
        text(cap.get("basis"), "capability evidence or missing-information reason")
        stamp(cap.get("checked_at"))
        require(isinstance(cap.get("actions"), list) and bool(cap["actions"]) and set(cap["actions"]) <= {"read", "write"}, "capability actions required")
    checks = ids(scope.get("checks"), "checks")
    for check in checks.values():
        text(check.get("case_id"), "case_id")
        text(check.get("oracle"), "oracle")
        require(check.get("source_id") in sources, "unknown check source")
        require(check.get("target_id") in targets, "unknown check target")
        require(type(check.get("required")) is bool, "required must be boolean")
        require(check.get("effect") in {"read", "write"}, "effect must be read or write")
        require(check.get("cleanup") in {"required", "not-required"}, "cleanup declaration required")
        for key in ("depends_on", "capability_ids", "requirement_refs"):
            values = check.get(key)
            require(isinstance(values, list) and len(values) == len(set(values)), f"invalid {key}")
        require(bool(check["capability_ids"]), "each check requires scoped capability")
        require(set(check["capability_ids"]) <= capabilities.keys(), "unknown capability")
        require(all(capabilities[c]["target_id"] == check["target_id"] for c in check["capability_ids"]), "cross-target capability")
        require(any(check["effect"] in capabilities[c]["actions"] for c in check["capability_ids"]), "effect not covered by scoped capability")
        require(set(check["depends_on"]) <= checks.keys(), "unknown dependency")
        if scope["mode"] == "acceptance":
            require(bool(check["requirement_refs"]), "acceptance checks need requirement refs")
        binding = check.get("binding")
        require(isinstance(binding, dict), "binding required")
        require(binding.get("runner") in {"observation", "testkit-arazzo", "schemathesis", "pytest"}, "unsupported binding runner")
        text(binding.get("selector"), "binding selector")
        if binding["runner"] != "observation":
            require(binding.get("definition_source_id") in sources, "runner definition must be frozen")
            require(sources[binding["definition_source_id"]]["kind"] == "runner-definition", "binding definition has wrong source kind")
    visiting, done = set(), set()
    def visit(key):
        require(key not in visiting, "dependency cycle")
        if key in done:
            return
        visiting.add(key)
        for dependency in checks[key]["depends_on"]:
            visit(dependency)
        visiting.remove(key)
        done.add(key)
    for key in checks:
        visit(key)
    require(any(c["required"] for c in checks.values()), "scope must contain required checks")
    if scope["mode"] == "acceptance":
        require(any(s["kind"] == "requirements" for s in sources.values()), "acceptance needs requirements snapshot")
        require(any(s["kind"] == "cases" for s in sources.values()), "acceptance needs cases snapshot")
        require(isinstance(scope.get("source_revision"), dict) and bool(scope["source_revision"]), "acceptance needs source revision")
        text(scope.get("scope_basis"), "confirmed scope basis")
        if verify_sources:
            case_ids = set()
            requirement_ids = set()
            for source in sources.values():
                if source["kind"] == "requirements":
                    content = inside(root, source["path"]).read_text(encoding="utf-8")
                    requirement_ids.update(re.findall(r"\b(?:REQ|AC)-[A-Za-z0-9_-]+\b", content))
                    match = re.search(r"<!--\s*testspec-context\s*(\{.*?\})\s*-->", content, re.S)
                    require(match is not None, "requirements need TestSpec context; migrate legacy context first")
                    context = json.loads(match.group(1))
                    require(context.get("context_schema_version") == 2 and context.get("source_revision") == scope["source_revision"], "requirements revision mismatch")
                if source["kind"] == "cases":
                    artifact = load(inside(root, source["path"]))
                    require(artifact.get("_context", {}).get("source_revision") == scope["source_revision"], "case revision mismatch")
                    require(artifact.get("_context", {}).get("context_schema_version") == 2, "migrate TestSpec context first")
                    case_ids.update(c["id"] for c in artifact["testcases"])
            require(all(c["case_id"] in case_ids for c in checks.values()), "unknown case in acceptance scope")
            require(all(set(c["requirement_refs"]) <= requirement_ids for c in checks.values()), "unknown requirement in acceptance scope")
    return checks


def freeze(draft, root, directory):
    scope = load(draft)
    scope.update(schema_version=1, kind="test-scope")
    for source in scope.get("sources", []):
        source["sha256"] = digest(inside(root, source["path"]))
    validate_scope(scope, root)
    scope["frozen_at"] = datetime.now(timezone.utc).isoformat()
    directory = Path(directory)
    require(not directory.exists(), "choose a new run directory")
    directory.mkdir(parents=True)
    write_new(directory / "scope.json", scope)
    return {"scope_sha256": digest(directory / "scope.json"), "checks": len(scope["checks"])}


def pointer(value, locator):
    require(locator.startswith("/"), "observation selector must be a JSON pointer")
    for part in locator[1:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def outcome(raw, binding):
    runner, selector = binding["runner"], binding["selector"]
    if runner == "observation":
        item = pointer(raw, selector)
        require(item.get("status") in {"passed", "failed", "blocked", "skipped", "inconclusive", "error"}, "invalid observation status")
        text(item.get("actual"), "observed actual value")
        text(item.get("basis"), "observation basis")
        require(item.get("method") in {"tool", "human"}, "observation method required")
        return item["status"]
    require(raw.get("schema_version") == 1 and raw.get("runner") == runner, "runner/schema mismatch")
    require(raw.get("status") in {"passed", "failed", "error"}, "invalid runner status")
    if runner == "schemathesis":
        require(selector == "suite", "Schemathesis envelope only proves suite result")
        code = raw.get("returncode")
        require(type(code) is int, "returncode required")
        require(raw["status"] == ({0: "passed", 1: "failed"}.get(code, "error")), "inconsistent exit status")
        return raw["status"]
    if runner == "testkit-arazzo":
        candidates = [r for r in raw["runs"] if r["workflow_id"] == selector and r.get("dataset_index") == binding.get("dataset_index")]
        require(len(candidates) == 1, "workflow/dataset must match exactly once")
        result = candidates[0]
        require(result["status"] in {"passed", "failed", "error"}, "invalid workflow status")
        require(result.get("steps"), "empty workflow evidence")
        if result["status"] == "passed":
            require(all(s.get("status") == "passed" for s in result["steps"]), "workflow hides unsuccessful step")
        return result["status"]
    require(type(raw.get("exit_code")) is int, "pytest exit code required")
    require(raw["status"] == ({0: "passed", 1: "failed"}.get(raw["exit_code"], "error")), "inconsistent pytest exit status")
    # JUnit names are not reliably identical to native nodeids. A whole invocation
    # is the only trustworthy unit in the existing normalized envelope.
    require(selector == "suite", "legacy pytest envelope supports suite mapping only")
    require(raw.get("selected_nodeids") == binding.get("nodeids") and bool(binding.get("nodeids")), "pytest selection mismatch")
    require(raw.get("summary", {}).get("total", 0) > 0, "zero-test pytest result")
    if raw["status"] == "passed":
        require(raw["summary"].get("skipped", 0) == 0 and raw["summary"].get("errors", 0) == 0 and raw["summary"].get("failed", 0) == 0, "pytest suite incomplete")
    return raw["status"]


def validate_attempt(attempt, scope, root, scope_hash):
    require(isinstance(attempt, dict), "attempt must be an object")
    require(attempt.get("schema_version") == 1 and attempt.get("kind") == "test-attempt", "invalid attempt")
    require(attempt.get("scope_sha256") == scope_hash, "attempt scope mismatch")
    checks = {c["id"]: c for c in scope["checks"]}
    require(attempt.get("check_id") in checks, "unknown attempt check")
    check = checks[attempt["check_id"]]
    text(attempt.get("id"), "attempt id")
    require(re.fullmatch(r"[A-Za-z0-9_-]+", attempt["id"]), "unsafe attempt id")
    start, end = stamp(attempt.get("started_at")), stamp(attempt.get("finished_at"))
    require(stamp(scope["frozen_at"]) <= start <= end <= datetime.now(timezone.utc), "execution predates scope or invalid/future interval")
    target = next(t for t in scope["targets"] if t["id"] == check["target_id"])
    require(attempt.get("target") == target, "attempt target mismatch")
    require(attempt.get("status") in {"passed", "failed", "blocked", "skipped", "inconclusive", "error"}, "invalid attempt status")
    require(attempt.get("cleanup_status") in {"passed", "failed", "not-required", "unknown"}, "invalid cleanup status")
    if check["cleanup"] == "required":
        require(attempt["cleanup_status"] != "not-required", "cleanup required by scope")
    capabilities = {c["id"]: c for c in scope["capabilities"]}
    if attempt["status"] in {"passed", "failed"}:
        require(all(capabilities[c]["authorization"] == "granted" and capabilities[c]["availability"] in {"available", "limited"} for c in check["capability_ids"]), "execution lacks capability/authorization")
    evidence = attempt.get("evidence", [])
    require(isinstance(evidence, list), "evidence must be a list")
    if attempt["status"] in {"passed", "failed"}:
        require(bool(evidence), "passed/failed requires evidence")
    else:
        text(attempt.get("reason"), "non-verdict reason")
    for entry in evidence:
        require(isinstance(entry, dict), "evidence entry must be an object")
        path = inside(root, entry["path"])
        require(digest(path) == entry["sha256"], "evidence content changed")
        require(start <= stamp(entry["collected_at"]) <= end, "evidence timestamp outside attempt")
        text(entry.get("collector"), "evidence collector")
    if evidence:
        raw = load(inside(root, evidence[0]["path"]))
        require(outcome(raw, check["binding"]) == attempt["status"], "attempt reinterprets raw result")
    if check["cleanup"] == "required" and attempt["cleanup_status"] == "passed":
        text(attempt.get("cleanup_basis"), "cleanup evidence basis")
    return check


def record(draft, root, directory):
    directory = Path(directory)
    scope = load(directory / "scope.json")
    validate_scope(scope, root)
    attempt = load(draft)
    attempt.update(schema_version=1, kind="test-attempt", scope_sha256=digest(directory / "scope.json"))
    for evidence in attempt.get("evidence", []):
        evidence["sha256"] = digest(inside(root, evidence["path"]))
    validate_attempt(attempt, scope, root, attempt["scope_sha256"])
    write_new(directory / "attempts" / (attempt["id"] + ".json"), attempt)
    return attempt


def evaluate(root, directory, current_targets):
    directory = Path(directory)
    scope = load(directory / "scope.json")
    checks = validate_scope(scope, root, verify_sources=False)
    require("frozen_at" in scope, "scope not frozen")
    scope_hash = digest(directory / "scope.json")
    stale = []
    for source in scope["sources"]:
        try:
            if digest(inside(root, source["path"])) != source["sha256"]:
                stale.append(source["id"])
        except ContractError:
            stale.append(source["id"])
    require(isinstance(current_targets, list), "current targets must be explicitly supplied")
    if current_targets != scope["targets"]:
        stale.append("targets")
    attempts, seen = [], set()
    for path in sorted((directory / "attempts").glob("*.json")):
        require(path.resolve().is_relative_to(directory.resolve()), "attempt symlink escapes run")
        item = load(path)
        validate_attempt(item, scope, root, scope_hash)
        require(item["id"] not in seen, "duplicate attempt id")
        seen.add(item["id"])
        attempts.append(item)
    results = {}
    for key, check in checks.items():
        rows = [a for a in attempts if a["check_id"] == key]
        statuses = {a["status"] for a in rows}
        status = "not-run"
        if rows:
            status = "passed" if statuses == {"passed"} else "failed" if "failed" in statuses else "error" if "error" in statuses else "blocked" if "blocked" in statuses else "inconclusive"
            if "passed" in statuses and len(statuses) > 1:
                status = "inconclusive"
            if any(a["cleanup_status"] in {"failed", "unknown"} for a in rows):
                status = "inconclusive"
        results[key] = {"status": status, "attempt_ids": [a["id"] for a in rows], "required": check["required"],
                        "case_id": check["case_id"], "target_id": check["target_id"], "oracle": check["oracle"],
                        "requirement_refs": check["requirement_refs"],
                        "reasons": [a["reason"] for a in rows if a.get("reason")],
                        "evidence": [e for a in rows for e in a.get("evidence", [])]}
    # A dependent pass needs a prior successful dependency, not a later repair.
    for key, check in checks.items():
        for row in [a for a in attempts if a["check_id"] == key and a["status"] == "passed"]:
            for dep in check["depends_on"]:
                prior = [a for a in attempts if a["check_id"] == dep and a["status"] == "passed" and stamp(a["finished_at"]) <= stamp(row["started_at"])]
                if not prior or results[dep]["status"] != "passed":
                    results[key]["status"] = "inconclusive"
    # Propagate failed prerequisites regardless of source-list ordering.
    for _ in checks:
        changed = False
        for key, check in checks.items():
            if results[key]["status"] == "passed" and any(results[d]["status"] != "passed" for d in check["depends_on"]):
                results[key]["status"] = "inconclusive"
                changed = True
        if not changed:
            break
    required = [v["status"] for v in results.values() if v["required"]]
    verdict = "passed" if all(s == "passed" for s in required) else "failed" if "failed" in required else "blocked" if any(s in {"not-run", "blocked"} for s in required) else "inconclusive"
    return {"schema_version": 1, "kind": "test-acceptance", "scope_sha256": scope_hash,
            "run_id": scope["run_id"], "targets": scope["targets"], "source_revision": scope.get("source_revision"),
            "mode": scope["mode"], "record_validity": "valid", "acceptance_status": "stale" if stale else verdict,
            "execution_status": "not-run" if not attempts else "recorded",
            "coverage_status": "complete" if all(v["attempt_ids"] for v in results.values() if v["required"]) else "partial",
            "stale_sources": stale, "checks": results, "attempts_sha256": fingerprint(attempts),
            "limitations": ["Content hashes do not authenticate external facts; scope, targets and observations require supported provenance."]}


def migrate(source, output=None):
    raw = load(source)
    require(isinstance(raw, dict), "legacy report must be an object")
    require(raw.get("kind") != "legacy-test-record", "already migrated")
    require(raw.get("schema_version") == 1 and (raw.get("runner") in {"schemathesis", "pytest", "testkit-arazzo"} or "workflow_result" in raw), "unsupported legacy result")
    require(raw.get("status") in {"passed", "failed", "error"}, "invalid legacy status")
    result = {"schema_version": 1, "kind": "legacy-test-record", "original_sha256": digest(source),
              "original": raw, "historical_status": raw["status"], "acceptance_eligible": False,
              "missing": ["pre-execution scope", "verified target identity", "assertion bindings"],
              "migration": "Re-run under frozen scope for current acceptance; retain this as historical evidence."}
    if output:
        write_new(output, result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    for name in ("freeze", "record", "evaluate"):
        p = sub.add_parser(name)
        p.add_argument("--root", type=Path, required=True)
        p.add_argument("--run-dir", type=Path, required=True)
        if name != "evaluate":
            p.add_argument("--input", type=Path, required=True)
        else:
            p.add_argument("--current-targets", type=Path, required=True)
            p.add_argument("--output", type=Path)
    p = sub.add_parser("migrate")
    p.add_argument("--input", type=Path, required=True)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        if args.action == "freeze":
            result = freeze(args.input, args.root, args.run_dir)
        elif args.action == "record":
            result = record(args.input, args.root, args.run_dir)
        elif args.action == "migrate":
            result = migrate(args.input, args.output)
        else:
            result = evaluate(args.root, args.run_dir, load(args.current_targets))
            if args.output:
                write_new(args.output, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("acceptance_status", "passed") == "passed" else 1
    except (ContractError, OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        print(json.dumps({"record_validity": "invalid", "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
