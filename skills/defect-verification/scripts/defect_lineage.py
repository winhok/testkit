"""Bind a defect to source failures and a separately evaluated reacceptance run."""
from test_run import digest, evaluate, inside, load, require, stamp, text


def referenced_run(root, reference):
    require(isinstance(reference, dict), "lineage run reference must be an object")
    for key in ("run_dir", "run_id", "scope_sha256"):
        text(reference.get(key), "lineage " + key)
    scope_path = inside(root, reference["run_dir"] + "/scope.json")
    scope = load(scope_path)
    require(isinstance(scope, dict), "lineage scope must be an object")
    require(scope.get("run_id") == reference["run_id"], "lineage run_id mismatch")
    require(digest(scope_path) == reference["scope_sha256"], "lineage scope hash mismatch")
    return scope_path.parent, scope


def check_identity(scope, check_id):
    checks = {c["id"]: c for c in scope["checks"]}
    require(check_id in checks, "lineage check missing: " + check_id)
    check = checks[check_id]
    identity = {key: check[key] for key in ("case_id", "target_id", "oracle", "binding", "effect", "cleanup")}
    identity["depends_on"] = sorted(check["depends_on"])
    if "definition_source_id" in check["binding"]:
        source_id = check["binding"]["definition_source_id"]
        identity["definition_sha256"] = next(s["sha256"] for s in scope["sources"] if s["id"] == source_id)
    return identity


def target(scope, check_id):
    target_id = check_identity(scope, check_id)["target_id"]
    return next(t for t in scope["targets"] if t["id"] == target_id)


def verify_lineage(root, lineage, scopes, directories, phase_results, verification_status, current_targets):
    require(isinstance(lineage, dict), "lineage must be an object")
    source_dir, source = referenced_run(root, lineage.get("source"))
    source_result = evaluate(root, source_dir, source["targets"])
    check_ids = lineage["source"].get("check_ids")
    require(isinstance(check_ids, list) and bool(check_ids)
            and all(isinstance(c, str) and c.strip() for c in check_ids)
            and len(check_ids) == len(set(check_ids)), "lineage check_ids must be unique and nonempty")
    require(source_result["acceptance_status"] == "failed", "lineage source must contain valid failures")
    for check_id in check_ids:
        identity = check_identity(source, check_id)
        require(source_result["checks"][check_id]["status"] == "failed", "lineage source check is not failed")
        require(phase_results["red"]["checks"].get(check_id, {}).get("status") == "failed", "linked RED check did not reproduce failure")
        for phase in ("red", "green"):
            require(identity == check_identity(scopes[phase], check_id), "lineage check identity changed")
            require(next(c for c in scopes[phase]["checks"] if c["id"] == check_id)["required"], "linked RED/GREEN check must be required")
        require(target(source, check_id) == target(scopes["red"], check_id), "source and RED targets differ")
    result = {"source": {**lineage["source"], "attempts_sha256": source_result["attempts_sha256"]},
              "reacceptance_status": "not-run", "closed_check_ids": []}
    if "reacceptance" not in lineage:
        return result
    directory, scope = referenced_run(root, lineage["reacceptance"])
    require(directory not in {source_dir, *directories.values()}, "reacceptance needs a new run")
    previous_ids = {source["run_id"], *(s["run_id"] for s in scopes.values())}
    require(scope["run_id"] not in previous_ids, "reacceptance run_id must be distinct")
    require(scope["mode"] == "acceptance", "reacceptance requires a formal acceptance scope")
    require(current_targets is not None, "reacceptance requires explicit current targets")
    acceptance = evaluate(root, directory, current_targets)
    source_required = {c["id"] for c in source["checks"] if c["required"]}
    accepted_required = {c["id"] for c in scope["checks"] if c["required"]}
    require(source_required <= accepted_required, "reacceptance cannot drop source required checks")
    for check_id in source_required:
        require(check_identity(source, check_id) == check_identity(scope, check_id), "reacceptance changed a source required check")
    require(stamp(scope["frozen_at"]) >= max(stamp(s["frozen_at"]) for s in [source, *scopes.values()]), "reacceptance predates verification scopes")
    for prior in {source_dir, *directories.values()}:
        for path in (prior / "attempts").glob("*.json"):
            require(stamp(scope["frozen_at"]) >= stamp(load(path)["finished_at"]), "reacceptance must start after verification attempts")
    for check_id in check_ids:
        require(check_identity(source, check_id) == check_identity(scope, check_id), "reacceptance check identity changed")
        require(next(c for c in scope["checks"] if c["id"] == check_id)["required"], "reacceptance cannot demote linked checks")
        require(target(scope, check_id) == target(scopes["green"], check_id), "reacceptance is not on verified build")
    result["reacceptance"] = {**lineage["reacceptance"], "result": acceptance}
    result["reacceptance_status"] = acceptance["acceptance_status"]
    if verification_status == "verified" and acceptance["acceptance_status"] == "passed":
        result["closed_check_ids"] = list(check_ids)
    return result
