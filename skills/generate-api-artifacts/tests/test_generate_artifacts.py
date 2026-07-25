import json
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_ROOT / "scripts" / "generate_artifacts.py"
FIXTURE = SKILL_ROOT / "tests" / "fixtures" / "mini-openapi.yaml"


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        timeout=30,
    )


class TestGenerateArtifacts(unittest.TestCase):
    def test_inspect_reports_contract_gaps(self):
        result = run_cli("inspect", str(FIXTURE))
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads(result.stdout)
        self.assertEqual(summary["source_version"], "3.1.0")
        self.assertEqual(summary["operation_count"], 3)
        self.assertEqual(summary["missing_operation_ids"], ["GET /users/{id}"])

    def test_apifox_preserves_source_and_writes_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            result = run_cli(
                "generate",
                str(FIXTURE),
                "--target",
                "apifox",
                "--output-dir",
                td,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = json.loads((Path(td) / "artifact-manifest.json").read_text())
            [artifact] = manifest["generated"]
            output = Path(artifact["path"])
            self.assertEqual(output.read_bytes(), FIXTURE.read_bytes())
            self.assertEqual(artifact["target"], "apifox")
            self.assertTrue(manifest["manual_follow_ups"])

    def test_jmeter_is_property_driven_single_scenario_skeleton(self):
        with tempfile.TemporaryDirectory() as td:
            result = run_cli(
                "generate",
                str(FIXTURE),
                "--target",
                "jmeter",
                "--output-dir",
                td,
                "--threads",
                "10",
                "--ramp-seconds",
                "30",
                "--loops",
                "2",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            jmx_path = next(Path(td).glob("*.jmx"))
            root = ET.parse(jmx_path).getroot()
            self.assertEqual(len(root.findall(".//ThreadGroup")), 1)
            self.assertEqual(len(root.findall(".//HTTPSamplerProxy")), 3)
            self.assertEqual(len(root.findall(".//ResponseAssertion")), 3)
            self.assertEqual(len(root.findall(".//JSONPathAssertion")), 0)
            threads = root.find(
                ".//ThreadGroup/stringProp[@name='ThreadGroup.num_threads']"
            )
            ramp = root.find(".//ThreadGroup/stringProp[@name='ThreadGroup.ramp_time']")
            self.assertEqual(threads.text, "${__P(threads,10)}")
            self.assertEqual(ramp.text, "${__P(ramp_seconds,30)}")
            self.assertEqual(root.findall(".//ViewResultsTree"), [])
            manifest = json.loads((Path(td) / "artifact-manifest.json").read_text())
            self.assertIn("not a reviewed workload model", manifest["warnings"][0])

    def test_refuses_to_overwrite_outputs(self):
        with tempfile.TemporaryDirectory() as td:
            first = run_cli(
                "generate", str(FIXTURE), "--target", "apifox", "--output-dir", td
            )
            second = run_cli(
                "generate", str(FIXTURE), "--target", "apifox", "--output-dir", td
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 2)
            self.assertIn("use --force", second.stderr)

    def test_missing_postman_converter_is_configuration_error(self):
        with tempfile.TemporaryDirectory() as td:
            result = run_cli(
                "generate",
                str(FIXTURE),
                "--target",
                "postman",
                "--output-dir",
                td,
                "--postman-converter",
                "definitely-not-installed-openapi-converter",
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("Postman converter not found", result.stderr)

    def test_postman_uses_converter_and_validates_collection_v21(self):
        with tempfile.TemporaryDirectory() as td:
            converter = Path(td) / "fake-openapi2postmanv2"
            converter.write_text(
                f"""#!{sys.executable}
import json
import sys
output = sys.argv[sys.argv.index("-o") + 1]
with open(output, "w", encoding="utf-8") as handle:
    json.dump({{"info": {{"schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"}}, "item": []}}, handle)
"""
            )
            converter.chmod(0o755)
            output_dir = Path(td) / "out"
            result = run_cli(
                "generate",
                str(FIXTURE),
                "--target",
                "postman",
                "--output-dir",
                str(output_dir),
                "--postman-converter",
                str(converter),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            collection = next(output_dir.glob("*.postman_collection.json"))
            self.assertIn("collection/v2.1", collection.read_text())
            manifest = json.loads((output_dir / "artifact-manifest.json").read_text())
            self.assertEqual(manifest["generated"][0]["format"], "2.1")

    def test_jmeter_requires_a_concrete_server(self):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "no-server.json"
            source.write_text(
                json.dumps(
                    {
                        "openapi": "3.1.0",
                        "info": {"title": "No server", "version": "1"},
                        "paths": {
                            "/health": {
                                "get": {"responses": {"204": {"description": "ok"}}}
                            }
                        },
                    }
                )
            )
            result = run_cli(
                "generate",
                str(source),
                "--target",
                "jmeter",
                "--output-dir",
                str(Path(td) / "out"),
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("requires a concrete credential-free", result.stderr)


if __name__ == "__main__":
    unittest.main()
