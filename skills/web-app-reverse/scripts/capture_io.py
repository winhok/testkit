"""Bounded, offline capture normalization and integrity-checked asset export."""
import base64
import binascii
import hashlib
import json
import os
from pathlib import Path
import shutil
from urllib.parse import urlsplit

from inspect_assets import normalize_site_origin, origin_label, safe_path

MAX_INPUT = 32 * 1024 * 1024
MAX_BODY = 2 * 1024 * 1024
MAX_RECORDS = 500


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def load_json(path, limit=MAX_INPUT):
    path = Path(path)
    if not path.is_file():
        raise ValueError('input must be a regular file')
    with path.open('rb') as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('input size limit exceeded')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique), digest(raw)


def private_json(path, value):
    with open(path, 'x', encoding='utf-8', opener=lambda name, flags: os.open(name, flags, 0o600)) as stream:
        json.dump(value, stream, ensure_ascii=True, indent=2, allow_nan=False)


def resource_type(url, mime):
    suffix = urlsplit(url).path.lower().rsplit('.', 1)[-1]
    if 'javascript' in mime or suffix in {'js', 'mjs', 'cjs', 'jsx', 'ts', 'tsx'}:
        return '.js'
    if 'text/html' in mime or suffix in {'html', 'htm'}:
        return '.html'
    if 'text/css' in mime or suffix == 'css':
        return '.css'
    if suffix == 'map':
        return '.map'
    return None


def export_capture(source, destination, site_origin, allowed_origins=()):
    data, capture_sha = load_json(source)
    return export_data(data, capture_sha, destination, site_origin, allowed_origins)


