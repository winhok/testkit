"""Offline and loopback protocol tests; none of these contacts a physical device."""
import io
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from ios_appium_smoke import Client, DriverError, ELEMENT, capabilities, local_url, smoke
from mobile_host_check import check
from android_preflight import probe


CAPS = {'platformName':'iOS', 'appium:automationName':'XCUITest', 'appium:udid':'synthetic-device',
        'appium:bundleId':'synthetic.app', 'appium:webDriverAgentUrl':'http://localhost:8100'}


class FakeClient:
    timeout = 1

    def __init__(self, contexts=None, native_visible=True, dom_visible=True, delete_error=False, create_error=None, duplicate_elements=False):
        self.contexts = contexts if contexts is not None else ['NATIVE_APP', 'WEBVIEW_synthetic']
        self.native_visible = native_visible
        self.dom_visible = dom_visible
        self.delete_error = delete_error
        self.create_error = create_error
        self.duplicate_elements = duplicate_elements
        self.current_context = 'NATIVE_APP'
        self.calls = []

    def call(self, method, path, body=None, timeout=None):
        self.calls.append((method,path,body))
        if path == '/status':
            return {'ready':True}
        if path == '/session':
            if self.create_error:
                raise DriverError(self.create_error)
            return {'sessionId':'synthetic-session'}
        if method == 'DELETE':
            if self.delete_error:
                raise DriverError('transport-error')
            return None
        if path.endswith('/context'):
            self.current_context = body['name']
            return None
        if path.endswith('/contexts'):
            return self.contexts
        if path.endswith('/elements'):
            return [{ELEMENT:'synthetic-element'}] * (2 if self.duplicate_elements else 1)
        if path.endswith('/displayed'):
            return self.native_visible if self.current_context == 'NATIVE_APP' else self.dom_visible
        raise AssertionError((method,path,body))


