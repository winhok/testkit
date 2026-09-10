import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILLS / "web-app-reverse" / "scripts"))
sys.path.insert(0, str(SKILLS / "video-to-issue" / "scripts"))
from inspect_assets import discover_assets, inspect
from sample_video import sample


class InspectionTests(unittest.TestCase):
    def test_candidates_redact_query_and_form_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "index.html").write_text('<input type="hidden" value="private-secret"><script src="/main.js?token=private-secret"></script>')
            (root / "main.js").write_text('fetch("/api/check?token=private-secret"); localStorage.getItem("auth")')
            result = inspect(root, ["index.html", "main.js"])
            self.assertNotIn("private-secret", json.dumps(result))
            self.assertEqual(result["assets"][1]["request_candidates"][0]["path"], "/api/check")
            self.assertEqual(result["assets"][1]["classification"], "static-candidate")

    def test_large_assets_report_not_inspected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "big.js").write_text("x" * 100)
            self.assertEqual(inspect(root, ["big.js"], max_bytes=10)["assets"][0]["status"], "not-inspected")

    def test_service_origins_and_explicit_methods_survive_redaction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'main.js').write_text('axios.post("https://alpha.example.invalid/api/status?token=secret"); axios.get("https://beta.example.invalid/api/status");')
            rows = inspect(root, ['main.js'])['assets'][0]['request_candidates']
            self.assertEqual(len({r['origin_label'] for r in rows}), 2)
            self.assertEqual([r['method'] for r in rows], ['POST', 'GET'])
            self.assertNotIn('secret', json.dumps(rows))

    def test_runtime_transport_candidates_and_signal_locations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "main.js").write_text(
                'const xhr = new XMLHttpRequest();\n'
                'xhr.open("PATCH", "/api/profile?token=secret");\n'
                'navigator.sendBeacon("/audit", "synthetic");\n'
                'new WebSocket("wss://stream.example.invalid/events");\n'
                'new EventSource("/events");\n'
                'history.pushState({}, "", "/next");'
            )
            report = inspect(root, ["main.js"])["assets"][0]
            rows = report["request_candidates"]
            self.assertEqual([row["transport"] for row in rows], ["xhr", "beacon", "websocket", "sse"])
            self.assertEqual([row["method"] for row in rows], ["PATCH", "POST", None, None])
            self.assertEqual(rows[0]["path"], "/api/profile")
            self.assertNotIn("secret", json.dumps(report))
            self.assertIn({"signal": "pushState", "line": 6}, report["signal_locations"])

    def test_form_and_iframe_inventory_redacts_urls(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "index.html").write_text(
                '<form method="post" action="https://api.example.invalid/save?token=secret">'
                '<input required></form><iframe src="/embed?id=123456"></iframe>'
            )
            report = inspect(root, ["index.html"])["assets"][0]
            self.assertEqual(report["forms"][0]["method"], "POST")
            self.assertEqual(report["forms"][0]["path"], "/save")
            self.assertEqual(report["resource_references"][0]["path"], "/embed")
            self.assertNotIn("secret", json.dumps(report))

    def test_static_reverse_map_candidates_have_locators(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "main.js").write_text(
                'const routes = [{path: "/admin"}];\n'
                'const lazy = import("./chunks/admin.js");\n'
                'navigator.serviceWorker.register("/sw.js");\n'
                'localStorage.getItem("role"); indexedDB.open("app-cache");\n'
                'const q = `mutation SaveProfile { saveProfile { id } }`;\n'
                '//# sourceMappingURL=main.js.map'
            )
            report = inspect(root, ["main.js"])["assets"][0]
            self.assertEqual(report["route_candidates"][0]["path"], "/admin")
            self.assertEqual(
                [row["kind"] for row in report["resource_candidates"]],
                ["dynamic-import", "service-worker", "source-map"],
            )
            self.assertEqual([row["store"] for row in report["storage_candidates"]], ["localStorage", "indexedDB"])
            self.assertEqual(report["graphql_candidates"][0]["name"], "SaveProfile")
            self.assertTrue(all("line" in row for key in ("route_candidates", "resource_candidates", "storage_candidates") for row in report[key]))

    def test_local_discovery_is_bounded_and_supported_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "index.html").write_text("<html></html>")
            (root / "main.js").write_text("void 0")
            (root / "notes.txt").write_text("ignored")
            self.assertEqual(discover_assets(root), ["index.html", "main.js"])
            with self.assertRaises(ValueError):
                discover_assets(root, max_assets=1)

    def test_static_imports_and_missing_local_references_support_coverage_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "index.html").write_text('<script src="./main.js"></script>')
            (root / "main.js").write_text('import "./present.js"; export { value } from "./missing.js";')
            (root / "present.js").write_text("export const value = 1")
            result = inspect(root, ["index.html", "main.js", "present.js"])
            rows = result["assets"][1]["resource_candidates"]
            self.assertEqual([row["kind"] for row in rows], ["static-import", "static-import"])
            self.assertEqual(result["schema_version"], 2)
            self.assertEqual(result["reference_coverage"]["local_reference_edges"], 3)
            self.assertEqual(result["reference_coverage"]["available_reference_edges"], 2)
            self.assertEqual(result["reference_coverage"]["unique_local_resources"], 3)
            self.assertEqual(result["reference_coverage"]["available_unique_resources"], 2)
            self.assertEqual(result["reference_coverage"]["missing"], [
                {"from": "main.js", "path": "./missing.js", "kind": "static-import"}
            ])

    def test_site_origin_base_and_duplicate_edges_have_distinct_coverage_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "app").mkdir()
            hashed_name = "main.0123456789abcdef01234567.js"
            (root / "app" / hashed_name).write_text("void 0")
            (root / "shared.js").write_text("void 0")
            (root / "index.html").write_text(
                f'<base href="/app/"><script src="{hashed_name}"></script>'
                f'<script src="{hashed_name}"></script>'
                '<script src="https://target.example.invalid/shared.js"></script>'
            )
            result = inspect(
                root,
                ["index.html", f"app/{hashed_name}", "shared.js"],
                site_origin="https://target.example.invalid",
            )
            coverage = result["reference_coverage"]
            self.assertEqual(coverage["local_reference_edges"], 3)
            self.assertEqual(coverage["available_reference_edges"], 3)
            self.assertEqual(coverage["unique_local_resources"], 2)
            self.assertEqual(coverage["available_unique_resources"], 2)
            self.assertEqual(coverage["unresolved"], [])
            self.assertEqual(result["assets"][0]["resource_references"][0]["origin_label"], "target-origin")
            self.assertEqual(result["assets"][0]["resource_references"][2]["origin_label"], "target-origin")
            self.assertIn("[REDACTED-ID]", result["assets"][0]["resource_references"][0]["path"])

    def test_absolute_reference_without_site_origin_stays_unresolved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "index.html").write_text('<script src="https://target.example.invalid/main.js"></script>')
            result = inspect(root, ["index.html"])
            coverage = result["reference_coverage"]
            self.assertEqual(coverage["local_reference_edges"], 0)
            self.assertEqual(coverage["unresolved"][0]["reason"], "site-origin-unset")
            with self.assertRaises(ValueError):
                inspect(root, ["index.html"], site_origin="https://target.example.invalid/app")

    def test_inline_resource_content_is_not_exported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "index.html").write_text('<iframe src="data:text/html,private-secret"></iframe>')
            report = inspect(root, ["index.html"])["assets"][0]
            self.assertEqual(report["resource_references"][0]["path"], "[DATA-RESOURCE]")
            self.assertNotIn("private-secret", json.dumps(report))

    def test_uppercase_html_is_parsed_and_invalid_sourcemap_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'INDEX.HTML').write_text('<input required>')
            self.assertEqual(len(inspect(root, ['INDEX.HTML'])['assets'][0]['controls']), 1)
            (root / 'main.MAP').write_text('[]')
            with self.assertRaises(ValueError):
                inspect(root, ['main.MAP'])

    def test_escape_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                inspect(tmp, ["../private.js"])

    def test_video_bounds_rejected_before_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "video.mp4"
            source.write_bytes(b"synthetic")
            with self.assertRaises(ValueError):
                sample(source, Path(tmp) / "frames", duration=1000)
            with self.assertRaises(ValueError):
                sample(source, Path(tmp) / "frames", interval=float("nan"))

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "optional ffmpeg/ffprobe unavailable")
    def test_real_extraction_from_synthetic_video_is_unreviewed(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "synthetic.mp4"
            subprocess.run([shutil.which("ffmpeg"), "-nostdin", "-v", "error", "-f", "lavfi", "-i", "color=c=blue:s=64x64:r=2", "-t", "2", "-c:v", "mpeg4", str(source)], check=True, capture_output=True, timeout=30)
            result = sample(source, Path(tmp) / "frames", duration=2, interval=1)
            self.assertFalse(result["reviewed"])
            self.assertEqual(len(result['source_sha256']), 64)
            self.assertEqual(len(result['frame_timestamps']), len(result['frames']))
            self.assertTrue(all(t['precision']=='approximate' for t in result['frame_timestamps']))
            self.assertGreater(len(result["frames"]), 0)
            self.assertTrue((Path(tmp) / "frames" / result["frames"][0]).is_file())
            with self.assertRaises(ValueError):
                sample(source, Path(tmp) / "frames")


if __name__ == "__main__":
    unittest.main()
