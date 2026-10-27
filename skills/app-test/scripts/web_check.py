#!/usr/bin/env python3
"""Read-only Web tool inventory. Does not launch tools or inspect browser data."""
import argparse
import json
import shutil

TOOLS = ('ego-browser', 'agent-browser', 'node', 'python3')
HOSTS = ('browser-connector', 'computer-use', 'midscene-project')


def check(host_tools=()):
    installed = {name: shutil.which(name) is not None for name in TOOLS}
    declared = {name: name in host_tools for name in HOSTS}
    routes = []
    if installed['ego-browser']:
        routes.append('ego-lite')
    if installed['agent-browser']:
        routes.append('agent-browser')
    routes.extend(name for name in HOSTS if declared[name])
    return {
        'schema_version': 1,
        'status': 'preflight-required' if routes else 'blocked',
        'commands': installed,
        'host_declared': declared,
        'candidate_routes': routes,
        'session_ready': False,
        'authentication': 'not-checked',
        'next_step': 'verify-selected-session' if routes else 'follow-browser-setup',
        'limitations': ['PATH-only', 'host-tools-are-caller-declarations',
                        'no-browser-launch', 'no-session-or-authentication-check'],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host-tool', action='append', choices=HOSTS, default=[],
                        help='Declare a tool actually exposed by the current host; repeatable')
    args = parser.parse_args()
    report = check(args.host_tool)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 2 if report['status'] == 'blocked' else 0


if __name__ == '__main__':
    raise SystemExit(main())
