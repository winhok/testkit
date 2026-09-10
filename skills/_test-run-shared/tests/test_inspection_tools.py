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
            self.assertGreater(len(result["frames"]), 0)
            self.assertTrue((Path(tmp) / "frames" / result["frames"][0]).is_file())
            with self.assertRaises(ValueError):
                sample(source, Path(tmp) / "frames")


if __name__ == "__main__":
    unittest.main()
