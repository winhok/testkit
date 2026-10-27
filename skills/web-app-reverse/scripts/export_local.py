#!/usr/bin/env python3
"""Normalize user-exported static files into the same verified Web capture contract."""
import argparse
import json
from pathlib import Path
from urllib.parse import quote, urljoin, urlsplit

from capture_io import MAX_BODY, MAX_INPUT, digest, export_data
from inspect_assets import normalize_site_origin


def export_local(root, destination, site_origin, base_path='/'):
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError('local input must be a directory')
    site_origin = normalize_site_origin(site_origin)
    if not base_path.startswith('/') or not base_path.endswith('/') or urlsplit(base_path).query or urlsplit(base_path).fragment or '..' in base_path.split('/') or base_path.startswith('//'):
        raise ValueError('base-path must be a root-relative directory path')
    types = {'.js':'text/javascript','.mjs':'text/javascript','.cjs':'text/javascript',
             '.jsx':'text/javascript','.ts':'text/javascript','.tsx':'text/javascript',
             '.html':'text/html','.htm':'text/html','.css':'text/css','.map':'application/json'}
    records = []
    total = 0
    for path in sorted(root.rglob('*')):
        if not path.is_file() or not path.resolve().is_relative_to(root) or path.suffix.lower() not in types:
            continue
        if len(records) >= 200:
            raise ValueError('local asset limit exceeded')
        row = {'url':urljoin(site_origin + base_path, quote(path.relative_to(root).as_posix(),safe='/')),
               'mimeType':types[path.suffix.lower()], 'collection':'local-file'}
        with path.open('rb') as stream:
            raw = stream.read(MAX_BODY+1)
        if len(raw) > MAX_BODY:
            row['reason']='body-size-limit'
        else:
            try:
                row['text']=raw.decode('utf-8')
            except UnicodeDecodeError:
                row['reason']='body-not-retained'
        total += len(raw)
        if total > MAX_INPUT:
            raise ValueError('local source budget exceeded')
        records.append(row)
    if not records:
        raise ValueError('no supported local assets')
    capture={'schema_version':1,'kind':'web-page-capture','resources':records,'coverage':{'kind':'local-directory'}}
    encoded=json.dumps(capture,ensure_ascii=False).encode()
    return export_data(capture,digest(encoded),destination,site_origin)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True)
    parser.add_argument('--output-dir',required=True)
    parser.add_argument('--site-origin',required=True)
    parser.add_argument('--base-path',default='/')
    args=parser.parse_args()
    try:
        report=export_local(args.root,args.output_dir,args.site_origin,args.base_path)
        print(f"Exported {report['coverage']['exported_sources']} local sources")
        return 0
    except (OSError,ValueError,TypeError,UnicodeError):
        print('Local export failed: check root, source limits, base path and destination')
        return 2


if __name__=='__main__':
    raise SystemExit(main())
