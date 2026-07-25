from __future__ import annotations

import json
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

import yaml


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from workflow_engine import (  # noqa: E402
    HttpResponse,
    WorkflowConfigurationError,
    WorkflowRunner,
    WorkflowTransportError,
    UrllibTransport,
    _SameOriginRedirectHandler,
    _jsonpath,
    _redact,
)


class _FakeTransport:
    def __init__(
        self,
        *,
        fail_business_assertion: bool = False,
        omit_user_name: bool = False,
    ):
        self.fail_business_assertion = fail_business_assertion
        self.omit_user_name = omit_user_name
        self.requests: list[dict[str, object]] = []
        self.reset_count = 0

    def reset(self) -> None:
        self.reset_count += 1

    def request(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        query: dict[str, object],
        body: object,
        timeout: float,
    ) -> HttpResponse:
        self.requests.append(
            {
                "method": method,
                "url": url,
                "headers": dict(headers),
                "query": dict(query),
                "body": body,
                "timeout": timeout,
            }
        )
        if url.endswith("/login"):
            if body != {"username": "alice", "password": "password-secret"}:
                return HttpResponse(401, {}, {}, '{"error":"bad credentials"}')
            return HttpResponse(
                200,
                {"content-type": "application/json"},
                {"accessToken": "token-secret", "user": {"id": 7}},
                '{"accessToken":"token-secret","user":{"id":7}}',
            )
        if method == "GET" and url.endswith("/users/7"):
            if headers.get("Authorization") != "Bearer token-secret":
                return HttpResponse(401, {}, {}, '{"error":"unauthorized"}')
            if self.omit_user_name:
                return HttpResponse(200, {}, {"id": 7}, "")
            name = "Wrong" if self.fail_business_assertion else "Alice"
            return HttpResponse(200, {}, {"id": 7, "name": name}, "")
        if method == "DELETE" and url.endswith("/users/7"):
            if headers.get("Authorization") != "Bearer token-secret":
                return HttpResponse(401, {}, {}, '{"error":"unauthorized"}')
            return HttpResponse(204, {}, None, "")
        return HttpResponse(404, {}, {}, "")


class _FailingTransport(_FakeTransport):
    def request(self, **kwargs):
        if kwargs["method"] == "GET":
            self.requests.append(dict(kwargs))
            raise WorkflowTransportError("connection reset")
        return super().request(**kwargs)


