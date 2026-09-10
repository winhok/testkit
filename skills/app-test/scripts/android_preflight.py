#!/usr/bin/env python3
"""Read selected-device ADB readiness and package version; never performs UI actions."""
import argparse
import json
import re
import shutil
import subprocess


def probe(serial, package=None, run=subprocess.run):
    if not isinstance(serial, str) or not re.fullmatch(r'[A-Za-z0-9_.:-]+', serial):
        raise ValueError('serial must come from current device discovery')
    if package is not None and not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)+', package):
        raise ValueError('invalid Android package identifier')
    adb = shutil.which('adb')
    if not adb:
        return {'status':'blocked','reason':'adb-unavailable','device_connection':'not-checked'}
    def command(*args):
        try:
            result = run([adb,'-s',serial,*args],capture_output=True,text=True,timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            return None
        return result.stdout if result.returncode == 0 else None
    state = command('get-state')
    if state is None or state.strip() != 'device':
        return {'status':'blocked','reason':'device-offline-unauthorized-or-unreachable',
                'device_connection':'blocked','mutations_performed':False}
    release = command('shell','getprop','ro.build.version.release')
    qemu = command('shell','getprop','ro.kernel.qemu')
    result = {'status':'device-connected','device_connection':'connected','native_session':'not-checked',
              'physical_device_verified':False,'os_version':release.strip() if release else None,
              'emulator_signal':(qemu or '').strip()=='1' or serial.startswith('emulator-'),
              'mutations_performed':False}
    if package:
        raw = command('shell','dumpsys','package',package) or ''
        version = re.search(r'^\s*versionName=(.*)$',raw,re.M)
        code = re.search(r'\bversionCode=(\d+)',raw)
        result['app'] = {'metadata_available':bool(version and code),
                         'version_name':version.group(1).strip() if version else None,
                         'version_code':code.group(1) if code else None}
        if not result['app']['metadata_available']:
            result['status'] = 'blocked'
            result['reason'] = 'package-version-unavailable'
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serial',required=True)
    parser.add_argument('--package')
    args = parser.parse_args()
    try:
        result = probe(args.serial,args.package)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        raise SystemExit(1 if result['status']=='blocked' else 0)
    except ValueError as exc:
        print(json.dumps({'status':'invalid','error':str(exc)}))
        raise SystemExit(2)
