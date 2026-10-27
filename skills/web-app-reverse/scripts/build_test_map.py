#!/usr/bin/env python3
"""Build a provenance-linked Web test map from a verified local capture export."""
import argparse
import json
import re
from pathlib import Path
import subprocess
from urllib.parse import urljoin, urlsplit

from capture_io import digest, private_json, verified_sources
from inspect_assets import DOMInventory, normalize_site_origin, origin_label, safe_path


def build(root, site_origin, document_url=None):
    site_origin = normalize_site_origin(site_origin)
    manifest, sources = verified_sources(root)
    if manifest.get('site_origin_sha256') != digest(site_origin.encode()):
        raise ValueError('site origin differs from exported capture')
    if document_url is not None and origin_label(document_url, site_origin) != 'target-origin':
        raise ValueError('document URL must belong to selected site origin')
    javascript = [row for row in sources if row['file'].endswith('.js')]
    try:
        process = subprocess.run(['node', '--max-old-space-size=256', str(Path(__file__).with_name('analyze_ast.mjs'))],
                                 input=json.dumps([{'id': row['id'], 'text': row['text']} for row in javascript]),
                                 text=True, capture_output=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        raise ValueError('AST runtime unavailable; install Node/parser or reduce selected assets') from None
    if process.returncode:
        raise ValueError('AST parser unavailable or analysis limit exceeded; run npm ci for this skill')
    analysis = json.loads(process.stdout)
    by_id = {row['id']: row for row in sources}
    by_url = {}
    for row in manifest['resources']:
        by_url.setdefault(row['source_url'], []).append(row)
    nodes, edges, candidates, unknowns = [], [], [], list(manifest['unknowns'])
    for row in manifest['resources']:
        nodes.append({'id': row['id'], 'kind': 'resource', 'path': row['url_path'],
                      'origin_label': row['origin_label'], 'sha256': row['sha256'], 'status': row['status'],
                      'locator': row['locator']})
        if row['status'] != 'available':
            unknowns.append({'source_id': row['id'], 'reason': row.get('reason', 'body-not-retained')})
    def identity(kind, value):
        return kind + '-' + digest(json.dumps(value, sort_keys=True).encode())[:16]
    def provenance(source, line=1, column=0):
        return {'source_id': source['id'], 'sha256': source['sha256'], 'line': line, 'column': column}
    def candidate(kind, source, location, target, actions, expected, data):
        candidate_id = identity('test', [source['id'], location, kind, target])
        candidates.append({'id': candidate_id, 'classification': 'test-candidate', 'authority': 'reference',
                           'kind': kind, 'target': target, 'provenance': provenance(source, **location),
                           'role': 'confirm-with-user', 'preconditions': ['selected environment', 'selected session and role; authenticate when required'],
                           'test_data': data, 'actions': actions, 'oracle': expected,
                           'automation': 'Midscene UI with deterministic business checks',
                           'side_effects': 'within-task-authorization', 'priority': 'review-required'})
    for result in analysis:
        source = by_id[result['id']]
        for unknown in result['unknowns']:
            unknowns.append({'source_id': source['id'], **unknown})
        for route in result['routes']:
            value = safe_path(route['path'])
            node_id = identity('route', [source['origin_label'], digest(urlsplit(route['path']).path.encode())])
            nodes.append({'id': node_id, 'kind': 'route', 'path': value, 'origin_label': source['origin_label'],
                          'classification': 'static-candidate', 'mechanism': route['mechanism']})
            edges.append({'from': source['id'], 'to': node_id, 'relation': 'declares-route',
                          'provenance': provenance(source, route['line'], route['column'])})
            candidate('route-navigation', source, {'line': route['line'], 'column': route['column']}, value,
                      ['open confirmed route', 'refresh', 'back/forward', 'check selected role access'],
                      ['expected page and business state', 'permission outcome confirmed against requirements'],
                      ['valid and invalid route parameters'] if ':' in value or '*' in value else ['confirmed route'])
        for request in result['requests']:
            value = request['value']
            if not value.startswith(('/', 'http://', 'https://')) and document_url is None:
                unknowns.append({'source_id': source['id'], 'line': request['line'], 'reason': 'request-document-base-required'})
                continue
            resolved = urljoin(document_url or site_origin + '/', value)
            if urlsplit(resolved).scheme not in {'http', 'https'}:
                unknowns.append({'source_id': source['id'], 'line': request['line'], 'reason': 'unsupported-request-scheme'})
                continue
            label, path = origin_label(resolved, site_origin), safe_path(resolved)
            path_sha = digest(urlsplit(resolved).path.encode())
            method = request['method']
            matches = [record['id'] for record in manifest['network'] if record['origin_label'] == label
                       and record.get('path_sha256') == path_sha and method is not None and record['method'] == method]
            node_id = identity('endpoint', [label, path_sha, method])
            nodes.append({'id': node_id, 'kind': 'endpoint', 'path': path, 'origin_label': label, 'path_sha256': path_sha, 'method': method,
                          'classification': 'static-candidate', 'historical_matches': matches,
                          'reconciliation': 'method-unknown' if method is None else 'historical-match' if matches else 'not-observed-in-capture'})
            edges.append({'from': source['id'], 'to': node_id, 'relation': 'request-callsite',
                          'provenance': provenance(source, request['line'], request['column'])})
            for match in matches:
                edges.append({'from': node_id, 'to': match, 'relation': 'matches-recorded-endpoint'})
            candidate('request-ui-branch', source, {'line': request['line'], 'column': request['column']},
                      {'origin_label': label, 'path': path, 'method': method},
                      ['identify UI trigger', 'observe loading/success/error states', 'check role and input boundaries'],
                      ['business outcome independently verified', 'error recovery state'],
                      ['empty and boundary input', 'approved failure fixture'])
        for reference in result['imports']:
            specifier = reference['value']
            resolved = urljoin(source['source_url'], specifier)
            bare = not specifier.startswith(('.', '/', 'http://', 'https://'))
            targets = [] if bare else by_url.get(resolved, [])
            status = 'bare-specifier' if bare else 'missing-resource' if not targets else 'ambiguous-resource' if len(targets) > 1 else 'resolved'
            if status != 'resolved' or targets[0]['status'] != 'available':
                unknowns.append({'source_id': source['id'], 'line': reference['line'], 'reason': status if status != 'resolved' else 'import-body-not-retained'})
            for target in targets:
                edges.append({'from': source['id'], 'to': target['id'], 'relation': reference['mechanism'],
                              'resolution': status, 'provenance': provenance(source, reference['line'], reference['column'])})
        for state in result['states']:
            node_id = identity('state', [source['origin_label'], state['store'], state['key']])
            nodes.append({'id': node_id, 'kind': 'state', 'store': state['store'], 'key': state['key'],
                          'origin_label': source['origin_label'], 'classification': 'static-candidate'})
            edges.append({'from': source['id'], 'to': node_id, 'relation': state['operation'],
                          'provenance': provenance(source, state['line'], state['column'])})
            candidate('state-lifecycle', source, {'line': state['line'], 'column': state['column']},
                      {'store': state['store'], 'key': state['key']}, ['check navigation and refresh state', 'check logout or role change'],
                      ['state lifecycle agreed with requirements'], ['approved test profile'])
    for source in sources:
        if source['file'].endswith('.js'):
            for match in re.finditer(r'[#@]\s*sourceMappingURL\s*=\s*([^\s*]+)', source['text']):
                targets = by_url.get(urljoin(source['source_url'], match.group(1)), [])
                if len(targets) != 1 or targets[0]['status'] != 'available':
                    unknowns.append({'source_id': source['id'], 'reason': 'source-map-unavailable-or-ambiguous'})
                else:
                    edges.append({'from': source['id'], 'to': targets[0]['id'], 'relation': 'declares-source-map',
                                  'provenance': provenance(source)})
        if source['file'].endswith('.map'):
            try:
                source_map = json.loads(source['text'])
                if source_map.get('version') != 3 or not isinstance(source_map.get('sources'), list):
                    raise ValueError('invalid source map')
                for node in nodes:
                    if node['id'] == source['id']:
                        node['source_count'] = len(source_map['sources'])
                        node['embedded_source_count'] = sum(isinstance(value, str) for value in source_map.get('sourcesContent', []))
                unknowns.append({'source_id': source['id'], 'reason': 'source-map-originals-not-analyzed'})
            except (ValueError, TypeError, AttributeError):
                unknowns.append({'source_id': source['id'], 'reason': 'invalid-source-map'})
        if source['file'].endswith('.html'):
            dom = DOMInventory(site_origin)
            dom.feed(source['text'])
            for control in dom.controls:
                if control['required']:
                    candidate('required-input', source, {'line': control['line']}, {'tag': control['tag'], 'type': control['type']},
                              ['identify associated form', 'submit empty input in approved test environment'],
                              ['field validation', 'no unintended business change'], ['empty input'])
            for resource in dom.resources:
                unknowns.append({'source_id': source['id'], 'line': resource['line'], 'reason': 'html-reference-review',
                                 'path': resource['path']})
    for record in manifest['network']:
        nodes.append({'id': record['id'], 'kind': 'recorded-request', **{key: record[key] for key in
                      ('origin_label', 'path', 'path_sha256', 'method', 'status', 'locator', 'classification')}})
        if record['status'] == 0 or record['status'] >= 400:
            unknowns.append({'record_id': record['id'], 'reason': 'recorded-request-failure', 'status': record['status']})
    for source in sources:
        related = [edge['to'] for edge in edges if edge['from'] == source['id'] and edge['relation'] in {'declares-route', 'request-callsite'}]
        if len(related) > 1:
            unknowns.append({'source_id': source['id'], 'reason': 'shared-module-is-not-action-causality'})
    # Deduplicate entities, preserving every callsite as an edge.
    unique_nodes = {}
    for node in nodes:
        unique_nodes.setdefault(node['id'], node)
    ids = set(unique_nodes)
    if any(edge['from'] not in ids or edge['to'] not in ids for edge in edges):
        raise ValueError('dangling evidence relationship')
    return {'schema_version': 1, 'scope': {'capture_sha256': manifest['capture_sha256'], 'authority': 'reference'},
            'coverage': {**manifest['coverage'], 'ast_sources': len(analysis),
                         'ast_parsed': sum(not any(u['reason'] == 'parse-failed' for u in row['unknowns']) for row in analysis)},
            'maps': {'pages': [node for node in unique_nodes.values() if node['kind'] == 'route'],
                     'resources': [node for node in unique_nodes.values() if node['kind'] == 'resource'],
                     'communications': [node for node in unique_nodes.values() if node['kind'] in {'endpoint', 'recorded-request'}],
                     'states': [node for node in unique_nodes.values() if node['kind'] == 'state'],
                     'behaviors': edges, 'test_candidates': list({row['id']: row for row in candidates}.values())},
            'findings': [], 'unknowns': unknowns}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--export-dir', required=True)
    parser.add_argument('--site-origin', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--document-url', help='Explicit page base for relative fetch targets; kept out of output')
    args = parser.parse_args()
    try:
        result = build(args.export_dir, args.site_origin, args.document_url)
        private_json(args.output, result)
        print(f"Test map ready: {len(result['maps']['test_candidates'])} candidates")
        return 0
    except (OSError, ValueError, TypeError, KeyError, UnicodeError):
        print('Map failed: check manifest integrity, parser dependencies and output path')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
