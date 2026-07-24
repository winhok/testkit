from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"


class CliSmokeTests(unittest.TestCase):
    def _run(self, args: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, *args],
            cwd=REPO_ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_import_api_inspect_cli_emits_summary_json(self):
        fixture = FIXTURES / "mini-openapi.yaml"
        completed = self._run(
            ["skills/test-api-contracts/scripts/import_api.py", "inspect", str(fixture)]
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["kind"], "openapi")
        self.assertEqual(payload["fidelity"], "lossless")
        self.assertEqual(payload["operation_count"], 1)

    def test_import_api_import_cli_writes_manifest_and_schema(self):
        fixture = FIXTURES / "mini-postman.json"
        with tempfile.TemporaryDirectory() as td:
            out_dir = Path(td) / "api-tests"
            completed = self._run(
                [
                    "skills/test-api-contracts/scripts/import_api.py",
                    "import",
                    str(fixture),
                    "--output-dir",
                    str(out_dir),
                ]
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            manifest = json.loads((out_dir / "source-manifest.json").read_text(encoding="utf-8"))
            schema = (out_dir / "openapi.yaml").read_text(encoding="utf-8")
        self.assertEqual(manifest["kind"], "postman")
        self.assertEqual(manifest["fidelity"], "high-with-losses")
        self.assertIn("openapi: 3.1.0", schema)

    def test_run_api_cli_executes_fake_schemathesis_and_writes_redacted_result(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            schema = root / "openapi.yaml"
            schema.write_text((FIXTURES / "mini-openapi.yaml").read_text(encoding="utf-8"), encoding="utf-8")
            output = root / "run-result.json"
            bin_dir = root / "bin"
            bin_dir.mkdir()
            fake = bin_dir / "schemathesis"
            fake.write_text(
                textwrap.dedent(
                    """\
                    #!/usr/bin/env python3
                    import sys
                    print("schemathesis ok")
                    print("Authorization: token-secret", file=sys.stderr)
                    raise SystemExit(1)
                    """
                ),
                encoding="utf-8",
            )
            fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
            env = {
                **os.environ,
                "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
                "API_TOKEN": "token-secret",
            }
            completed = self._run(
                [
                    "skills/test-api-contracts/scripts/run_api.py",
                    str(schema),
                    "--url",
                    "https://api.example.invalid",
                    "--header-env",
                    "Authorization=API_TOKEN",
                    "--output",
                    str(output),
                ],
                env=env,
            )
            self.assertEqual(completed.returncode, 1, completed.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(payload["status"], "failed")
        self.assertNotIn("token-secret", json.dumps(payload, ensure_ascii=False))
        self.assertIn("[REDACTED]", json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
