#!/usr/bin/env python3
"""Bootstrap a minimal case YAML for the apitestspec-composer stage.

This script only produces ``cases/*.yaml``.  It deliberately does NOT
generate ``project.yaml``, ``flows/*.yaml``, or ``config/.env.example``
because those belong to the flow-configurator stage.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import yaml


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _build_case_payload(case_id: str, case_name: str) -> dict:
    return {
        "cases": [
            {
                "id": case_id,
                "name": case_name,
                "steps": [
                    {
                        "name": "sample_request",
                        "request": {"method": "GET", "url": "/health"},
                        "validate": [{"eq": ["status_code", 200]}],
                    }
                ],
            }
        ]
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap a framework-native API case spec")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--case-name", required=True)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    _write_yaml(
        output_dir / "cases" / f"{args.case_id}.yaml",
        _build_case_payload(args.case_id, args.case_name),
    )

    print(f"Created cases/{args.case_id}.yaml in {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
