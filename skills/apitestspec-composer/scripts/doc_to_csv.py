#!/usr/bin/env python3
"""Export YAML/JSON API specs to CSV."""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _spec_table import COLUMNS, load_spec, spec_to_rows


def main():
    parser = argparse.ArgumentParser(description="Export YAML/JSON API specs to CSV")
    parser.add_argument("--input", "-i", required=True, help="Input YAML/JSON spec path")
    parser.add_argument("--output", "-o", required=True, help="Output CSV path")
    args = parser.parse_args()

    inp = Path(args.input)
    if not inp.exists():
        raise FileNotFoundError(f"Input file not found: {inp}")

    rows = spec_to_rows(load_spec(inp))

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    print(f"Exported {len(rows)} rows to {out}")


if __name__ == "__main__":
    main()
