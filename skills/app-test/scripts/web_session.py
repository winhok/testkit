#!/usr/bin/env python3
"""Classify fresh, redacted browser observations; never reads browser secrets."""
import argparse
import json

IDENTITY = ('provider', 'session', 'page', 'profile', 'target')
CONNECTION = {'connected', 'disconnected', 'start-failed', 'permission-blocked'}
AUTH = {'authenticated', 'required', 'unknown'}


def diagnose(binding, observation):
    """Fail closed on malformed or changed identity. Output fixed labels only."""
    if not isinstance(binding, dict) or not isinstance(observation, dict):
        return result('invalid-observation')
    for record in (binding, observation):
        if any(not isinstance(record.get(k), str) or not record[k].strip() for k in IDENTITY):
            return result('invalid-observation')
    if (not isinstance(observation.get('connection'), str)
            or not isinstance(observation.get('authentication'), str)
            or observation.get('connection') not in CONNECTION
            or type(observation.get('target_confirmed')) is not bool
            or observation.get('authentication') not in AUTH):
        return result('invalid-observation')
    connection = observation['connection']
    if connection != 'connected':
        return result({'disconnected': 'connection-lost', 'start-failed': 'browser-start-failed',
                       'permission-blocked': 'permission-blocked'}[connection])
    if any(binding[k] != observation[k] for k in IDENTITY):
        return result('session-mismatch')
    if not observation['target_confirmed']:
        return result('target-unconfirmed')
    return result({'authenticated': 'ready', 'required': 'authentication-required',
                   'unknown': 'authentication-unknown'}[observation['authentication']])


def result(reason):
    return {'status': 'ready' if reason == 'ready' else 'blocked', 'reason': reason,
            'switch_browser': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binding', required=True)
    parser.add_argument('--observation', required=True)
    args = parser.parse_args()
    try:
        with open(args.binding, encoding='utf-8') as stream:
            binding = json.load(stream)
        with open(args.observation, encoding='utf-8') as stream:
            observation = json.load(stream)
        verdict = diagnose(binding, observation)
    except (OSError, ValueError, TypeError):
        verdict = result('invalid-observation')
    print(json.dumps(verdict))
    return 0 if verdict['status'] == 'ready' else 2


if __name__ == '__main__':
    raise SystemExit(main())
