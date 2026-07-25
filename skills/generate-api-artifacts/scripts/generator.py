#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JMX 测试脚本生成器
根据 API 文档生成 Apache JMeter 测试脚本
"""

import json
import logging
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

try:
    from .builder import AssertionTestType, JmxBuilder
    from .parsers import OpenApiParser
except ImportError:
    from builder import AssertionTestType, JmxBuilder
    from parsers import OpenApiParser

logger = logging.getLogger(__name__)


class JmxGenerator:
    """JMX 测试脚本生成器"""

    def __init__(self):
        self.builder = JmxBuilder()
        self.base_url = ""
        self.endpoints = []

    def generate_from_openapi(self, openapi_file: str,
                             test_plan_name: str = "API Test Plan",
                             num_threads: int = 1,
                             ramp_time: int = 1,
                             loops: int = 1,
                             base_url: str | None = None) -> str:
        """
        从 OpenAPI 文档生成 JMX 测试脚本

        Args:
            openapi_file: OpenAPI 文档路径
            test_plan_name: 测试计划名称
            num_threads: 线程数
            ramp_time: 启动时间（秒）
            loops: 循环次数

        Returns:
            JMX XML 字符串
        """
        parser = OpenApiParser()
        parser.parse(openapi_file)
        self.endpoints = parser.get_endpoints()
        self.base_url = base_url or parser.get_base_url()
        return self._generate_jmx(test_plan_name, num_threads, ramp_time, loops)

    def generate_from_endpoints(self, endpoints_data: dict,
                                test_plan_name: Optional[str] = None,
                                num_threads: Optional[int] = None,
                                ramp_time: Optional[int] = None,
                                loops: Optional[int] = None) -> str:
        """
        从 endpoints 数据字典生成 JMX 测试脚本

        Args:
            endpoints_data: 包含 endpoints、base_url 等信息的字典
            test_plan_name: 测试计划名称（覆盖 JSON 中的值）
            num_threads: 线程数（覆盖 JSON 中的值）
            ramp_time: 启动时间（覆盖 JSON 中的值）
            loops: 循环次数（覆盖 JSON 中的值）

        Returns:
            JMX XML 字符串
        """
        self.endpoints = endpoints_data.get('endpoints', [])
        self.base_url = endpoints_data.get('base_url', '')

        # CLI 参数优先于 JSON 中的值
        plan_name = test_plan_name or endpoints_data.get('test_plan_name', 'API Test Plan')
        threads = num_threads if num_threads is not None else endpoints_data.get('num_threads', 1)
        ramp = ramp_time if ramp_time is not None else endpoints_data.get('ramp_time', 1)
        loop_count = loops if loops is not None else endpoints_data.get('loops', 1)

        return self._generate_jmx(plan_name, threads, ramp, loop_count)

    def _generate_jmx(self, test_plan_name: str, num_threads: int,
                      ramp_time: int, loops: int) -> str:
        """生成一个可复核的 JMeter 场景骨架。"""
        url_parts = self._parse_url(self.base_url)

        self.builder = JmxBuilder()
        self.builder.create_test_plan(test_plan_name, {
            'protocol': url_parts.get('protocol', 'http'),
            'server': url_parts.get('domain', 'localhost'),
            'port': str(url_parts.get('port', 80)),
            'base_path': url_parts.get('base_path', ''),
        })
        _, scenario_tree = self.builder.add_thread_group(
            "API scenario",
            f"${{__P(threads,{num_threads})}}",
            f"${{__P(ramp_seconds,{ramp_time})}}",
            f"${{__P(loops,{loops})}}",
        )
        for endpoint in self.endpoints:
            self._add_endpoint(endpoint, scenario_tree)

        return self.builder.to_xml_string()

    def _add_endpoint(self, endpoint: Dict[str, Any],
                      scenario_tree: ET.Element) -> None:
        """把单个端点作为场景中的采样器加入。"""
        path = "${base_path}" + endpoint['path']
        method = endpoint['method']

        # 提取参数（区分 path、query、header 参数）
        path_params = [p for p in endpoint.get('parameters', []) if p.get('in') == 'path']
        query_params = [p for p in endpoint.get('parameters', []) if p.get('in') == 'query']
        header_params = [p for p in endpoint.get('parameters', []) if p.get('in') == 'header']

        # 替换路径参数
        for param in path_params:
            param_name = param.get('name', '')
            value = param.get('example', param.get('default'))
            replacement = str(value) if value not in (None, '') else f"${{{param_name}}}"
            path = path.replace(f"{{{param_name}}}", replacement)

        # 准备请求体
        request_body = None
        if endpoint.get('requestBody'):
            request_body = self._extract_request_body(endpoint['requestBody'])

        # 构建请求头
        headers: Dict[str, str] = {}
        for param in header_params:
            param_name = param.get('name', '')
            param_value = param.get('default', '')
            if param_name and param_value:
                normalized = param_name.lower()
                if normalized in {'authorization', 'cookie', 'x-api-key', 'api-key'}:
                    prop_name = normalized.replace('-', '_')
                    headers[param_name] = f"${{__P({prop_name},)}}"
                else:
                    headers[param_name] = param_value
        if request_body and method.upper() in ['POST', 'PUT', 'PATCH']:
            if 'Content-Type' not in headers:
                headers['Content-Type'] = 'application/json'

        # 添加 HTTP 请求（返回 http_sampler 和它的 hashTree）
        http_sampler, http_sampler_hash_tree = self.builder.add_http_request(
            scenario_tree,
            name=f"{method} {path}",
            domain="${server}",
            path=path,
            method=method,
            port="${port}",
            protocol="${protocol}",
            parameters=query_params,
            headers=headers or None,
            body=request_body
        )

        # 添加断言（放在 http_sampler 的 hashTree 中）
        self._add_assertions(http_sampler_hash_tree, endpoint)

    def _parse_url(self, url: str) -> Dict[str, Any]:
        """解析 URL"""
        if not url:
            return {'protocol': 'http', 'domain': 'localhost', 'port': 80, 'base_path': ''}

        # 移除末尾的斜杠
        url = url.rstrip('/')

        # 解析协议
        protocol = 'http'
        if url.startswith('https://'):
            protocol = 'https'
            url = url[8:]
        elif url.startswith('http://'):
            protocol = 'http'
            url = url[7:]

        # 解析域名和端口
        parts = url.split('/', 1)
        domain_part = parts[0]
        base_path = '/' + parts[1] if len(parts) > 1 else ''

        if ':' in domain_part:
            domain, port_str = domain_part.split(':', 1)
            try:
                port = int(port_str)
            except ValueError:
                port = 443 if protocol == 'https' else 80
        else:
            domain = domain_part
            port = 443 if protocol == 'https' else 80

        return {
            'protocol': protocol,
            'domain': domain,
            'port': port,
            'base_path': base_path
        }

    def _extract_request_body(self, request_body: Dict[str, Any]) -> Optional[str]:
        """提取请求体"""
        if not request_body:
            return None

        # OpenAPI 3.0 格式
        if 'content' in request_body:
            content = request_body['content']
            if 'application/json' in content:
                json_content = content['application/json']
                schema = json_content.get('schema', {})
                # 优先使用 example（可能在 schema 中，也可能在 content 中）
                example = json_content.get('example') or schema.get('example')
                if example:
                    return json.dumps(example, ensure_ascii=False)
                # 如果没有 example，尝试从 schema 生成
                return json.dumps(self._generate_example_from_schema(schema), ensure_ascii=False)

        return None

    def _generate_example_from_schema(self, schema: Dict[str, Any]) -> Any:
        """从 schema 生成示例数据"""
        schema_type = schema.get('type', 'object')

        if schema_type == 'object':
            example = {}
            properties = schema.get('properties', {})
            for prop_name, prop_schema in properties.items():
                example[prop_name] = self._generate_example_from_schema(prop_schema)
            return example
        elif schema_type == 'array':
            items = schema.get('items', {})
            return [self._generate_example_from_schema(items)]
        elif schema_type == 'string':
            return schema.get('example', 'string')
        elif schema_type == 'integer':
            return schema.get('example', 0)
        elif schema_type == 'number':
            return schema.get('example', 0.0)
        elif schema_type == 'boolean':
            return schema.get('example', True)
        else:
            return None

    def _add_assertions(self, parent_hash_tree: ET.Element, endpoint: Dict[str, Any]) -> None:
        """添加断言

        - 优先使用显式 assertions 数组（支持 status_code / json_path / response_contains）
        - 无 assertions 字段时走自动生成模式（向后兼容 OpenAPI/Markdown 流程）
        """
        explicit_assertions: Optional[List[Dict[str, Any]]] = endpoint.get('assertions')

        if explicit_assertions is not None:
            self._add_explicit_assertions(parent_hash_tree, explicit_assertions)
        else:
            self._add_documented_status_assertion(parent_hash_tree, endpoint)

    def _add_explicit_assertions(self, parent_hash_tree: ET.Element,
                                 assertions: List[Dict[str, Any]]) -> None:
        """根据显式 assertions 数组生成断言。"""
        for assertion in assertions:
            a_type = assertion.get('type', '')
            if a_type == 'status_code':
                self.builder.add_response_assertion(
                    parent_hash_tree,
                    name="Response Code Assertion",
                    field_to_test="Assertion.response_code",
                    test_type=AssertionTestType.EQUALS,
                    pattern=str(assertion.get('status_code', '200'))
                )
            elif a_type == 'json_path':
                json_path = assertion.get('json_path', '$')
                expected = assertion.get('expected_value')
                self.builder.add_json_path_assertion(
                    parent_hash_tree,
                    name=f"JSONPath Assertion - {json_path}",
                    json_path=json_path,
                    expected_value=str(expected) if expected is not None else None
                )
            elif a_type == 'response_contains':
                contains = assertion.get('contains', '')
                self.builder.add_response_assertion(
                    parent_hash_tree,
                    name=f"Response Contains - {contains}",
                    field_to_test="Assertion.response_data",
                    test_type=AssertionTestType.CONTAINS,
                    pattern=contains
                )

    def _add_documented_status_assertion(self, parent_hash_tree,
                                         endpoint: Dict[str, Any]) -> None:
        """仅为契约明确声明的单个成功状态码生成轻量断言。"""
        responses = endpoint.get('responses', {})
        success_codes = [
            str(code) for code in responses
            if str(code).isdigit() and 200 <= int(str(code)) < 300
        ]
        if len(success_codes) != 1:
            return
        self.builder.add_response_assertion(
            parent_hash_tree,
            name="Response Code Assertion",
            field_to_test="Assertion.response_code",
            test_type=AssertionTestType.EQUALS,
            pattern=success_codes[0]
        )

    def save_jmx(self, file_path: str, pretty: bool = True) -> None:
        """
        保存 JMX 文件

        Args:
            file_path: 文件路径
            pretty: 是否格式化输出
        """
        self.builder.save(file_path, pretty)
        logger.info("JMX 文件已保存: %s", file_path)