def export_data(data, capture_sha, destination, site_origin, allowed_origins=()):
    site_origin = normalize_site_origin(site_origin)
    allowed = {site_origin, *(normalize_site_origin(value) for value in allowed_origins)}
    if not isinstance(data, dict):
        raise ValueError('capture must be an object')
    is_har = 'log' in data
    if is_har:
        if not isinstance(data['log'], dict) or data['log'].get('version') != '1.2':
            raise ValueError('HAR 1.2 required')
        records = data['log'].get('entries')
    else:
        if data.get('schema_version') != 1 or data.get('kind') != 'web-page-capture':
            raise ValueError('unsupported capture schema')
        records = data.get('resources')
    if not isinstance(records, list) or len(records) > MAX_RECORDS:
        raise ValueError('invalid record list or record limit exceeded')
    resources, network, pending, unknowns = [], [], [], []
    for ordinal, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError('invalid capture record')
        if is_har:
            request, response = record.get('request'), record.get('response')
            if not isinstance(request, dict) or not isinstance(response, dict):
                raise ValueError('invalid HAR request/response')
            url, method, status = request.get('url'), request.get('method'), response.get('status')
            if not isinstance(method, str) or not method.isalpha() or type(status) is not int or not (status == 0 or 100 <= status <= 599):
                raise ValueError('invalid HAR method/status')
            body = response.get('content', {})
            if not isinstance(body, dict):
                raise ValueError('invalid HAR content')
            locator = f'har:entries[{ordinal}]'
        else:
            url, method, status = record.get('url'), None, None
            body = record
            locator = f'capture:resources[{ordinal}]'
        if not isinstance(url, str):
            raise ValueError('resource URL required')
        parsed = urlsplit(url)
        if parsed.scheme not in {'http', 'https'} or parsed.username or parsed.password or not parsed.hostname:
            unknowns.append({'locator': locator, 'reason': 'unsupported-resource-url'})
            continue
        current_origin = normalize_site_origin(f'{parsed.scheme}://{parsed.netloc}')
        if current_origin not in allowed:
            unknowns.append({'locator': locator, 'reason': 'outside-selected-origins'})
            continue
        source_id = 'source-' + digest(f'{capture_sha}:{ordinal}'.encode())[:16]
        label, path = origin_label(url, site_origin), safe_path(url)
        if is_har:
            network.append({'id': f'network-{ordinal}', 'source_id': source_id, 'locator': locator,
                            'origin_label': label, 'path': path, 'path_sha256': digest(parsed.path.encode()), 'method': method.upper(),
                            'status': status, 'classification': 'historical-observed'})
        mime = body.get('mimeType', '')
        if not isinstance(mime, str):
            raise ValueError('invalid MIME type')
        extension = resource_type(url, mime.lower())
        if extension is None:
            continue
        row = {'id': source_id, 'origin_label': label, 'url_path': path,
               'url_sha256': digest(url.encode()), 'locator': locator, 'media_type': mime,
               'collection': 'har-response' if is_har else 'debugger-source' if body.get('collection') == 'debugger-source' else 'local-file' if body.get('collection') == 'local-file' else 'document-projection',
               'status': 'unavailable', 'file': None, 'sha256': None, 'bytes': None}
        # Full source URLs stay in the private manifest solely for exact module resolution.
        # Reports use origin labels and query-free paths instead.
        row['source_url'] = url
        text, encoding = body.get('text'), body.get('encoding')
        if text is None:
            row['reason'] = body.get('reason') if body.get('reason') in {'external-reference-only', 'body-size-limit'} else 'body-not-retained'
        elif not isinstance(text, str):
            raise ValueError('invalid body text')
        elif is_har and (status < 200 or status >= 300):
            row['reason'] = 'non-success-response'
        elif len(text) > MAX_BODY * 2:
            row['reason'] = 'body-size-limit'
        else:
            if encoding == 'base64':
                try:
                    raw = base64.b64decode(text, validate=True)
                except (ValueError, binascii.Error):
                    raise ValueError('invalid base64 body') from None
            elif encoding is None:
                raw = text.encode('utf-8')
            else:
                raise ValueError('unsupported body encoding')
            if len(raw) > MAX_BODY:
                row['reason'] = 'body-size-limit'
            else:
                try:
                    raw.decode('utf-8')
                except UnicodeDecodeError:
                    row['reason'] = 'non-utf8-source'
                else:
                    row.update(status='available', file=f'assets/{source_id}{extension}', sha256=digest(raw), bytes=len(raw))
                    pending.append((row['file'], raw))
        resources.append(row)
    result = {'schema_version': 1, 'kind': 'web-capture-export', 'capture_sha256': capture_sha, 'site_origin_sha256': digest(site_origin.encode()),
              'resources': resources, 'network': network, 'unknowns': unknowns,
              'coverage': {'input_records': len(records), 'exported_sources': len(pending),
                           'unavailable_sources': sum(row['status'] != 'available' for row in resources),
                           'application': 'unknown', 'producer': ({'kind': 'local-directory' if data.get('coverage', {}).get('kind') == 'local-directory' else 'structural-projection', 'truncated': data.get('coverage', {}).get('truncated') is True, 'script_gaps': [gap for gap in data.get('coverage', {}).get('scripts', {}).get('gaps', []) if gap in {'script-budget', 'script-size-limit', 'script-source-unavailable'}]} if not is_har else {'kind': 'HAR-1.2'})}}
    destination = Path(destination)
    destination.mkdir(mode=0o700)  # Exclusive ownership; never overwrite an export.
    try:
        (destination / 'assets').mkdir(mode=0o700)
        for name, raw in pending:
            with open(destination / name, 'xb', opener=lambda name, flags: os.open(name, flags, 0o600)) as stream:
                stream.write(raw)
            if digest((destination / name).read_bytes()) != digest(raw):
                raise ValueError('export readback mismatch')
        private_json(destination / 'manifest.json', result)
    except BaseException:
        shutil.rmtree(destination)
        raise
    return result


def verified_sources(root):
    root = Path(root).resolve()
    manifest, _ = load_json(root / 'manifest.json')
    if manifest.get('kind') != 'web-capture-export' or manifest.get('schema_version') != 1:
        raise ValueError('invalid export manifest')
    if not isinstance(manifest.get('resources'), list) or len(manifest['resources']) > MAX_RECORDS:
        raise ValueError('invalid manifest resources')
    sources = []
    seen = set()
    for row in manifest['resources']:
        if not isinstance(row, dict) or not isinstance(row.get('id'), str) or row['id'] in seen:
            raise ValueError('invalid or duplicate source identity')
        seen.add(row['id'])
        if (not isinstance(row.get('source_url'), str) or digest(row['source_url'].encode()) != row.get('url_sha256')):
            raise ValueError('source URL integrity mismatch')
        if row.get('status') != 'available':
            continue
        name = row.get('file')
        if not isinstance(name, str) or Path(name).is_absolute() or '..' in Path(name).parts:
            raise ValueError('invalid source path')
        path = (root / name).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError('source escapes export or is missing')
        with path.open('rb') as stream:
            raw = stream.read(MAX_BODY + 1)
        if len(raw) > MAX_BODY or len(raw) != row.get('bytes') or digest(raw) != row.get('sha256'):
            raise ValueError('source integrity mismatch')
        sources.append({**row, 'text': raw.decode('utf-8')})
    return manifest, sources
