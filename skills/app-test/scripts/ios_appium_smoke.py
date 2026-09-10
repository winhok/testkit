#!/usr/bin/env python3
"""Check an installed iOS app through an existing local Appium/WDA session service.

--check is offline. --execute creates and cleans up only its own Appium session.
No installation, signing, reset, generic script execution or business navigation.
"""
import argparse
import json
import math
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ELEMENT = 'element-6066-11e4-a52e-4f735466cecf'
MAX_RESPONSE = 2 * 1024 * 1024


class DriverError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def local_url(value):
    if not isinstance(value, str) or not value:
        raise ValueError('local Appium/WDA URL required')
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme not in {'http', 'https'} or parsed.hostname not in {'localhost', '127.0.0.1', '::1'} or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('smoke helper requires a credential-free local Appium/WDA URL')
    _ = parsed.port
    return value.rstrip('/')


def capabilities(value):
    if not isinstance(value, dict):
        raise ValueError('capabilities must be a flat W3C capability object')
    allowed = {'platformName','appium:automationName','appium:udid','appium:bundleId','appium:webDriverAgentUrl',
               'appium:noReset','appium:fullReset','appium:shouldTerminateApp','appium:forceAppLaunch',
               'appium:autoAcceptAlerts','appium:autoDismissAlerts','appium:newCommandTimeout'}
    if set(value) - allowed:
        raise ValueError('unsupported capability; use the runbook for setup or advanced workflows')
    if str(value.get('platformName', '')).lower() != 'ios' or str(value.get('appium:automationName', '')).lower() != 'xcuitest':
        raise ValueError('iOS and XCUITest capabilities required')
    for key in ('appium:udid', 'appium:bundleId'):
        if not isinstance(value.get(key), str) or not re.fullmatch(r'[A-Za-z0-9_.:-]+', value[key]):
            raise ValueError(f'{key} must come from current device/app discovery')
    local_url(value.get('appium:webDriverAgentUrl', ''))
    result = dict(value)
    fixed = {'appium:noReset':True, 'appium:fullReset':False, 'appium:shouldTerminateApp':False,
             'appium:forceAppLaunch':False, 'appium:autoAcceptAlerts':False, 'appium:autoDismissAlerts':False}
    for key, expected in fixed.items():
        if key in value and value[key] is not expected:
            raise ValueError(f'{key} violates state-preserving smoke mode')
        result[key] = expected
    timeout = value.get('appium:newCommandTimeout', 60)
    if type(timeout) is not int or not 1 <= timeout <= 300:
        raise ValueError('newCommandTimeout must be between 1 and 300 seconds')
    result['appium:newCommandTimeout'] = timeout
    return result


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise DriverError('redirect-blocked')


class Client:
    def __init__(self, server, timeout=20):
        self.server = local_url(server)
        if not math.isfinite(timeout) or not 0 < timeout <= 120:
            raise ValueError('command timeout must be in (0, 120] seconds')
        self.timeout = timeout
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def call(self, method, path, body=None, timeout=None):
        request = urllib.request.Request(self.server + path, method=method,
                    data=json.dumps(body).encode() if body is not None else None,
                    headers={'Content-Type':'application/json'})
        try:
            try:
                response = self.opener.open(request, timeout=timeout or self.timeout)
            except urllib.error.HTTPError as exc:
                response = exc
            with response:
                raw = response.read(MAX_RESPONSE + 1)
                status = response.status
            if len(raw) > MAX_RESPONSE:
                raise DriverError('response-too-large')
            envelope = json.loads(raw)
            if not isinstance(envelope, dict) or 'value' not in envelope:
                raise DriverError('invalid-protocol-response')
            value = envelope['value']
            if isinstance(value, dict) and 'error' in value:
                code = value['error']
                safe = {'no such element','stale element reference','session not created','invalid session id','invalid argument','timeout','unknown error'}
                raise DriverError(code if isinstance(code, str) and code in safe else 'webdriver-error')
            if status >= 400:
                raise DriverError('http-error')
            return value
        except DriverError:
            raise
        except (TimeoutError, urllib.error.URLError, OSError):
            raise DriverError('transport-error') from None
        except (ValueError, TypeError):
            raise DriverError('invalid-protocol-response') from None


def segment(value):
    if not isinstance(value, str) or not value:
        raise DriverError('invalid-protocol-identifier')
    return urllib.parse.quote(value, safe='')


def layer(status='not-requested', actual='not requested'):
    return {'status':status, 'actual':actual, 'basis':'Appium protocol observation', 'method':'tool'}


def validate_assertions(native_id, webview_selector, webview_context, wait_seconds):
    if not isinstance(native_id, str) or not native_id.strip():
        raise ValueError('native accessibility id required')
    if not math.isfinite(wait_seconds) or not 0 <= wait_seconds <= 60:
        raise ValueError('WebView wait must be between 0 and 60 seconds')
    if webview_selector is not None and (not isinstance(webview_selector, str) or not webview_selector.strip()):
        raise ValueError('WebView CSS selector must be nonempty')
    if webview_context and not webview_selector:
        raise ValueError('WebView context requires a DOM selector assertion')


def unique_element(value):
    if not isinstance(value, list):
        raise DriverError('invalid-elements-response')
    if not value:
        raise DriverError('no such element')
    if len(value) != 1:
        raise DriverError('element-ambiguous')
    return segment(value[0].get(ELEMENT) if isinstance(value[0], dict) else None)


