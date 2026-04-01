#!/usr/bin/env python3
"""Generate or incrementally update project.yaml, a reusable flow YAML,
and config/.env.example.

Key safety invariants:
  - project.yaml: if it already exists, load it and only fill missing
    top-level keys; never overwrite user-customized values.
  - config/.env.example: append-only for missing keys.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

import yaml

_TEMPLATE_PATH = Path(__file__).resolve().parent / ".." / ".." / "apitestspec-shared" / "scripts" / "_project_template.py"
_spec = importlib.util.spec_from_file_location("_project_template", _TEMPLATE_PATH)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
build_project_spec = _mod.build_project_spec


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge *override* into *base*, keeping existing values."""
    merged = dict(base)
    for key, val in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(val, dict):
            merged[key] = _deep_merge(merged[key], val)
        elif key not in merged:
            merged[key] = val
    return merged


def _ensure_project_yaml(path: Path, project_name: str) -> None:
    template = build_project_spec(project_name)
    if path.exists():
        try:
            existing = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            existing = {}
        merged = _deep_merge(existing, template)
        if merged == existing:
            return
    else:
        merged = template
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(merged, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _existing_keys(path: Path) -> set[str]:
    keys: set[str] = set()
    if not path.exists():
        return keys
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        keys.add(stripped.split("=", 1)[0].strip())
    return keys


def _ensure_env_example(path: Path, keys: list[str]) -> None:
    existing = _existing_keys(path)
    missing: list[str] = []
    if "BASE_URL" not in existing:
        missing.append("BASE_URL=http://localhost:8080")
    for key in keys:
        if key not in existing:
            missing.append(f"{key}=CHANGE_ME_{key}")
    if not missing:
        return
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(missing) + "\n", encoding="utf-8")
        return
    original = path.read_text(encoding="utf-8")
    suffix = "\n" if not original.endswith("\n") else ""
    path.write_text(original + suffix + "\n".join(missing) + "\n", encoding="utf-8")


def _parse_json_body(raw_body: str) -> dict:
    try:
        return json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid --body JSON: {exc}")


def _parse_extract_args(items: list[str]) -> dict[str, str]:
    extract: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise SystemExit(f"Invalid --extract value: {item}")
        key, value = item.split("=", 1)
        extract[key.strip()] = value.strip()
    return extract


def _build_flow_spec(flow_name: str, method: str, path: str, body: dict, extract: dict[str, str]) -> dict:
    return {
        "flows": {
            flow_name: {
                "steps": [
                    {
                        "name": flow_name,
                        "request": {
                            "method": method.upper(),
                            "url": path,
                            "json": body,
                        },
                        "extract": extract,
                        "validate": [{"eq": ["status_code", 200]}],
                    }
                ]
            }
        }
    }


def _extract_env_keys(body: dict) -> list[str]:
    env_keys = []
    for token in json.dumps(body, ensure_ascii=False).split("${ENV.")[1:]:
        env_keys.append(token.split("}", 1)[0])
    return env_keys


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Generate or update project.yaml, reusable flow YAML, and .env.example")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--project-name", required=True)
    parser.add_argument("--flow-name", required=True)
    parser.add_argument("--method", required=True)
    parser.add_argument("--path", required=True)
    parser.add_argument("--body", default="{}")
    parser.add_argument("--extract", action="append", default=[])
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    flows_dir = output_dir / "flows"
    flows_dir.mkdir(parents=True, exist_ok=True)

    body = _parse_json_body(args.body)
    extract = _parse_extract_args(args.extract)

    _ensure_project_yaml(output_dir / "project.yaml", args.project_name)

    flow_path = flows_dir / f"{args.flow_name}.yaml"
    new_flow = _build_flow_spec(args.flow_name, args.method, args.path, body, extract)
    if flow_path.exists():
        try:
            existing = yaml.safe_load(flow_path.read_text(encoding="utf-8")) or {}
        except Exception:
            existing = {}
        merged = _deep_merge(existing, new_flow)
    else:
        merged = new_flow
    flow_path.write_text(
        yaml.safe_dump(merged, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    _ensure_env_example(output_dir / "config" / ".env.example", _extract_env_keys(body))
    print(f"Updated project.yaml, flows/{args.flow_name}.yaml, and config/.env.example in {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
