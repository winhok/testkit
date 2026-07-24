from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from source_adapters import (  # noqa: E402
    LoadedPayload,
    SourceError,
    _request_json,
    count_operations,
    import_source,
    import_yapi_project,
    operation_inventory,
)
import import_api  # noqa: E402


class SourceAdapterTests(unittest.TestCase):
    def _write_json(self, root: Path, name: str, value: object) -> Path:
        path = root / name
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return path

    def test_openapi_3_is_preserved_losslessly(self):
        source = {
            "openapi": "3.1.0",
            "info": {"title": "Demo", "version": "1"},
            "paths": {
                "/users": {
                    "get": {
                        "operationId": "listUsers",
                        "responses": {"200": {"description": "ok"}},
                    }
                }
            },
        }
        with tempfile.TemporaryDirectory() as td:
            path = self._write_json(Path(td), "openapi.json", source)
            imported = import_source(path)
        self.assertEqual(imported.kind, "openapi")
        self.assertEqual(imported.fidelity, "lossless")
        self.assertEqual(imported.document, source)
        self.assertEqual(count_operations(imported.document), 1)

    def test_openapi_31_webhooks_only_is_preserved_losslessly(self):
        source = {
            "openapi": "3.1.0",
            "info": {"title": "Webhook only", "version": "1"},
            "webhooks": {
                "newEvent": {
                    "post": {
                        "operationId": "receiveEvent",
                        "responses": {"200": {"description": "ok"}},
                    }
                }
            },
        }
        with tempfile.TemporaryDirectory() as td:
            path = self._write_json(Path(td), "openapi.json", source)
            imported = import_source(path)
        self.assertEqual(imported.fidelity, "lossless")
        self.assertEqual(count_operations(imported.document), 1)
        self.assertEqual(
            operation_inventory(imported.document),
            [
                {
                    "method": "POST",
                    "path": "webhooks:newEvent",
                    "operation_id": "receiveEvent",
                    "summary": "",
                    "tags": [],
                }
            ],
        )

    def test_swagger_2_is_preserved_losslessly(self):
        source = {
            "swagger": "2.0",
            "info": {"title": "Legacy", "version": "1"},
            "paths": {"/health": {"get": {"responses": {"200": {"description": "ok"}}}}},
        }
        with tempfile.TemporaryDirectory() as td:
            path = self._write_json(Path(td), "swagger.json", source)
            imported = import_source(path)
        self.assertEqual(imported.version, "2.0")
        self.assertEqual(imported.document, source)

    def test_openapi_32_is_accepted_but_similar_invalid_versions_are_rejected(self):
        valid = {
            "openapi": "3.2.0",
            "info": {"title": "Future", "version": "1"},
            "paths": {},
        }
        invalid = {**valid, "openapi": "3.20.0"}
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            valid_path = self._write_json(root, "valid.json", valid)
            invalid_path = self._write_json(root, "invalid.json", invalid)
            self.assertEqual(import_source(valid_path).version, "3.2.0")
            with self.assertRaisesRegex(SourceError, "Expected OpenAPI/Swagger"):
                import_source(invalid_path)

    def test_openapi_32_inventory_includes_query_additional_operations_and_webhooks(self):
        source = {
            "openapi": "3.2.0",
            "info": {"title": "Extended methods", "version": "1"},
            "paths": {
                "/search": {
                    "query": {"responses": {"200": {"description": "ok"}}},
                    "additionalOperations": {
                        "COPY": {"responses": {"200": {"description": "ok"}}}
                    },
                }
            },
            "webhooks": {
                "newEvent": {
                    "post": {"responses": {"200": {"description": "ok"}}}
                }
            },
        }
        with tempfile.TemporaryDirectory() as td:
            path = self._write_json(Path(td), "openapi.json", source)
            imported = import_source(path)
        self.assertEqual(count_operations(imported.document), 3)
        self.assertEqual(
            {(item["method"], item["path"]) for item in operation_inventory(imported.document)},
            {
                ("QUERY", "/search"),
                ("COPY", "/search"),
                ("POST", "webhooks:newEvent"),
            },
        )

    def test_yapi_export_maps_parameters_and_json_schema(self):
        source = [
            {
                "name": "用户",
                "list": [
                    {
                        "_id": 7,
                        "title": "获取用户",
                        "method": "GET",
                        "path": "/users/{id}",
                        "req_params": [{"name": "id", "desc": "用户 ID"}],
                        "req_query": [
                            {
                                "name": "verbose",
                                "required": "0",
                                "example": "true",
                                "type": "boolean",
                            }
                        ],
                        "res_body_is_json_schema": True,
                        "res_body": json.dumps(
                            {
                                "type": "object",
                                "properties": {"id": {"type": "integer"}},
                            }
                        ),
                    }
                ],
            }
        ]
        with tempfile.TemporaryDirectory() as td:
            path = self._write_json(Path(td), "yapi.json", source)
            imported = import_source(path)
        operation = imported.document["paths"]["/users/{id}"]["get"]
        self.assertEqual(imported.kind, "yapi")
        self.assertEqual(operation["tags"], ["用户"])
        self.assertEqual(
            [(p["name"], p["in"], p["required"]) for p in operation["parameters"]],
            [("id", "path", True), ("verbose", "query", False)],
        )
        self.assertEqual(operation["parameters"][1]["schema"]["type"], "boolean")
        self.assertIs(operation["parameters"][1]["example"], True)
        schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
        self.assertEqual(schema["properties"]["id"]["type"], "integer")

    def test_postman_21_recurses_folders_and_records_script_loss(self):
        source = {
            "info": {
                "name": "Orders",
                "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
            },
            "variable": [{"key": "baseUrl", "value": "https://api.example.invalid"}],
            "item": [
                {
                    "name": "Orders",
                    "item": [
                        {
                            "name": "Get order",
                            "event": [{"listen": "test", "script": {"exec": ["pm.test()"]}}],
                            "request": {
                                "method": "GET",
                                "url": {
                                    "raw": "{{baseUrl}}/orders/:id?expand=true",
                                    "path": ["orders", ":id"],
                                    "variable": [{"key": "id", "value": "1"}],
                                    "query": [{"key": "expand", "value": "true"}],
                                },
                                "header": [
                                    {"key": "Authorization", "value": "Bearer {{token}}"},
                                    {"key": "Accept", "value": "application/json"},
                                ],
                            },
                            "response": [{"name": "ok", "code": 200, "body": "{\"id\":1}"}],
                        }
                    ],
                }
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            path = self._write_json(Path(td), "postman.json", source)
            imported = import_source(path)
        operation = imported.document["paths"]["/orders/{id}"]["get"]
        self.assertEqual(imported.kind, "postman")
        self.assertEqual(imported.document["servers"], [{"url": "https://api.example.invalid"}])
        self.assertEqual(operation["tags"], ["Orders"])
        self.assertEqual(
            [(parameter["name"], parameter["in"]) for parameter in operation["parameters"]],
            [("id", "path"), ("expand", "query")],
        )
        self.assertIn("Postman pre-request/test scripts", imported.unsupported_features)
        self.assertIn("Postman Authorization headers", imported.unsupported_features)
        self.assertIn("Postman Accept headers", imported.unsupported_features)
        self.assertIn("Postman variable scopes", imported.unsupported_features)
        self.assertEqual(operation["responses"]["200"]["content"]["application/json"]["example"], {"id": 1})

    def test_postman_server_never_preserves_url_credentials(self):
        source = {
            "info": {
                "name": "Credential URL",
                "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
            },
            "item": [
                {
                    "name": "Health",
                    "request": {
                        "method": "GET",
                        "url": "https://user:secret@api.example.invalid/health",
                    },
                }
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            path = self._write_json(Path(td), "postman.json", source)
            imported = import_source(path)
        self.assertNotIn("servers", imported.document)
        self.assertNotIn("secret", json.dumps(imported.document))

    def test_postman_preserves_all_nested_folder_tags(self):
        source = {
            "info": {
                "name": "Nested",
                "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
            },
            "item": [
                {
                    "name": "Administration",
                    "item": [
                        {
                            "name": "Users",
                            "item": [
                                {
                                    "name": "Get user",
                                    "request": {
                                        "method": "GET",
                                        "url": {
                                            "path": ["users", ":userId"],
                                            "variable": [{"key": "userId", "value": "42"}],
                                        },
                                    },
                                }
                            ],
                        }
                    ],
                }
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            path = self._write_json(Path(td), "postman.json", source)
            imported = import_source(path)
        operation = imported.document["paths"]["/users/{userId}"]["get"]
        self.assertEqual(operation["tags"], ["Administration", "Users"])
        self.assertEqual(operation["parameters"][0]["name"], "userId")

    def test_postman_url_object_falls_back_to_raw_query_string(self):
        source = {
            "info": {
                "name": "Query fallback",
                "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
            },
            "item": [
                {
                    "name": "Get orders",
                    "request": {
                        "method": "GET",
                        "url": {
                            "raw": "https://api.example.invalid/orders?expand=true&limit=10"
                        },
                    },
                }
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            path = self._write_json(Path(td), "postman.json", source)
            imported = import_source(path)
        operation = imported.document["paths"]["/orders"]["get"]
        self.assertEqual(
            [(parameter["name"], parameter["in"]) for parameter in operation["parameters"]],
            [("expand", "query"), ("limit", "query")],
        )

    def test_source_manifest_redacts_query_credentials(self):
        loaded = LoadedPayload(
            {
                "openapi": "3.1.0",
                "info": {"title": "Protected", "version": "1"},
                "paths": {},
            },
            b"source",
            "https://api.example.invalid/openapi.json?api_key=top-secret&version=1",
        )
        with patch("source_adapters.load_payload", return_value=loaded):
            imported = import_source("https://api.example.invalid/openapi.json")
        self.assertNotIn("top-secret", imported.source)
        self.assertIn("api_key=%5BREDACTED%5D", imported.source)
        self.assertIn("version=1", imported.source)

    def test_yapi_open_api_uses_token_without_putting_it_in_provenance(self):
        listing = LoadedPayload(
            {"errcode": 0, "data": {"list": [{"_id": 11}]}},
            b"list",
            "https://yapi.example.invalid/api/interface/list",
        )
        detail = LoadedPayload(
            {
                "errcode": 0,
                "data": {
                    "_id": 11,
                    "title": "Health",
                    "method": "GET",
                    "path": "/health",
                },
            },
            b"detail",
            "https://yapi.example.invalid/api/interface/get",
        )
        with patch("source_adapters._request_json", side_effect=[listing, detail]) as request:
            imported = import_yapi_project(
                "https://yapi.example.invalid", 9, "top-secret"
            )
        called_urls = [call.args[0] for call in request.call_args_list]
        self.assertTrue(all("top-secret" in url for url in called_urls))
        self.assertNotIn("top-secret", json.dumps(imported.manifest()))
        self.assertEqual(imported.source, "https://yapi.example.invalid/project/9")

    def test_yapi_open_api_fetches_additional_pages(self):
        listing_page_1 = LoadedPayload(
            {"errcode": 0, "data": {"list": [{"_id": 11}], "total": 2}},
            b"list-1",
            "https://yapi.example.invalid/api/interface/list?page=1",
        )
        detail_1 = LoadedPayload(
            {
                "errcode": 0,
                "data": {"_id": 11, "title": "Health", "method": "GET", "path": "/health"},
            },
            b"detail-1",
            "https://yapi.example.invalid/api/interface/get?id=11",
        )
        listing_page_2 = LoadedPayload(
            {"errcode": 0, "data": {"list": [{"_id": 12}], "total": 2}},
            b"list-2",
            "https://yapi.example.invalid/api/interface/list?page=2",
        )
        detail_2 = LoadedPayload(
            {
                "errcode": 0,
                "data": {"_id": 12, "title": "Ready", "method": "GET", "path": "/ready"},
            },
            b"detail-2",
            "https://yapi.example.invalid/api/interface/get?id=12",
        )
        with patch(
            "source_adapters._request_json",
            side_effect=[listing_page_1, detail_1, listing_page_2, detail_2],
        ) as request:
            imported = import_yapi_project(
                "https://yapi.example.invalid", 9, "top-secret"
            )
        self.assertEqual(sorted(imported.document["paths"]), ["/health", "/ready"])
        list_urls = [
            call.args[0]
            for call in request.call_args_list
            if "/api/interface/list?" in call.args[0]
        ]
        self.assertEqual(len(list_urls), 2)
        self.assertIn("page=1", list_urls[0])
        self.assertIn("page=2", list_urls[1])

    def test_yapi_request_error_redacts_token(self):
        with patch(
            "source_adapters.urllib.request.urlopen",
            side_effect=OSError("connection refused"),
        ):
            with self.assertRaises(SourceError) as caught:
                _request_json(
                    "https://yapi.example.invalid/api/interface/list?"
                    "token=top-secret&page=1"
                )
        message = str(caught.exception)
        self.assertNotIn("top-secret", message)
        self.assertIn("token=%5BREDACTED%5D", message)

    def test_source_url_rejects_embedded_credentials_before_network_access(self):
        with patch("source_adapters.urllib.request.urlopen") as request:
            with self.assertRaisesRegex(SourceError, "credential-free"):
                import_source(
                    "https://user:plain-secret@api.example.invalid/openapi.json"
                )
        request.assert_not_called()

    def test_yapi_request_error_with_invalid_port_still_returns_source_error(self):
        with patch(
            "source_adapters.urllib.request.urlopen",
            side_effect=OSError("connection refused"),
        ):
            with self.assertRaises(SourceError) as caught:
                _request_json(
                    "https://yapi.example.invalid:bad/api/interface/list?"
                    "token=top-secret&page=1"
                )
        message = str(caught.exception)
        self.assertNotIn("top-secret", message)
        self.assertIn("/api/interface/list", message)

    def test_swagger_ui_url_discovers_raw_description(self):
        html_response = MagicMock()
        html_response.__enter__.return_value = html_response
        html_response.read.return_value = (
            b'<html><script>SwaggerUIBundle({url: "/openapi.json"})</script></html>'
        )
        html_response.headers.get.return_value = "text/html"
        html_response.geturl.return_value = "https://api.example.invalid/docs"
        description_response = MagicMock()
        description_response.__enter__.return_value = description_response
        description_response.read.return_value = json.dumps(
            {
                "openapi": "3.1.0",
                "info": {"title": "From UI", "version": "1"},
                "paths": {},
            }
        ).encode()
        description_response.headers.get.return_value = "application/json"
        description_response.geturl.return_value = (
            "https://api.example.invalid/openapi.json"
        )
        with patch(
            "source_adapters.urllib.request.urlopen",
            side_effect=[html_response, description_response],
        ) as request:
            imported = import_source("https://api.example.invalid/docs")
        self.assertEqual(imported.source, "https://api.example.invalid/openapi.json")
        self.assertEqual(
            [call.args[0].full_url for call in request.call_args_list],
            [
                "https://api.example.invalid/docs",
                "https://api.example.invalid/openapi.json",
            ],
        )

    def test_import_refuses_to_overwrite_existing_artifacts(self):
        source = {
            "openapi": "3.1.0",
            "info": {"title": "Demo", "version": "1"},
            "paths": {},
        }
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source_path = self._write_json(root, "openapi.json", source)
            output_dir = root / "output"
            output_dir.mkdir()
            description = output_dir / "openapi.yaml"
            description.write_text("keep-me\n", encoding="utf-8")
            code = import_api.main(
                ["import", str(source_path), "--output-dir", str(output_dir)]
            )
            preserved = description.read_text(encoding="utf-8")
        self.assertEqual(code, 2)
        self.assertEqual(preserved, "keep-me\n")

    def test_import_description_name_cannot_escape_output_directory(self):
        source = {
            "openapi": "3.1.0",
            "info": {"title": "Demo", "version": "1"},
            "paths": {},
        }
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source_path = self._write_json(root, "openapi.json", source)
            outside = root / "outside.yaml"
            code = import_api.main(
                [
                    "import",
                    str(source_path),
                    "--output-dir",
                    str(root / "output"),
                    "--description-name",
                    "../outside.yaml",
                ]
            )
        self.assertEqual(code, 2)
        self.assertFalse(outside.exists())

    def test_unknown_json_fails_with_actionable_message(self):
        with tempfile.TemporaryDirectory() as td:
            path = self._write_json(Path(td), "unknown.json", {"hello": "world"})
            with self.assertRaisesRegex(SourceError, "Expected OpenAPI/Swagger"):
                import_source(path)


if __name__ == "__main__":
    unittest.main()
