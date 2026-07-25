from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import csv
import yaml


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from legacy_case_adapter import LegacyMigrationError, migrate_legacy_project  # noqa: E402
from workflow_engine import HttpResponse, WorkflowRunner  # noqa: E402


class _MigrationTransport:
    def __init__(self) -> None:
        self.methods: list[str] = []

    def reset(self) -> None:
        pass

    def request(self, *, method, url, headers, query, body, timeout):
        self.methods.append(method)
        if url.endswith("/login"):
            return HttpResponse(
                200,
                {},
                {"accessToken": "token-secret", "user": {"id": 7}},
                "",
            )
        if method == "GET":
            self.assert_auth = headers.get("Authorization")
            return HttpResponse(200, {}, {"id": 7, "name": "Alice"}, "")
        return HttpResponse(204, {}, None, "")


class LegacyMigrationTests(unittest.TestCase):
    def _write_project(self, root: Path) -> tuple[Path, Path]:
        project = root / "project.yaml"
        project.write_text(
            """
project:
  name: users
  base_url: ${ENV.BASE_URL}
  vars:
    tenant: test-tenant
  defaults:
    headers:
      X-Tenant: ${project.tenant}
""",
            encoding="utf-8",
        )
        (root / "flows").mkdir()
        (root / "flows" / "auth.yaml").write_text(
            """
flows:
  auth:
    steps:
      - name: login
        request:
          method: POST
          url: /login
          json:
            username: ${ENV.TEST_USER}
            password: ${ENV.TEST_PASS}
        extract:
          token: $.accessToken
          user_id: $.user.id
        validate:
          - eq: [status_code, 200]
          - exists: $.accessToken
""",
            encoding="utf-8",
        )
        (root / "cases").mkdir()
        (root / "cases" / "users.yaml").write_text(
            """
cases:
  - id: user_lifecycle
    name: user lifecycle
    tags: [smoke, auth]
    setup:
      - name: settle
        sleep: 0
      - use: flow:auth
    steps:
      - name: get_user
        request:
          method: GET
          url: /users/${vars.user_id}
          headers:
            Authorization: Bearer ${vars.token}
        validate:
          - eq: [status_code, 200]
          - contains: [$.name, Ali]
          - exists: $.id
    teardown:
      - name: delete_user
        request:
          method: DELETE
          url: /users/${vars.user_id}
          headers:
            Authorization: Bearer ${vars.token}
        validate:
          - eq: [status_code, 204]
""",
            encoding="utf-8",
        )
        schema = root / "openapi.yaml"
        schema.write_text(
            yaml.safe_dump(
                {
                    "openapi": "3.1.0",
                    "info": {"title": "users", "version": "1"},
                    "paths": {
                        "/login": {"post": {"operationId": "login", "responses": {}}},
                        "/users/{id}": {
                            "get": {"operationId": "getUser", "responses": {}},
                            "delete": {"operationId": "deleteUser", "responses": {}},
                        },
                    },
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        return project, schema

    def test_migrates_flow_extraction_templates_assertions_and_cleanup(self):
        with tempfile.TemporaryDirectory() as td:
            project, schema = self._write_project(Path(td))
            output = Path(td) / "workflow.yaml"
            manifest = migrate_legacy_project(project, schema, output)
            document = yaml.safe_load(output.read_text(encoding="utf-8"))

        by_id = {item["workflowId"]: item for item in document["workflows"]}
        auth = by_id["auth"]
        lifecycle = by_id["user_lifecycle"]
        self.assertEqual(manifest["status"], "migrated")
        self.assertEqual(manifest["unsupported_features"], [])
        self.assertEqual(auth["steps"][0]["operationId"], "login")
        self.assertEqual(
            auth["steps"][0]["outputs"]["token"],
            {"type": "jsonpath", "context": "$response.body", "selector": "$.accessToken"},
        )
        self.assertEqual(lifecycle["x-testkit-setup"][0]["x-testkit-delay-ms"], 0)
        self.assertEqual(lifecycle["x-testkit-setup"][1]["workflowId"], "auth")
        self.assertEqual(
            lifecycle["steps"][0]["parameters"][0],
            {"name": "id", "in": "path", "value": "$outputs.user_id"},
        )
        self.assertIn(
            {"name": "X-Tenant", "in": "header", "value": "$inputs.project_tenant"},
            lifecycle["steps"][0]["parameters"],
        )
        self.assertEqual(lifecycle["x-testkit-cleanup"][0]["operationId"], "deleteUser")
        self.assertEqual(
            lifecycle["inputs"]["properties"]["project_tenant"]["default"],
            "test-tenant",
        )
        self.assertIn("TEST_PASS", lifecycle["inputs"]["required"])

    def test_unmappable_operation_fails_without_writing_partial_output(self):
        with tempfile.TemporaryDirectory() as td:
            project, schema = self._write_project(Path(td))
            case_path = Path(td) / "cases" / "users.yaml"
            raw = yaml.safe_load(case_path.read_text(encoding="utf-8"))
            raw["cases"][0]["steps"][0]["request"]["url"] = "/unknown"
            case_path.write_text(yaml.safe_dump(raw), encoding="utf-8")
            output = Path(td) / "workflow.yaml"

            with self.assertRaisesRegex(LegacyMigrationError, "/unknown"):
                migrate_legacy_project(project, schema, output)

            self.assertFalse(output.exists())

    def test_migrated_login_flow_executes_with_child_outputs_and_cleanup(self):
        with tempfile.TemporaryDirectory() as td:
            project, schema = self._write_project(Path(td))
            output = Path(td) / "workflow.yaml"
            migrate_legacy_project(project, schema, output)
            transport = _MigrationTransport()
            runner = WorkflowRunner(
                output,
                base_url="https://api.example.invalid",
                transport=transport,
            )
            result = runner.run(
                workflow_ids=["user_lifecycle"],
                inputs={"TEST_USER": "alice", "TEST_PASS": "password-secret"},
                secret_values=["password-secret"],
                allow_mutating_target=True,
            )

        self.assertEqual(result["status"], "passed")
        self.assertEqual(transport.methods, ["POST", "GET", "DELETE"])
        self.assertEqual(transport.assert_auth, "Bearer token-secret")

    def test_tabular_case_without_case_id_fails_instead_of_silent_drop(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            project = root / "project.yaml"
            project.write_text("project:\n  name: table\n", encoding="utf-8")
            (root / "cases").mkdir()
            with (root / "cases" / "table.csv").open(
                "w", encoding="utf-8", newline=""
            ) as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["用例ID", "用例名称", "请求方法", "接口路径", "预期状态码"],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "用例ID": "",
                        "用例名称": "missing id",
                        "请求方法": "GET",
                        "接口路径": "/users/1",
                        "预期状态码": "200",
                    }
                )
            schema = root / "openapi.yaml"
            schema.write_text(
                yaml.safe_dump(
                    {
                        "openapi": "3.1.0",
                        "info": {"title": "users", "version": "1"},
                        "paths": {
                            "/users/{id}": {
                                "get": {"operationId": "getUser", "responses": {}}
                            }
                        },
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
            output = root / "workflow.yaml"

            with self.assertRaisesRegex(LegacyMigrationError, "用例ID"):
                migrate_legacy_project(project, schema, output)

        self.assertFalse(output.exists())

    def test_report_directories_cannot_escape_the_legacy_project(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            bundle = root / "bundle"
            bundle.mkdir()
            project, schema = self._write_project(bundle)
            project.write_text(
                """
project:
  name: users
  report:
    cases_dir: ../outside
""",
                encoding="utf-8",
            )
            outside = root / "outside"
            outside.mkdir()
            (outside / "unrelated.yaml").write_text(
                "cases:\n  - id: unrelated\n    steps: []\n",
                encoding="utf-8",
            )
            output = bundle / "workflow.yaml"

            with self.assertRaisesRegex(
                LegacyMigrationError,
                "cases_dir must stay inside",
            ):
                migrate_legacy_project(project, schema, output)

        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