def smoke(client, caps, native_id, *, webview_selector=None, webview_context=None, wait_seconds=5):
    caps = capabilities(caps)
    validate_assertions(native_id, webview_selector, webview_context, wait_seconds)
    result = {'schema_version':1, 'kind':'ios-appium-smoke', 'provider':'appium-xcuitest',
              'started_at':datetime.now(timezone.utc).isoformat(), 'physical_device_verified':False,
              'build_verification':'requires separate device/build evidence',
              'layers':{'device':layer('blocked','session not established'), 'native':layer('blocked','native assertion not executed'),
                        'webview':layer(), 'h5':layer()}, 'cleanup_status':'not-required', 'errors':[]}
    if webview_selector:
        result['layers']['webview'] = layer('blocked','WebView not selected')
        result['layers']['h5'] = layer('blocked','DOM assertion not executed')
    session = None
    switched = False
    creating = False
    try:
        state = client.call('GET','/status')
        if not isinstance(state, dict) or state.get('ready') is not True:
            raise DriverError('server-not-ready')
        creating = True
        created = client.call('POST','/session',{'capabilities':{'alwaysMatch':caps,'firstMatch':[{}]}})
        if not isinstance(created, dict):
            raise DriverError('invalid-session-response')
        session = segment(created.get('sessionId'))
        creating = False
        prefix = '/session/' + session
        result['layers']['device'] = layer('passed','Appium session established; physical type verified separately')
        client.call('POST',prefix+'/appium/context',{'name':'NATIVE_APP'})
        found = client.call('POST',prefix+'/elements',{'using':'accessibility id','value':native_id})
        element_id = unique_element(found)
        visible = client.call('GET',prefix+'/element/'+element_id+'/displayed')
        result['layers']['native'] = layer('passed' if visible is True else 'failed','native element is displayed' if visible is True else 'native element is not displayed')
        if visible is not True:
            raise DriverError('native-assertion-failed')
        if webview_selector:
            deadline = time.monotonic() + wait_seconds
            candidates = []
            while True:
                contexts = client.call('GET',prefix+'/appium/contexts',timeout=min(client.timeout, max(0.01, deadline-time.monotonic())))
                if not isinstance(contexts, list) or not all(isinstance(c, str) for c in contexts):
                    raise DriverError('invalid-context-list')
                candidates = [c for c in contexts if c.startswith('WEBVIEW')]
                if (webview_context in candidates if webview_context else candidates) or time.monotonic() >= deadline:
                    break
                time.sleep(min(0.2, max(0, deadline-time.monotonic())))
            if webview_context:
                if webview_context not in candidates:
                    raise DriverError('requested-webview-unavailable')
                selected = webview_context
            elif len(candidates) == 1:
                selected = candidates[0]
            else:
                raise DriverError('webview-unavailable' if not candidates else 'webview-ambiguous')
            client.call('POST',prefix+'/appium/context',{'name':selected})
            switched = True
            result['layers']['webview'] = layer('passed','inspectable WebView selected')
            found = client.call('POST',prefix+'/elements',{'using':'css selector','value':webview_selector})
            element_id = unique_element(found)
            visible = client.call('GET',prefix+'/element/'+element_id+'/displayed')
            result['layers']['h5'] = layer('passed' if visible is True else 'failed','DOM element is displayed' if visible is True else 'DOM element is not displayed')
    except DriverError as exc:
        result['errors'].append(exc.code)
        if exc.code == 'no such element':
            result['layers']['h5' if switched else 'native'] = layer('failed','expected element was not found')
        if creating and exc.code in {'transport-error','timeout','invalid-session-response','invalid-protocol-identifier','invalid-protocol-response','response-too-large'}:
            result['cleanup_status'] = 'unknown'
            result['errors'].append('session creation outcome uncertain; inspect server before retrying')
    finally:
        if session:
            result['cleanup_status'] = 'passed'
            if switched:
                try:
                    client.call('POST','/session/'+session+'/appium/context',{'name':'NATIVE_APP'})
                except DriverError:
                    result['errors'].append('native-context-restore-failed')
            try:
                client.call('DELETE','/session/'+session)
            except DriverError:
                result['cleanup_status'] = 'failed'
                result['errors'].append('session-delete-failed')
        result['finished_at'] = datetime.now(timezone.utc).isoformat()
    statuses = [v['status'] for v in result['layers'].values() if v['status'] != 'not-requested']
    result['status'] = 'failed' if 'failed' in statuses else 'blocked' if 'blocked' in statuses else 'passed'
    if result['cleanup_status'] in {'failed','unknown'} or (result['errors'] and result['status']=='passed'):
        result['status'] = 'inconclusive'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', required=True)
    parser.add_argument('--capabilities', type=Path, required=True)
    parser.add_argument('--native-id', required=True)
    parser.add_argument('--webview-selector')
    parser.add_argument('--webview-context')
    parser.add_argument('--wait-seconds', type=float, default=5)
    parser.add_argument('--timeout', type=float, default=20)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check', action='store_true')
    mode.add_argument('--execute', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        caps = capabilities(json.loads(args.capabilities.read_text()))
        client = Client(args.server, args.timeout)
        validate_assertions(args.native_id, args.webview_selector, args.webview_context, args.wait_seconds)
        if args.check:
            print(json.dumps({'status':'configuration-valid', 'device_connection':'not-checked', 'execution_performed':False}))
            return 0
        if not args.output or args.output.exists() or args.output.is_symlink():
            raise ValueError('execute requires a new output file')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8') as stream:
            result = smoke(client, caps, args.native_id, webview_selector=args.webview_selector,
                           webview_context=args.webview_context, wait_seconds=args.wait_seconds)
            json.dump(result, stream, ensure_ascii=False, indent=2)
        print(json.dumps({'status':result['status'],'cleanup_status':result['cleanup_status']}))
        return 0 if result['status']=='passed' else 1
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({'status':'invalid','error':str(exc)}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
