import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILLS / "web-runtime-analysis" / "scripts"))
sys.path.insert(0, str(SKILLS / "video-to-issue" / "scripts"))
from inspect_assets import inspect
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