class MobileExecutionTests(unittest.TestCase):
    def test_android_preflight_only_uses_selected_device_read_commands(self):
        calls = []
        def run(command, **kwargs):
            calls.append(command)
            output = 'device' if command[-1]=='get-state' else '14' if command[-1]=='ro.build.version.release' else '0' if command[-1]=='ro.kernel.qemu' else 'versionCode=42 minSdk=26\n versionName=synthetic-1'
            return subprocess.CompletedProcess(command,0,output,'')
        with patch('android_preflight.shutil.which',return_value='/synthetic/adb'):
            result = probe('synthetic-device','synthetic.app',run=run)
        self.assertEqual(result['status'],'device-connected')
        self.assertEqual(result['app']['version_code'],'42')
        self.assertTrue(all(command[1:3]==['-s','synthetic-device'] for command in calls))
        self.assertNotIn('synthetic-device',json.dumps(result))
        self.assertNotIn('synthetic.app',json.dumps(result))
        self.assertFalse(result['physical_device_verified'])

    def test_android_preflight_blocks_unavailable_device(self):
        with patch('android_preflight.shutil.which',return_value='/synthetic/adb'):
            result = probe('synthetic-device',run=lambda *a,**k: subprocess.CompletedProcess(a,1,'','unauthorized'))
        self.assertEqual(result['status'],'blocked')

    def test_android_package_cannot_inject_shell_commands(self):
        with self.assertRaises(ValueError):
            probe('synthetic-device','synthetic.app; reboot')

    def test_capabilities_preserve_data_and_do_not_enable_alert_acceptance(self):
        value = capabilities(CAPS)
        self.assertTrue(value['appium:noReset'])
        for field in ('fullReset','forceAppLaunch','shouldTerminateApp','autoAcceptAlerts','autoDismissAlerts'):
            self.assertFalse(value['appium:'+field])
        self.assertNotIn('appium:noReset', CAPS)

    def test_setup_and_destructive_capabilities_rejected(self):
        for value in ({**CAPS,'appium:fullReset':True}, {**CAPS,'appium:app':'private.ipa'}, {**CAPS,'appium:xcodeOrgId':'synthetic-team'}):
            with self.assertRaises(ValueError):
                capabilities(value)

    def test_remote_credentials_and_invalid_urls_rejected(self):
        for url in (None, 'https://outside.example.invalid', 'http://user:secret@localhost:4723', 'http://localhost:4723?token=secret'):
            with self.assertRaises(ValueError):
                local_url(url)

    def test_native_success_cleans_only_owned_session(self):
        client = FakeClient()
        result = smoke(client,CAPS,'home')
        self.assertEqual(result['status'],'passed')
        self.assertEqual(result['layers']['h5']['status'],'not-requested')
        self.assertEqual(result['cleanup_status'],'passed')
        self.assertEqual(client.calls[-1][:2],('DELETE','/session/synthetic-session'))
        self.assertFalse(result['physical_device_verified'])
        self.assertNotIn('synthetic-device',json.dumps(result))

    def test_hybrid_success_checks_dom_and_restores_native(self):
        client = FakeClient()
        result = smoke(client,CAPS,'home',webview_selector='#ready',wait_seconds=0)
        self.assertEqual(result['status'],'passed')
        self.assertEqual(result['layers']['h5']['status'],'passed')
        self.assertTrue(any(body and body.get('using')=='css selector' for _,_,body in client.calls))
        self.assertEqual(client.current_context,'NATIVE_APP')
        self.assertTrue(any(path == '/session/synthetic-session/appium/contexts' for _,path,_ in client.calls))

    def test_no_webview_does_not_promote_native_success(self):
        result = smoke(FakeClient(contexts=['NATIVE_APP']),CAPS,'home',webview_selector='#ready',wait_seconds=0)
        self.assertEqual(result['layers']['native']['status'],'passed')
        self.assertEqual(result['layers']['h5']['status'],'blocked')
        self.assertEqual(result['status'],'blocked')

    def test_multiple_webviews_require_explicit_selection(self):
        contexts = ['NATIVE_APP','WEBVIEW_a','WEBVIEW_b']
        result = smoke(FakeClient(contexts),CAPS,'home',webview_selector='#ready',wait_seconds=0)
        self.assertIn('webview-ambiguous',result['errors'])
        selected = smoke(FakeClient(contexts),CAPS,'home',webview_selector='#ready',webview_context='WEBVIEW_b',wait_seconds=0)
        self.assertEqual(selected['status'],'passed')

    def test_failed_native_assertion_still_cleans_session(self):
        client = FakeClient(native_visible=False)
        result = smoke(client,CAPS,'home',webview_selector='#ready',wait_seconds=0)
        self.assertEqual(result['status'],'failed')
        self.assertFalse(any(path.endswith('/contexts') for _,path,_ in client.calls))
        self.assertEqual(result['cleanup_status'],'passed')

    def test_duplicate_elements_cannot_count_as_unique_match(self):
        result = smoke(FakeClient(duplicate_elements=True),CAPS,'home')
        self.assertNotEqual(result['status'],'passed')
        self.assertIn('element-ambiguous',result['errors'])

    def test_cleanup_failure_prevents_overall_success(self):
        result = smoke(FakeClient(delete_error=True),CAPS,'home')
        self.assertEqual(result['status'],'inconclusive')
        self.assertEqual(result['layers']['native']['status'],'passed')
        self.assertEqual(result['cleanup_status'],'failed')

    def test_create_timeout_does_not_retry_unknown_session(self):
        client = FakeClient(create_error='transport-error')
        result = smoke(client,CAPS,'home')
        self.assertEqual(result['cleanup_status'],'unknown')
        self.assertEqual(len([1 for method,path,_ in client.calls if method=='POST' and path=='/session']),1)
        self.assertFalse(any(method=='DELETE' for method,_,_ in client.calls))

    def test_explicit_session_rejection_is_blocked(self):
        result = smoke(FakeClient(create_error='session not created'),CAPS,'home')
        self.assertEqual(result['status'],'blocked')
        self.assertEqual(result['cleanup_status'],'not-required')

    def test_check_mode_has_no_network_or_private_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'caps.json'
            path.write_text(json.dumps(CAPS))
            result = subprocess.run([sys.executable,str(SCRIPTS/'ios_appium_smoke.py'),'--server','http://localhost:1','--capabilities',str(path),'--native-id','home','--check'],capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertFalse(json.loads(result.stdout)['execution_performed'])
            self.assertNotIn('synthetic-device',result.stdout)

    def test_host_check_never_claims_session_readiness(self):
        with patch('mobile_host_check.shutil.which',return_value='/synthetic/tool'):
            result = check('ios')
        self.assertEqual(result['missing_commands'],[])
        self.assertFalse(result['session_ready'])
        self.assertEqual(result['device_connection'],'not-checked')

    def test_real_loopback_w3c_transport_roundtrip(self):
        fake = FakeClient()
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):
                pass
            def handle_method(self):
                length = int(self.headers.get('Content-Length',0))
                body = json.loads(self.rfile.read(length)) if length else None
                value = fake.call(self.command,self.path,body)
                raw = json.dumps({'value':value}).encode()
                self.send_response(200)
                self.send_header('Content-Type','application/json')
                self.send_header('Content-Length',str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
            do_GET = do_POST = do_DELETE = handle_method
        server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread = threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            client = Client('http://127.0.0.1:'+str(server.server_port),timeout=2)
            result = smoke(client,CAPS,'home',webview_selector='#ready',wait_seconds=0)
            self.assertEqual(result['status'],'passed')
            self.assertEqual(fake.calls[-1][0],'DELETE')
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == '__main__':
    unittest.main()
