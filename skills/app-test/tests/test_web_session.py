import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/web_session.py'
spec = importlib.util.spec_from_file_location('web_session', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.binding = dict(provider='ego-lite', session='16', page='p1', profile='default', target='fixture')
        self.observation = dict(self.binding, connection='connected', target_confirmed=True,
                                authentication='authenticated')

    def test_resume_then_expire_then_recover(self):
        for auth, reason in [('authenticated', 'ready'), ('required', 'authentication-required'),
                             ('unknown', 'authentication-unknown'), ('authenticated', 'ready')]:
            self.observation['authentication'] = auth
            self.assertEqual(module.diagnose(self.binding, self.observation)['reason'], reason)

    def test_identity_drift_blocks_every_field(self):
        for key in self.binding:
            with self.subTest(key=key):
                changed = dict(self.observation, **{key: 'other'})
                self.assertEqual(module.diagnose(self.binding, changed)['reason'], 'session-mismatch')

    def test_connection_and_target(self):
        for connection, reason in [('disconnected', 'connection-lost'), ('start-failed', 'browser-start-failed'),
                                   ('permission-blocked', 'permission-blocked')]:
            self.assertEqual(module.diagnose(self.binding, dict(self.observation, connection=connection))['reason'], reason)
        self.assertEqual(module.diagnose(self.binding, dict(self.observation, target_confirmed=False))['reason'], 'target-unconfirmed')

    def test_invalid_is_closed(self):
        for value in [None, [], {}, dict(self.observation, target_confirmed='false'),
                      dict(self.observation, authentication='maybe'), dict(self.observation, session=16)]:
            self.assertEqual(module.diagnose(self.binding, value)['status'], 'blocked')

    def test_cli_red_green_and_no_secret_echo(self):
        with tempfile.TemporaryDirectory() as directory:
            binding = Path(directory) / 'binding.json'
            observation = Path(directory) / 'observation.json'
            binding.write_text(json.dumps(self.binding))
            for auth, code in [('required', 2), ('authenticated', 0)]:
                observation.write_text(json.dumps(dict(self.observation, authentication=auth, token='SECRET-SENTINEL')))
                run = subprocess.run([sys.executable, str(SCRIPT), '--binding', str(binding),
                                      '--observation', str(observation)], capture_output=True, text=True)
                self.assertEqual(run.returncode, code)
                self.assertNotIn('SECRET-SENTINEL', run.stdout + run.stderr)
                self.assertFalse(json.loads(run.stdout)['switch_browser'])


if __name__ == '__main__':
    unittest.main()