class WorkflowRunnerTests(unittest.TestCase):
    def _write_documents(self, root: Path) -> Path:
        schema = {
            "openapi": "3.1.0",
            "info": {"title": "Workflow fixture", "version": "1"},
            "paths": {
                "/login": {
                    "post": {
                        "operationId": "login",
                        "responses": {"200": {"description": "ok"}},
                    }
                },
                "/users/{id}": {
                    "get": {
                        "operationId": "getUser",
                        "responses": {"200": {"description": "ok"}},
                    },
                    "delete": {
                        "operationId": "deleteUser",
                        "responses": {"204": {"description": "deleted"}},
                    },
                },
            },
        }
        (root / "openapi.yaml").write_text(
            yaml.safe_dump(schema, sort_keys=False),
            encoding="utf-8",
        )
        workflow = {
            "arazzo": "1.1.0",
            "info": {"title": "Authenticated user", "version": "1"},
            "sourceDescriptions": [
                {"name": "api", "url": "openapi.yaml", "type": "openapi"}
            ],
            "workflows": [
                {
                    "workflowId": "authenticatedUser",
                    "x-testkit-tags": ["smoke", "auth"],
                    "inputs": {
                        "type": "object",
                        "required": ["username", "password"],
                        "properties": {
                            "username": {"type": "string"},
                            "password": {"type": "string"},
                        },
                    },
                    "steps": [
                        {
                            "stepId": "login",
                            "operationId": "login",
                            "requestBody": {
                                "contentType": "application/json",
                                "payload": {
                                    "username": "$inputs.username",
                                    "password": "$inputs.password",
                                },
                            },
                            "successCriteria": [{"condition": "$statusCode == 200"}],
                            "outputs": {
                                "token": {
                                    "context": "$response.body",
                                    "selector": "/accessToken",
                                    "type": "jsonpointer",
                                },
                                "userId": "$response.body#/user/id",
                            },
                        },
                        {
                            "stepId": "getUser",
                            "operationId": "getUser",
                            "parameters": [
                                {
                                    "name": "id",
                                    "in": "path",
                                    "value": "$steps.login.outputs.userId",
                                },
                                {
                                    "name": "Authorization",
                                    "in": "header",
                                    "value": "Bearer {$steps.login.outputs.token}",
                                },
                            ],
                            "successCriteria": [
                                {"condition": "$statusCode == 200"},
                                {"condition": '$response.body#/name == "Alice"'},
                            ],
                        },
                    ],
                    "x-testkit-cleanup": [
                        {
                            "stepId": "deleteUser",
                            "operationId": "deleteUser",
                            "parameters": [
                                {
                                    "name": "id",
                                    "in": "path",
                                    "value": "$steps.login.outputs.userId",
                                },
                                {
                                    "name": "Authorization",
                                    "in": "header",
                                    "value": "Bearer {$steps.login.outputs.token}",
                                },
                            ],
                            "successCriteria": [{"condition": "$statusCode == 204"}],
                        }
                    ],
                }
            ],
        }
        workflow_path = root / "workflow.yaml"
        workflow_path.write_text(
            yaml.safe_dump(workflow, sort_keys=False),
            encoding="utf-8",
        )
        return workflow_path

    def _run(
        self,
        workflow: Path,
        transport: _FakeTransport,
        *,
        inputs: dict[str, object] | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, object]:
        runner = WorkflowRunner(
            workflow,
            base_url="https://api.example.invalid",
            transport=transport,
        )
        return runner.run(
            workflow_ids=["authenticatedUser"],
            tags=tags or [],
            inputs=inputs
            or {"username": "alice", "password": "password-secret"},
            secret_values=["password-secret", "token-secret"],
            allow_mutating_target=True,
        )

    def test_login_outputs_feed_later_steps_and_cleanup(self):
        with tempfile.TemporaryDirectory() as td:
            workflow = self._write_documents(Path(td))
            transport = _FakeTransport()
            result = self._run(workflow, transport)
            result_text = json.dumps(result, ensure_ascii=False)

        self.assertEqual(
            [(item["method"], item["url"]) for item in transport.requests],
            [
                ("POST", "https://api.example.invalid/login"),
                ("GET", "https://api.example.invalid/users/7"),
                ("DELETE", "https://api.example.invalid/users/7"),
            ],
        )
        self.assertEqual(result["status"], "passed")
        self.assertEqual(
            result["summary"],
            {"total": 1, "passed": 1, "failed": 0, "errors": 0},
        )
        self.assertEqual(result["runs"][0]["steps"][-1]["phase"], "cleanup")
        self.assertNotIn("password-secret", result_text)
        self.assertNotIn("token-secret", result_text)
        self.assertNotIn("accessToken", result_text)

    def test_cleanup_runs_after_a_business_assertion_failure(self):
        with tempfile.TemporaryDirectory() as td:
            workflow = self._write_documents(Path(td))
            transport = _FakeTransport(fail_business_assertion=True)
            result = self._run(workflow, transport)

        self.assertEqual(result["status"], "failed")
        self.assertEqual(
            result["summary"],
            {"total": 1, "passed": 0, "failed": 1, "errors": 0},
        )
        self.assertEqual(
            [item["method"] for item in transport.requests],
            ["POST", "GET", "DELETE"],
        )
        self.assertEqual(result["runs"][0]["steps"][-1]["status"], "passed")
        self.assertEqual(result["runs"][0]["steps"][-1]["phase"], "cleanup")

    def test_missing_response_field_becomes_failed_assertion_not_runner_error(self):
        with tempfile.TemporaryDirectory() as td:
            workflow = self._write_documents(Path(td))
            transport = _FakeTransport(omit_user_name=True)
            result = self._run(workflow, transport)

        self.assertEqual(result["status"], "failed")
        self.assertEqual(
            [item["method"] for item in transport.requests],
            ["POST", "GET", "DELETE"],
        )
        self.assertEqual(result["runs"][0]["steps"][1]["status"], "failed")
        self.assertIn("/name", result["runs"][0]["steps"][1]["error"])
        self.assertEqual(result["runs"][0]["steps"][-1]["phase"], "cleanup")
        self.assertEqual(result["runs"][0]["steps"][-1]["status"], "passed")

    def test_missing_extracted_output_becomes_failed_step_not_runner_error(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            workflow = self._write_documents(root)
            document = yaml.safe_load(workflow.read_text(encoding="utf-8"))
            document["workflows"][0]["steps"] = [document["workflows"][0]["steps"][0]]
            document["workflows"][0].pop("x-testkit-cleanup", None)
            workflow.write_text(
                yaml.safe_dump(document, sort_keys=False),
                encoding="utf-8",
            )
            transport = _FakeTransport()
            runner = WorkflowRunner(
                workflow,
                base_url="https://api.example.invalid",
                transport=transport,
            )
            result = runner.run(
                workflow_ids=["authenticatedUser"],
                inputs={"username": "alice", "password": "wrong-password"},
                secret_values=["wrong-password"],
                allow_mutating_target=True,
            )

        self.assertEqual(result["status"], "failed")
        self.assertEqual([item["method"] for item in transport.requests], ["POST"])
        self.assertEqual(result["runs"][0]["steps"][0]["status"], "failed")
        self.assertIn("accessToken", result["runs"][0]["steps"][0]["error"])

    def test_missing_input_fails_before_network_access(self):
        with tempfile.TemporaryDirectory() as td:
            workflow = self._write_documents(Path(td))
            transport = _FakeTransport()
            runner = WorkflowRunner(
                workflow,
                base_url="https://api.example.invalid",
                transport=transport,
            )
            with self.assertRaisesRegex(
                WorkflowConfigurationError,
                "password",
            ):
                runner.run(
                    workflow_ids=["authenticatedUser"],
                    inputs={"username": "alice"},
                    allow_mutating_target=True,
                )
            self.assertEqual(transport.requests, [])

    def test_every_dataset_row_is_validated_before_network_access(self):
        with tempfile.TemporaryDirectory() as td:
            workflow = self._write_documents(Path(td))
            transport = _FakeTransport()
            runner = WorkflowRunner(
                workflow,
                base_url="https://api.example.invalid",
                transport=transport,
            )
            with self.assertRaisesRegex(WorkflowConfigurationError, "password"):
                runner.run(
                    workflow_ids=["authenticatedUser"],
                    datasets=[
                        {"username": "alice", "password": "password-secret"},
                        {"username": "bob"},
                    ],
                    allow_mutating_target=True,
                )

        self.assertEqual(transport.requests, [])

    def test_each_dataset_row_gets_a_fresh_transport_session(self):
        with tempfile.TemporaryDirectory() as td:
            workflow = self._write_documents(Path(td))
            transport = _FakeTransport()
            runner = WorkflowRunner(
                workflow,
                base_url="https://api.example.invalid",
                transport=transport,
            )
            result = runner.run(
                workflow_ids=["authenticatedUser"],
                datasets=[
                    {"username": "alice", "password": "password-secret"},
                    {"username": "alice", "password": "password-secret"},
                ],
                secret_values=["password-secret", "token-secret"],
                allow_mutating_target=True,
            )

        self.assertEqual(result["summary"]["total"], 2)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(transport.reset_count, 2)

    def test_custom_transport_must_support_session_reset(self):
        class _NoResetTransport:
            def request(self, **kwargs):
                raise AssertionError("must not execute")

        with tempfile.TemporaryDirectory() as td:
            workflow = self._write_documents(Path(td))
            with self.assertRaisesRegex(
                WorkflowConfigurationError,
                r"must implement reset\(\)",
            ):
                WorkflowRunner(
                    workflow,
                    base_url="https://api.example.invalid",
                    transport=_NoResetTransport(),
                )

    def test_malformed_output_selector_is_rejected_before_network_access(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            workflow = self._write_documents(root)
            document = yaml.safe_load(workflow.read_text(encoding="utf-8"))
            document["workflows"][0]["steps"][0]["outputs"]["token"] = {
                "type": "jsonpointer",
                "context": "$response.body",
                "selector": "accessToken",
            }
            workflow.write_text(
                yaml.safe_dump(document, sort_keys=False),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                WorkflowConfigurationError,
                "invalid JSON Pointer",
            ):
                WorkflowRunner(
                    workflow,
                    base_url="https://api.example.invalid",
                    transport=_FakeTransport(),
                )

    def test_openapi_source_cannot_escape_the_workflow_directory(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            bundle = root / "bundle"
            bundle.mkdir()
            workflow = self._write_documents(bundle)
            external_schema = root / "external.yaml"
            external_schema.write_text(
                (bundle / "openapi.yaml").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            document = yaml.safe_load(workflow.read_text(encoding="utf-8"))
            document["sourceDescriptions"][0]["url"] = "../external.yaml"
            workflow.write_text(
                yaml.safe_dump(document, sort_keys=False),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                WorkflowConfigurationError,
                "must stay inside the workflow directory",
            ):
                WorkflowRunner(
                    workflow,
                    base_url="https://api.example.invalid",
                    transport=_FakeTransport(),
                )

    def test_querystring_preserves_repeated_keys(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            workflow = self._write_documents(root)
            schema_path = root / "openapi.yaml"
            schema = yaml.safe_load(schema_path.read_text(encoding="utf-8"))
            schema["paths"]["/search"] = {
                "get": {
                    "operationId": "search",
                    "responses": {"200": {"description": "ok"}},
                }
            }
            schema_path.write_text(
                yaml.safe_dump(schema, sort_keys=False),
                encoding="utf-8",
            )
            document = yaml.safe_load(workflow.read_text(encoding="utf-8"))
            document["workflows"] = [
                {
                    "workflowId": "search",
                    "steps": [
                        {
                            "stepId": "search",
                            "operationId": "search",
                            "parameters": [
                                {
                                    "name": "ids",
                                    "in": "query",
                                    "value": 0,
                                },
                                {
                                    "name": "ids",
                                    "in": "query",
                                    "value": [1, 2],
                                },
                                {
                                    "name": "query",
                                    "in": "querystring",
                                    "value": "ids=3&ids=4&tag=a",
                                }
                            ],
                        }
                    ],
                }
            ]
            workflow.write_text(
                yaml.safe_dump(document, sort_keys=False),
                encoding="utf-8",
            )
            transport = _FakeTransport()
            runner = WorkflowRunner(
                workflow,
                base_url="https://api.example.invalid",
                transport=transport,
            )
            runner.run(workflow_ids=["search"])

        self.assertEqual(
            transport.requests[0]["query"],
            {"ids": [0, 1, 2, "3", "4"], "tag": "a"},
        )

    def test_nested_workflow_step_records_its_elapsed_time(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            workflow = self._write_documents(root)
            document = yaml.safe_load(workflow.read_text(encoding="utf-8"))
            document["workflows"] = [
                {
                    "workflowId": "child",
                    "steps": [
                        {
                            "stepId": "pause",
                            "x-testkit-delay-ms": 20,
                        }
                    ],
                },
                {
                    "workflowId": "parent",
                    "steps": [
                        {
                            "stepId": "child",
                            "workflowId": "child",
                        }
                    ],
                },
            ]
            workflow.write_text(
                yaml.safe_dump(document, sort_keys=False),
                encoding="utf-8",
            )
            runner = WorkflowRunner(
                workflow,
                base_url="https://api.example.invalid",
                transport=_FakeTransport(),
            )
            result = runner.run(workflow_ids=["parent"])

        self.assertGreaterEqual(
            result["runs"][0]["steps"][0]["duration_ms"],
            15,
        )

    def test_tag_filter_selects_workflow(self):
        with tempfile.TemporaryDirectory() as td:
            workflow = self._write_documents(Path(td))
            result = self._run(
                workflow,
                _FakeTransport(),
                tags=["auth"],
            )
        self.assertEqual(result["summary"]["total"], 1)

    def test_post_workflow_cannot_self_bypass_mutating_confirmation(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            workflow = self._write_documents(root)
            document = yaml.safe_load(workflow.read_text(encoding="utf-8"))
            document["workflows"][0]["steps"] = [document["workflows"][0]["steps"][0]]
            document["workflows"][0].pop("x-testkit-cleanup", None)
            workflow.write_text(
                yaml.safe_dump(document, sort_keys=False),
                encoding="utf-8",
            )
            runner = WorkflowRunner(
                workflow,
                base_url="https://api.example.invalid",
                transport=_FakeTransport(),
            )
            with self.assertRaisesRegex(
                WorkflowConfigurationError,
                "mutating operations",
            ):
                runner.run(
                    workflow_ids=["authenticatedUser"],
                    inputs={"username": "alice", "password": "password-secret"},
                    secret_values=["password-secret", "token-secret"],
                )

        self.assertEqual(runner.transport.requests, [])

    def test_jsonpath_index_and_structural_redaction(self):
        payload = {"items": [{"token": 'a"b\\c'}]}
        self.assertEqual(_jsonpath(payload, "$.items[0].token"), 'a"b\\c')
        redacted = _redact(
            {"message": 'secret=a"b\\c', "nested": ['a"b\\c']},
            ['a"b\\c'],
        )
        self.assertEqual(
            redacted,
            {"message": "secret=[REDACTED]", "nested": ["[REDACTED]"]},
        )
        short_secret = _redact(
            {
                "status": "status",
                "steps": [],
                "message": "Authorization: t",
            },
            ["t"],
        )
        self.assertEqual(
            short_secret,
            {
                "status": "status",
                "steps": [],
                "message": "Authorization: [REDACTED]",
            },
        )
        reserved_value = _redact(
            {
                "status": "passed",
                "runs": [
                    {
                        "workflow_id": "passed",
                        "status": "passed",
                        "error": "passed",
                    }
                ],
            },
            ["passed"],
        )
        self.assertEqual(reserved_value["status"], "passed")
        self.assertEqual(reserved_value["runs"][0]["workflow_id"], "passed")
        self.assertEqual(reserved_value["runs"][0]["status"], "passed")
        self.assertEqual(reserved_value["runs"][0]["error"], "[REDACTED]")

    def test_transport_error_keeps_exit_classification_and_runs_cleanup(self):
        with tempfile.TemporaryDirectory() as td:
            workflow = self._write_documents(Path(td))
            transport = _FailingTransport()
            runner = WorkflowRunner(
                workflow,
                base_url="https://api.example.invalid",
                transport=transport,
            )
            result = runner.run(
                workflow_ids=["authenticatedUser"],
                inputs={"username": "alice", "password": "password-secret"},
                allow_mutating_target=True,
            )

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["runs"][0]["error_type"], "transport")
        failed_step = result["runs"][0]["steps"][1]
        self.assertEqual(failed_step["operation_id"], "getUser")
        self.assertEqual(failed_step["status"], "error")
        self.assertEqual(failed_step["error_type"], "transport")
        self.assertEqual(result["runs"][0]["steps"][-1]["phase"], "cleanup")
        self.assertEqual(
            [request["method"] for request in transport.requests],
            ["POST", "GET", "DELETE"],
        )

    def test_cross_origin_redirect_is_blocked_before_headers_can_be_forwarded(self):
        handler = _SameOriginRedirectHandler()
        request = urllib.request.Request(
            "https://api.example.invalid/me",
            headers={"Authorization": "Bearer token-secret"},
        )
        with self.assertRaisesRegex(urllib.error.URLError, "Cross-origin"):
            handler.redirect_request(
                request,
                None,
                302,
                "Found",
                {},
                "https://attacker.example/collect",
            )

    def test_default_transport_uses_an_identifiable_user_agent(self):
        class _Response:
            status = 200
            headers = {"Content-Type": "application/json"}

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return b"{}"

        class _Opener:
            request = None

            def open(self, request, *, timeout):
                self.request = request
                return _Response()

        transport = UrllibTransport()
        opener = _Opener()
        transport._opener = opener
        transport.request(
            method="GET",
            url="https://api.example.invalid/health",
            headers={},
            query={},
            body=None,
            timeout=1,
        )

        self.assertEqual(
            opener.request.get_header("User-agent"),
            "testkit-api-test-automation/1.0",
        )


if __name__ == "__main__":
    unittest.main()
