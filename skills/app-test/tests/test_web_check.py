import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/web_check.py'
spec = importlib.util.spec_from_file_location('web_check', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CheckTests(unittest.TestCase):
    def test_missing_tools_blocks(self):
        with patch.object(module.shutil, 'which', return_value=None):
            report = module.check()
        self.assertEqual(report['status'], 'blocked')
        self.assertEqual(report['candidate_routes'], [])

    def test_ego_first_but_not_ready(self):
        with patch.object(module.shutil, 'which', return_value='/private/tool'):
            report = module.check(['computer-use'])
        self.assertEqual(report['candidate_routes'], ['ego-lite', 'agent-browser', 'computer-use'])
        self.assertFalse(report['session_ready'])
        self.assertNotIn('/private/tool', str(report))

    def test_node_alone_is_not_browser(self):
        with patch.object(module.shutil, 'which', side_effect=lambda name: '/tool' if name == 'node' else None):
            self.assertEqual(module.check()['status'], 'blocked')

    def test_host_connector_without_cli(self):
        with patch.object(module.shutil, 'which', return_value=None):
            report = module.check(['browser-connector'])
        self.assertEqual(report['candidate_routes'], ['browser-connector'])
        self.assertEqual(report['authentication'], 'not-checked')


if __name__ == '__main__':
    unittest.main()
