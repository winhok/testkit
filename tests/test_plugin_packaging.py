import json
import os
import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class TestPluginPackaging(unittest.TestCase):
    def test_codex_plugin_manifest_is_complete(self):
        manifest_path = REPO_ROOT / ".codex-plugin" / "plugin.json"
        manifest = _load_json(manifest_path)

        self.assertEqual(manifest["name"], "testkit")
        self.assertEqual(manifest["version"], "1.0.9")
        self.assertEqual(manifest["skills"], "./skills/")
        self.assertEqual(manifest["author"]["name"], "winhok")

        interface = manifest["interface"]
        self.assertEqual(interface["displayName"], "TestKit")
        self.assertEqual(interface["category"], "Developer Tools")
        self.assertEqual(interface["developerName"], "winhok")
        self.assertGreaterEqual(len(interface["defaultPrompt"]), 1)
        self.assertLessEqual(len(interface["defaultPrompt"]), 3)

        for asset_key in ("composerIcon", "logo"):
            asset_path = REPO_ROOT / interface[asset_key]
            self.assertTrue(asset_path.exists(), f"missing asset: {asset_path}")

    def test_codex_marketplace_points_to_repo_plugin(self):
        marketplace_path = REPO_ROOT / ".agents" / "plugins" / "marketplace.json"
        marketplace = _load_json(marketplace_path)

        self.assertEqual(marketplace["name"], "testkit-marketplace")
        self.assertEqual(marketplace["interface"]["displayName"], "TestKit Local Plugins")

        [plugin] = [entry for entry in marketplace["plugins"] if entry["name"] == "testkit"]
        self.assertEqual(plugin["source"], {"source": "local", "path": "./plugins/testkit"})
        self.assertEqual(
            plugin["policy"],
            {
                "installation": "AVAILABLE",
                "authentication": "ON_INSTALL",
            },
        )
        self.assertEqual(plugin["category"], "Developer Tools")

        plugin_root = REPO_ROOT / "plugins" / "testkit"
        self.assertTrue((plugin_root / ".codex-plugin" / "plugin.json").exists())
        self.assertTrue((plugin_root / "skills").exists())

    def test_readme_documents_codex_installation(self):
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("### Codex", readme)
        self.assertIn(".codex-plugin/plugin.json", readme)
        self.assertIn(".agents/plugins/marketplace.json", readme)
        self.assertIn("python scripts/test_all.py", readme)

    def test_manifest_sync_version_and_keywords(self):
        claude = _load_json(REPO_ROOT / ".claude-plugin" / "marketplace.json")["plugins"][0]
        cursor = _load_json(REPO_ROOT / ".cursor-plugin" / "plugin.json")
        codex = _load_json(REPO_ROOT / ".codex-plugin" / "plugin.json")

        self.assertEqual(claude["version"], cursor["version"], "claude vs cursor version mismatch")
        self.assertEqual(claude["version"], codex["version"], "claude vs codex version mismatch")

        cursor_kw = sorted(cursor.get("keywords", []))
        codex_kw = sorted(codex.get("keywords", []))
        self.assertEqual(cursor_kw, codex_kw, "cursor vs codex keywords mismatch")

        for manifest, label in [(claude, "claude"), (cursor, "cursor"), (codex, "codex")]:
            self.assertTrue(
                manifest.get("description", "").strip(),
                f"{label} manifest missing description",
            )

    def test_repository_test_runner_executes_packaging_check(self):
        if os.environ.get("TESTKIT_TEST_ALL_CHILD") == "1":
            self.skipTest("avoid recursive test_all invocation")

        runner = REPO_ROOT / "scripts" / "test_all.py"
        self.assertTrue(runner.exists())

        result = subprocess.run(
            [sys.executable, str(runner), "--only", "packaging"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("packaging", result.stdout)


if __name__ == "__main__":
    unittest.main()
