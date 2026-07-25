from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import import_api  # noqa: E402
from source_adapters import SourceError, import_code_source, import_source  # noqa: E402


class CodeSourceAdapterTests(unittest.TestCase):
    def _write(self, root: Path, relative: str, content: str) -> Path:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_common_framework_routes_become_provenanced_openapi_skeleton(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write(
                root,
                "python/users.py",
                'router = APIRouter(prefix="/api")\n'
                '@app.get("/health")\n'
                "def health(): pass\n"
                '@router.get("/users/{id}")\n'
                "def get_user(): pass\n",
            )
            self._write(
                root,
                "java/HealthController.java",
                '@RequestMapping("/api")\n'
                "class HealthController {\n"
                '  @GetMapping("/health")\n'
                "  Object health() { return null; }\n"
                "}\n",
            )
            self._write(
                root,
                "node/orders.ts",
                '@Controller("api")\n'
                "export class OrdersController {\n"
                '  @Post("orders/:id")\n'
                "  create() {}\n"
                "}\n",
            )
            self._write(
                root,
                "go/main.go",
                'api := r.Group("/api")\n'
                'api.DELETE("/sessions/:id", deleteSession)\n',
            )
            imported = import_code_source(root)

        self.assertEqual(imported.kind, "source-code")
        self.assertEqual(imported.version, "static-scan-v1")
        self.assertEqual(imported.fidelity, "skeleton")
        self.assertEqual(set(imported.document["paths"]), {
            "/api/health",
            "/api/orders/{id}",
            "/api/sessions/{id}",
            "/api/users/{id}",
            "/health",
        })
        operation = imported.document["paths"]["/api/users/{id}"]["get"]
        self.assertEqual(operation["x-source-file"], "python/users.py")
        self.assertEqual(operation["x-source-framework"], "fastapi")
        self.assertEqual(operation["x-discovery-confidence"], "heuristic")
        self.assertEqual(operation["responses"], {
            "default": {
                "description": "Response contract was not inferred from source code."
            }
        })
        self.assertEqual(operation["parameters"][0]["name"], "id")
        self.assertFalse(
            any("spring ANY-method route" in item for item in imported.unsupported_features)
        )

    def test_any_routes_are_not_silently_mapped_to_get(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write(root, "app.py", '@app.route("/legacy")\ndef legacy(): pass\n')
            imported = import_code_source(root)

        self.assertEqual(imported.document["paths"], {})
        self.assertTrue(
            any("ANY-method route" in item for item in imported.unsupported_features)
        )

    def test_code_prefix_filters_and_tree_hash_is_stable(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = self._write(
                root,
                "app.py",
                '@app.get("/api/health")\ndef health(): pass\n'
                '@app.get("/apix/health")\ndef similar(): pass\n'
                '@app.get("/internal/health")\ndef internal(): pass\n',
            )
            first = import_code_source(root, url_prefix="/api")
            second = import_code_source(root, url_prefix="/api")
            self.assertEqual(first.source_sha256, second.source_sha256)
            self.assertEqual(set(first.document["paths"]), {"/api/health"})
            path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            changed = import_code_source(root, url_prefix="/api")
            self.assertNotEqual(first.source_sha256, changed.source_sha256)

    def test_code_scan_requires_explicit_flag_and_enforces_limits(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write(root, "app.py", '@app.get("/health")\ndef health(): pass\n')
            with self.assertRaisesRegex(SourceError, "Source file not found"):
                import_source(root)
            self._write(root, "other.py", '@app.get("/other")\ndef other(): pass\n')
            with self.assertRaisesRegex(SourceError, "supported source files"):
                import_code_source(root, max_files=1)

    def test_cli_import_writes_skeleton_and_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            code_root = root / "backend"
            code_root.mkdir()
            self._write(
                code_root,
                "app.py",
                '@app.get("/health")\ndef health(): pass\n',
            )
            output = root / "api-tests"
            exit_code = import_api.main(
                [
                    "import",
                    "--code-root",
                    str(code_root),
                    "--output-dir",
                    str(output),
                ]
            )
            manifest = json.loads(
                (output / "source-manifest.json").read_text(encoding="utf-8")
            )
            description = (output / "openapi.yaml").read_text(encoding="utf-8")

        self.assertEqual(exit_code, 0)
        self.assertEqual(manifest["kind"], "source-code")
        self.assertEqual(manifest["fidelity"], "skeleton")
        self.assertEqual(manifest["operation_count"], 1)
        self.assertIn("x-source-file: app.py", description)


if __name__ == "__main__":
    unittest.main()
