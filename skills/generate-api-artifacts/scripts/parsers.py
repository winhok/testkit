#!/usr/bin/env python3
"""Load the OpenAPI/Swagger fields needed by artifact generators."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - exercised by environments without YAML support
    yaml = None


HTTP_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}


class OpenApiParser:
    """Parse OpenAPI 3.x or Swagger 2.0 without mutating the source document."""

    def __init__(self) -> None:
        self.spec: dict[str, Any] | None = None
        self.version: str | None = None

    def parse(self, file_path: str) -> dict[str, Any]:
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"文件不存在: {file_path}")
        text = path.read_text(encoding="utf-8-sig")
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            if yaml is None:
                raise ImportError("解析 YAML 需要安装 pyyaml") from None
            try:
                value = yaml.safe_load(text)
            except yaml.YAMLError as exc:
                raise ValueError(f"YAML 格式无效: {exc}") from exc
        return self._accept(value)

    def parse_from_string(self, content: str, input_format: str = "yaml") -> dict[str, Any]:
        if input_format.lower() == "json":
            value = json.loads(content)
        else:
            if yaml is None:
                raise ImportError("解析 YAML 需要安装 pyyaml")
            value = yaml.safe_load(content)
        return self._accept(value)

    def _accept(self, value: Any) -> dict[str, Any]:
        if not isinstance(value, dict) or not isinstance(value.get("paths"), dict):
            raise ValueError("OpenAPI/Swagger 文档必须包含 paths 对象")
        if value.get("swagger") == "2.0":
            self.version = "2.0"
        elif str(value.get("openapi", "")).startswith(("3.0.", "3.1.", "3.2.")):
            self.version = str(value["openapi"])
        else:
            raise ValueError("仅支持 Swagger 2.0 或 OpenAPI 3.0/3.1/3.2")
        self.spec = value
        return value

    def get_endpoints(self) -> list[dict[str, Any]]:
        if self.spec is None:
            raise ValueError("请先解析 OpenAPI 文档")
        endpoints: list[dict[str, Any]] = []
        for path, path_item in self.spec["paths"].items():
            if not isinstance(path_item, dict):
                continue
            inherited = path_item.get("parameters", [])
            for method, operation in path_item.items():
                if method.lower() not in HTTP_METHODS or not isinstance(operation, dict):
                    continue
                parameters = [*inherited, *operation.get("parameters", [])]
                request_body = operation.get("requestBody")
                if self.version == "2.0":
                    body = next(
                        (item for item in parameters if item.get("in") == "body"),
                        None,
                    )
                    if body:
                        request_body = {
                            "content": {
                                "application/json": {"schema": body.get("schema", {})}
                            }
                        }
                endpoints.append(
                    {
                        "path": path,
                        "method": method.upper(),
                        "operationId": operation.get("operationId", ""),
                        "summary": operation.get("summary", ""),
                        "description": operation.get("description", ""),
                        "parameters": parameters,
                        "requestBody": request_body,
                        "responses": operation.get("responses", {}),
                        "tags": operation.get("tags", []),
                    }
                )
        return endpoints

    def get_base_url(self) -> str:
        if self.spec is None:
            return ""
        if self.version == "2.0":
            schemes = self.spec.get("schemes") or ["http"]
            host = self.spec.get("host", "")
            return f"{schemes[0]}://{host}{self.spec.get('basePath', '')}" if host else ""
        servers = self.spec.get("servers") or []
        if servers and isinstance(servers[0], dict):
            return str(servers[0].get("url", ""))
        return ""
