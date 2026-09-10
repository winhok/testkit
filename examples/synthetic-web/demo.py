#!/usr/bin/env python3
"""Exercise the protocol with explicitly synthetic observations, without external tools."""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "_test-run-shared" / "scripts"))
from test_run import evaluate, freeze, load, record, write_new


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args()
    root = args.output_dir.resolve()
    if root.exists():
        p.error("output directory must be new")
    root.mkdir(parents=True)
    scope = load(Path(__file__).with_name("scope-draft.json"))
    scope["sources"][0]["path"] = "check.json"
    write_new(root / "check.json", load(Path(__file__).with_name("check.json")))
    write_new(root / "draft.json", scope)
    freeze(root / "draft.json", root, root / "run")
    started = datetime.now(timezone.utc).isoformat()
    write_new(root / "raw.json", {"assertion": {"status": "passed", "actual": "confirmed", "basis": "synthetic protocol fixture, not browser execution", "method": "tool"}})
    finished = datetime.now(timezone.utc).isoformat()
    attempt = {"id": "attempt-1", "check_id": "check-1", "target": scope["targets"][0], "started_at": started, "finished_at": finished, "status": "passed", "cleanup_status": "not-required", "evidence": [{"path": "raw.json", "collector": "synthetic-demo", "collected_at": finished}]}
    write_new(root / "attempt.json", attempt)
    record(root / "attempt.json", root, root / "run")
    result = evaluate(root, root / "run", scope["targets"])
    write_new(root / "acceptance.json", result)
    print(json.dumps({"origin": "synthetic", "result": result}, indent=2))


if __name__ == "__main__":
    main()
