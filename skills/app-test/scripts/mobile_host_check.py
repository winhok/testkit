#!/usr/bin/env python3
"""Read-only command inventory, not a device/session readiness assertion."""
import argparse
import json
import shutil


def check(platform):
    required = ('node', 'adb') if platform == 'android' else ('xcrun', 'xcodebuild', 'appium')
    available = {name: shutil.which(name) is not None for name in required}
    return {'schema_version': 1, 'platform': platform, 'commands': available,
            'missing_commands': [name for name, exists in available.items() if not exists],
            'provider': 'mobile-next/mobile-mcp' if platform == 'android' else 'appium-xcuitest',
            'mcp_connection': 'not-checked', 'device_connection': 'not-checked',
            'session_ready': False, 'mutations_performed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--platform', choices=('android', 'ios'), required=True)
    result = check(parser.parse_args().platform)
    print(json.dumps(result, indent=2))
    raise SystemExit(1 if result['missing_commands'] else 0)
