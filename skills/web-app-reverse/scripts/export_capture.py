#!/usr/bin/env python3
"""Export retained HAR 1.2 or Web page capture to a new private directory."""
import argparse
from capture_io import export_capture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True)
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--site-origin', required=True)
    parser.add_argument('--allow-origin', action='append', default=[])
    args = parser.parse_args()
    try:
        result = export_capture(args.input, args.output_dir, args.site_origin, args.allow_origin)
        print(f"Exported {result['coverage']['exported_sources']} sources; manifest.json ready")
        return 0
    except (OSError, ValueError, TypeError, KeyError, UnicodeError):
        print('Export failed: check capture format, size, origin scope and destination; existing output preserved')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
