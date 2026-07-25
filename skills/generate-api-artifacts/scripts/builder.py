#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JMX XML 构建器
构建 Apache JMeter 测试计划的 XML 结构
"""

import xml.etree.ElementTree as ET
from datetime import datetime
from xml.dom import minidom
from typing import Any, Dict, List, Optional, Tuple


class AssertionTestType:
    """JMeter 断言测试类型常量（注意: Asserion 是 JMeter 自身的历史拼写错误）"""
    CONTAINS = "1"
    EQUALS = "2"
    MATCHES = "8"
    NOT = "16"


class JmxBuilder:
    """JMX XML 构建器"""
    
    def __init__(self):
        self.root: Optional[ET.Element] = None
        self.test_plan: Optional[ET.Element] = None
        self.hash_tree: Optional[ET.Element] = None

    def _set_prop(self, parent: ET.Element, tag: str, name: str, text: str) -> ET.Element:
        """创建子元素并设置文本值。"""
        elem = ET.SubElement(parent, tag, name=name)
        elem.text = text
        return elem

    def create_test_plan(self, test_plan_name: str = "Test Plan", 
                        user_defined_variables: Optional[Dict[str, str]] = None) -> ET.Element:
        """
        创建测试计划
        
        Args:
            test_plan_name: 测试计划名称
            user_defined_variables: 用户定义变量
        
        Returns:
            测试计划元素
        """
        # 创建根元素
        self.root = ET.Element("jmeterTestPlan", version="1.2", properties="5.0", jmeter="5.6")
        
        # 创建 hashTree
        hash_tree = ET.SubElement(self.root, "hashTree")
        
        # 创建测试计划
        self.test_plan = ET.SubElement(hash_tree, "TestPlan", guiclass="TestPlanGui", 
                                       testclass="TestPlan", testname=test_plan_name, enabled="true")
        
        # 测试计划属性
        self._set_prop(self.test_plan, "boolProp", "TestPlan.functional_mode", "false")
        self._set_prop(self.test_plan, "boolProp", "TestPlan.serialize_threadgroups", "false")
        
        element_prop = ET.SubElement(self.test_plan, "elementProp", name="TestPlan.arguments", 
                                    elementType="Arguments", guiclass="ArgumentsPanel", 
                                    testclass="Arguments", testname="User Defined Variables", enabled="true")
        
        collection_prop = ET.SubElement(element_prop, "collectionProp", name="Arguments.arguments")
        
        # 添加用户定义变量
        if user_defined_variables:
            for key, value in user_defined_variables.items():
                element_prop_var = ET.SubElement(collection_prop, "elementProp",
                                                 name=key, elementType="Argument")
                self._set_prop(element_prop_var, "stringProp", "Argument.name", key)
                self._set_prop(element_prop_var, "stringProp", "Argument.value", str(value))
                self._set_prop(element_prop_var, "stringProp", "Argument.metadata", "=")

        self._set_prop(self.test_plan, "stringProp", "TestPlan.user_define_classpath", "")
        
        # 创建测试计划的 hashTree（用于存放线程组等子元素）
        test_plan_hash_tree = ET.SubElement(hash_tree, "hashTree")
        self.hash_tree = test_plan_hash_tree
        
        return self.test_plan
    
    def add_thread_group(self, name: str, num_threads: int | str = 1,
                        ramp_time: int | str = 1, loops: int | str = 1,
                        scheduler: bool = False) -> Tuple[ET.Element, ET.Element]:
        """
        添加线程组
        
        Args:
            name: 线程组名称
            num_threads: 线程数
            ramp_time: 启动时间（秒）
            loops: 循环次数（-1 表示永远）
            scheduler: 是否启用调度器
        
        Returns:
            线程组元素
        """
        if self.hash_tree is None:
            raise ValueError("请先创建测试计划")
        
        thread_group = ET.SubElement(self.hash_tree, "ThreadGroup", 
                                    guiclass="ThreadGroupGui", testclass="ThreadGroup", 
                                    testname=name, enabled="true")
        
        string_prop = ET.SubElement(thread_group, "stringProp", name="ThreadGroup.on_sample_error")
        string_prop.text = "continue"

        element_prop = ET.SubElement(thread_group, "elementProp", name="ThreadGroup.main_controller",
                                    elementType="LoopController", guiclass="LoopControllerGui",
                                    testclass="LoopController", testname="Loop Controller", enabled="true")

        self._set_prop(element_prop, "boolProp", "LoopController.continue_forever", "false")
        self._set_prop(element_prop, "stringProp", "LoopController.loops", str(loops))
        self._set_prop(thread_group, "stringProp", "ThreadGroup.num_threads", str(num_threads))
        self._set_prop(thread_group, "stringProp", "ThreadGroup.ramp_time", str(ramp_time))
        self._set_prop(thread_group, "boolProp", "ThreadGroup.scheduler", str(scheduler).lower())
        self._set_prop(thread_group, "stringProp", "ThreadGroup.duration", "")
        self._set_prop(thread_group, "stringProp", "ThreadGroup.delay", "")
        
        # 创建线程组的 hashTree
        thread_group_hash_tree = ET.SubElement(self.hash_tree, "hashTree")
        
        return thread_group, thread_group_hash_tree
    
    def add_http_request(self, parent_hash_tree: ET.Element, name: str, domain: str,
                        path: str, method: str = "GET", port: int | str = 80,
                        protocol: str = "http",
                        parameters: Optional[List[Dict[str, Any]]] = None,
                        headers: Optional[Dict[str, str]] = None,
                        body: Optional[str] = None) -> Tuple[ET.Element, ET.Element]:
        """
        添加 HTTP 请求

        Args:
            parent_hash_tree: 父 hashTree 元素
            name: 请求名称
            domain: 域名
            path: 路径
            method: HTTP 方法
            port: 端口
            protocol: 协议（http/https）
            parameters: 查询参数列表
            headers: 请求头字典
            body: 请求体

        Returns:
            (HTTP 请求元素, 请求的 hashTree 元素)
        """
        http_sampler = ET.SubElement(parent_hash_tree, "HTTPSamplerProxy",
                                    guiclass="HttpTestSampleGui", testclass="HTTPSamplerProxy",
                                    testname=name, enabled="true")

        element_prop = ET.SubElement(http_sampler, "elementProp", name="HTTPsampler.Arguments",
                                    elementType="Arguments", guiclass="HTTPArgumentsPanel",
                                    testclass="Arguments", testname="User Defined Variables", enabled="true")

        collection_prop = ET.SubElement(element_prop, "collectionProp", name="Arguments.arguments")

        has_body = body and method.upper() in ['POST', 'PUT', 'PATCH']

        # 添加查询参数或拼接到 URL
        if parameters and not has_body:
            self._add_query_parameters(collection_prop, parameters)

        actual_path = path
        if parameters and has_body:
            actual_path = self._build_path_with_query(path, parameters)

        self._add_sampler_properties(http_sampler, domain, port, protocol, actual_path, method)

        # HTTPSamplerProxy 后面需要 hashTree
        http_sampler_hash_tree = ET.SubElement(parent_hash_tree, "hashTree")

        if headers:
            self._add_header_manager(http_sampler_hash_tree, headers)

        if has_body:
            self._add_request_body(http_sampler, body)

        return http_sampler, http_sampler_hash_tree

    def _add_query_parameters(self, collection_prop: ET.Element,
                              parameters: List[Dict[str, Any]]) -> None:
        """将查询参数添加到 Arguments 集合中。"""
        for param in parameters:
            if param.get('in') != 'query':
                continue
            param_name = param.get('name', '')
            if not param_name:
                continue

            default_value = param.get('default', '')
            if not default_value:
                default_value = self._generate_default_param_value(param)

            element_prop_arg = ET.SubElement(collection_prop, "elementProp",
                                            name=param_name, elementType="HTTPArgument")
            self._set_prop(element_prop_arg, "stringProp", "Argument.name", param_name)
            self._set_prop(element_prop_arg, "stringProp", "Argument.value", str(default_value))
            self._set_prop(element_prop_arg, "stringProp", "Argument.metadata", "=")
            self._set_prop(element_prop_arg, "boolProp", "HTTPArgument.always_encode", "false")
            self._set_prop(element_prop_arg, "boolProp", "HTTPArgument.use_equals", "true")

    def _build_path_with_query(self, path: str,
                               parameters: List[Dict[str, Any]]) -> str:
        """当有 raw body 时，将查询参数拼接到 URL path 上。"""
        query_parts = []
        for param in parameters:
            if param.get('in') != 'query':
                continue
            param_name = param.get('name', '')
            if not param_name:
                continue
            default_value = param.get('default', '')
            if not default_value:
                default_value = self._generate_default_param_value(param)
            query_parts.append(f"{param_name}={default_value}")
        if query_parts:
            return f"{path}?{'&'.join(query_parts)}"
        return path

    def _add_sampler_properties(self, http_sampler: ET.Element, domain: str,
                                port: int, protocol: str, path: str,
                                method: str) -> None:
        """添加 HTTPSamplerProxy 的标准属性。"""
        props = [
            ("stringProp", "HTTPSampler.domain", domain),
            ("stringProp", "HTTPSampler.port", str(port)),
            ("stringProp", "HTTPSampler.protocol", protocol),
            ("stringProp", "HTTPSampler.contentEncoding", ""),
            ("stringProp", "HTTPSampler.path", path),
            ("stringProp", "HTTPSampler.method", method),
            ("boolProp", "HTTPSampler.follow_redirects", "true"),
            ("boolProp", "HTTPSampler.auto_redirects", "false"),
            ("boolProp", "HTTPSampler.use_keepalive", "true"),
            ("boolProp", "HTTPSampler.DO_MULTIPART_POST", "false"),
            ("stringProp", "HTTPSampler.embedded_url_re", ""),
            ("stringProp", "HTTPSampler.connect_timeout", ""),
            ("stringProp", "HTTPSampler.response_timeout", ""),
        ]
        for tag, prop_name, value in props:
            elem = ET.SubElement(http_sampler, tag, name=prop_name)
            elem.text = value

    def _add_header_manager(self, hash_tree: ET.Element,
                            headers: Dict[str, str]) -> None:
        """在 hashTree 中添加请求头管理器。"""
        header_manager = ET.SubElement(hash_tree, "HeaderManager",
                                      guiclass="HeaderPanel", testclass="HeaderManager",
                                      testname="HTTP Header Manager", enabled="true")
        collection_prop = ET.SubElement(header_manager, "collectionProp", name="HeaderManager.headers")
        for key, value in headers.items():
            element_prop = ET.SubElement(collection_prop, "elementProp", name="",
                                        elementType="Header")
            self._set_prop(element_prop, "stringProp", "Header.name", key)
            self._set_prop(element_prop, "stringProp", "Header.value", value)
        ET.SubElement(hash_tree, "hashTree")

    def _add_request_body(self, http_sampler: ET.Element, body: str) -> None:
        """添加 raw 请求体到 HTTP 请求中。"""
        self._set_prop(http_sampler, "boolProp", "HTTPSampler.postBodyRaw", "true")
        element_prop = http_sampler.find(".//elementProp[@name='HTTPsampler.Arguments']")
        if element_prop is None:
            return
        collection_prop = element_prop.find(".//collectionProp[@name='Arguments.arguments']")
        if collection_prop is None:
            return
        element_prop_arg = ET.SubElement(collection_prop, "elementProp",
                                        name="", elementType="HTTPArgument")
        self._set_prop(element_prop_arg, "boolProp", "HTTPArgument.always_encode", "false")
        self._set_prop(element_prop_arg, "boolProp", "HTTPArgument.use_equals", "true")
        self._set_prop(element_prop_arg, "stringProp", "Argument.value", body)
        self._set_prop(element_prop_arg, "stringProp", "Argument.metadata", "=")
    
    def add_response_assertion(self, parent_hash_tree: ET.Element, name: str,
                             field_to_test: str = "Assertion.response_code",
                             test_type: str = AssertionTestType.EQUALS,
                             pattern: str = "200") -> ET.Element:
        """
        添加响应断言
        
        Args:
            parent_hash_tree: 父 hashTree 元素
            name: 断言名称
            field_to_test: 测试字段（响应代码、响应消息、响应头、响应体等）
            test_type: 测试类型（2=等于，1=包含，8=匹配，16=不匹配）
            pattern: 匹配模式
        
        Returns:
            响应断言元素
        """
        assertion = ET.SubElement(parent_hash_tree, "ResponseAssertion", 
                                  guiclass="AssertionGui", testclass="ResponseAssertion", 
                                  testname=name, enabled="true")
        
        # 注意: "Asserion" 是 JMeter 自身的历史拼写错误，不要修正
        collection_prop = ET.SubElement(assertion, "collectionProp", name="Asserion.test_strings")
        # "49586" 是 JMeter 内部 "200".hashCode() 的值
        self._set_prop(collection_prop, "stringProp", "49586", pattern)
        self._set_prop(assertion, "stringProp", "Assertion.custom_message", "")
        self._set_prop(assertion, "stringProp", "Assertion.test_field", field_to_test)
        self._set_prop(assertion, "boolProp", "Assertion.assume_success", "false")
        self._set_prop(assertion, "intProp", "Assertion.test_type", test_type)
        
        # ResponseAssertion 后面需要 hashTree
        ET.SubElement(parent_hash_tree, "hashTree")
        
        return assertion
    
    def add_json_path_assertion(self, parent_hash_tree: ET.Element, name: str, 
                               json_path: str, expected_value: Optional[str] = None) -> ET.Element:
        """
        添加 JSON 路径断言
        
        Args:
            parent_hash_tree: 父 hashTree 元素
            name: 断言名称
            json_path: JSON 路径表达式
            expected_value: 期望值（可选）
        
        Returns:
            JSON 路径断言元素
        """
        assertion = ET.SubElement(parent_hash_tree, "JSONPathAssertion", 
                                 guiclass="JSONPathAssertionGui", testclass="JSONPathAssertion", 
                                 testname=name, enabled="true")
        
        self._set_prop(assertion, "stringProp", "JSON_PATH", json_path)
        self._set_prop(assertion, "stringProp", "EXPECTED_VALUE", expected_value or "")
        self._set_prop(assertion, "boolProp", "JSONVALIDATION", "true")
        self._set_prop(assertion, "boolProp", "EXPECT_NULL", "false")
        self._set_prop(assertion, "boolProp", "INVERT", "false")
        self._set_prop(assertion, "boolProp", "ISREGEX", "false")

        # JSONPathAssertion 后面需要 hashTree
        ET.SubElement(parent_hash_tree, "hashTree")

        return assertion
    
    def add_listener(self, parent_hash_tree: ET.Element, listener_type: str = "ViewResultsTree") -> ET.Element:
        """
        添加监听器
        
        Args:
            parent_hash_tree: 父 hashTree 元素
            listener_type: 监听器类型（ViewResultsTree, SummaryReport, GraphResults 等）
        
        Returns:
            监听器元素
        """
        listeners = {
            "ViewResultsTree": ("ViewResultsFullVisualizer", "ViewResultsFullVisualizer"),
            "SummaryReport": ("SummaryReport", "SummaryReport"),
            "GraphResults": ("GraphVisualizer", "GraphVisualizer"),
            "AggregateReport": ("StatVisualizer", "StatVisualizer")
        }
        
        if listener_type not in listeners:
            listener_type = "ViewResultsTree"
        
        guiclass, testclass = listeners[listener_type]
        listener = ET.SubElement(parent_hash_tree, testclass, 
                                guiclass=guiclass, testclass=testclass, 
                                testname=listener_type, enabled="true")
        
        # 监听器需要一些子元素才能正确反序列化
        # 所有 ResultCollector 类型的监听器都需要这些属性
        self._set_prop(listener, "boolProp", "ResultCollector.error_logging", "false")

        obj_prop = ET.SubElement(listener, "objProp")
        obj_prop.set("name", "filename")

        self._set_prop(listener, "stringProp", "filename", "")
        
        # Listener 后面需要 hashTree
        ET.SubElement(parent_hash_tree, "hashTree")
        
        return listener
    
    def _generate_default_param_value(self, param: Dict[str, Any]) -> str:
        """
        根据参数类型和是否必填生成合理的默认值

        Args:
            param: 参数字典，包含 name, type, required 等信息

        Returns:
            默认值字符串
        """
        param_name = param.get('name', '').lower()
        param_type = param.get('type', 'string').lower()
        required = param.get('required', False)

        # 根据参数名推断默认值（优先匹配）
        name_defaults = {
            ('page', 'num'): "1",
            ('page', 'size'): "10",
        }
        for keys, value in name_defaults.items():
            if all(k in param_name for k in keys):
                return value
        if 'year' in param_name:
            return str(datetime.now().year)
        if 'month' in param_name:
            return str(datetime.now().month)

        # 如果参数不是必填的，可以留空
        if not required:
            return ""

        # 必填参数的名称默认值
        if 'id' in param_name:
            return "1"
        if 'name' in param_name or 'url' in param_name:
            return ""

        # 类型默认值映射
        type_map = {'int': "1", 'integer': "1", 'string': "", 'bool': "true", 'boolean': "true"}
        for type_key, default_value in type_map.items():
            if type_key in param_type:
                return default_value

        return ""
    
    def add_csv_data_set_config(self, parent_hash_tree: ET.Element, name: str, 
                               filename: str, variable_names: str, 
                               delimiter: str = ",", ignore_first_line: bool = False) -> ET.Element:
        """
        添加 CSV 数据集配置
        
        Args:
            parent_hash_tree: 父 hashTree 元素
            name: 配置名称
            filename: CSV 文件路径
            variable_names: 变量名（逗号分隔）
            delimiter: 分隔符
            ignore_first_line: 是否忽略第一行
        
        Returns:
            CSV 数据集配置元素
        """
        csv_config = ET.SubElement(parent_hash_tree, "CSVDataSet", 
                                   guiclass="TestBeanGUI", testclass="CSVDataSet", 
                                   testname=name, enabled="true")
        
        self._set_prop(csv_config, "stringProp", "delimiter", delimiter)
        self._set_prop(csv_config, "stringProp", "fileEncoding", "UTF-8")
        self._set_prop(csv_config, "stringProp", "filename", filename)
        self._set_prop(csv_config, "boolProp", "ignoreFirstLine", str(ignore_first_line).lower())
        self._set_prop(csv_config, "boolProp", "quotedData", "false")
        self._set_prop(csv_config, "boolProp", "recycle", "true")
        self._set_prop(csv_config, "stringProp", "shareMode", "shareMode.all")
        self._set_prop(csv_config, "boolProp", "stopThread", "false")
        self._set_prop(csv_config, "stringProp", "variableNames", variable_names)

        # CSVDataSet 后面需要 hashTree
        ET.SubElement(parent_hash_tree, "hashTree")

        return csv_config
    
    def to_xml_string(self, pretty: bool = True) -> str:
        """
        转换为 XML 字符串
        
        Args:
            pretty: 是否格式化输出
        
        Returns:
            XML 字符串
        """
        if not self.root:
            raise ValueError("请先创建测试计划")
        
        if pretty:
            rough_string = ET.tostring(self.root, encoding='utf-8')
            reparsed = minidom.parseString(rough_string)
            return reparsed.toprettyxml(indent="  ", encoding='utf-8').decode('utf-8')
        else:
            return ET.tostring(self.root, encoding='utf-8').decode('utf-8')
    
    def save(self, file_path: str, pretty: bool = True) -> None:
        """
        保存为 JMX 文件
        
        Args:
            file_path: 文件路径
            pretty: 是否格式化输出
        """
        xml_string = self.to_xml_string(pretty)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(xml_string)
