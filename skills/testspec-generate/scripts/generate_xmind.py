#!/usr/bin/env python3
"""
TestSpec XMind 用例生成脚本：根据 testcases.json 生成 .xmind 测试用例思维导图。

实现参考项目内 xmind_generator.py，输出 XMind 8 格式（content.xml + manifest/styles/meta），
支持前置条件/测试步骤/预期结果子节点及优先级与类型标记，兼容 XMind 桌面版打开。

用法：
    python generate_xmind.py --input testcases.json --output artifacts/cases.xmind --title "测试用例"
"""
import argparse
import json
import logging
import os
import sys
import time
import uuid
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from typing import Any, Dict, List, Optional

try:
    from utils import configure_logging, load_and_validate_testcases
except ImportError:
    from .utils import configure_logging, load_and_validate_testcases

logger = logging.getLogger(__name__)

NS = "urn:xmind:xmap:xmlns:content:2.0"

# 优先级 -> XMind marker（与 xmind_generator 一致）
PRIORITY_MARKERS = {"P1": "priority-1", "P2": "priority-2", "P3": "priority-3"}

# 测试类型 -> XMind flag marker（冒烟/正向/负向/边界/异常 对应）
TYPE_MARKERS = {
    "冒烟": "flag-green",
    "正向": "flag-blue",
    "负向": "flag-red",
    "边界": "flag-yellow",
    "异常": "flag-red",
    "其他": "flag-blue",
}


def _topic_id() -> str:
    return uuid.uuid4().hex


def _generate_markers(tc_type: str, priority: str) -> List[str]:
    """根据测试类型与优先级生成 marker 列表（与 xmind_generator._generate_markers 一致）。"""
    markers = []
    if tc_type and tc_type in TYPE_MARKERS:
        markers.append(TYPE_MARKERS[tc_type])
    if priority and priority in PRIORITY_MARKERS:
        markers.append(PRIORITY_MARKERS[priority])
    return markers


def _build_case_node(tc: Dict[str, Any], tc_type: str) -> Dict[str, Any]:
    """构建单个测试用例节点，包含 fields 和 markers。"""
    name = tc.get("title") or tc.get("name", "")
    preconditions = tc.get("preconditions", "")
    steps = tc.get("steps", "")
    expected = tc.get("expected_result", tc.get("expected", ""))
    priority = tc.get("priority", "")
    node: Dict[str, Any] = {"title": name, "children": []}
    if preconditions or steps or expected:
        node["fields"] = {
            "preconditions": preconditions,
            "test_steps": steps,
            "expected_result": expected,
            "priority": priority,
        }
    markers = _generate_markers(tc_type, priority)
    if markers:
        node["markers"] = markers
    return node


def build_xmind_structure(test_cases: list, root_title: str) -> List[Dict[str, Any]]:
    """
    将 testcases.json 的扁平用例列表组织为 XMind 层级结构。
    每个叶子用例节点可带 fields（前置条件、测试步骤、预期结果）和 markers（优先级、类型）。
    """
    by_feature = defaultdict(lambda: defaultdict(list))
    for tc in test_cases:
        feature = tc.get("feature", "未分类")
        tc_type = tc.get("type", "其他")
        by_feature[feature][tc_type].append(tc)

    type_order = ["冒烟", "正向", "负向", "边界", "异常", "其他"]
    root_children = []
    for feature in sorted(by_feature.keys()):
        feat_node = {"title": f"{feature} - 测试用例", "children": []}
        for tc_type in type_order:
            cases = by_feature[feature].get(tc_type)
            if not cases:
                continue
            type_node = {"title": f"{tc_type}用例", "children": []}
            for tc in cases:
                type_node["children"].append(_build_case_node(tc, tc_type))
            feat_node["children"].append(type_node)
        for tc_type, cases in by_feature[feature].items():
            if tc_type not in type_order:
                type_node = {"title": f"{tc_type}用例", "children": []}
                for tc in cases:
                    type_node["children"].append(_build_case_node(tc, tc_type))
                feat_node["children"].append(type_node)
        root_children.append(feat_node)
    grouping_node = {"title": root_title, "children": root_children}
    return [{"title": root_title, "children": [grouping_node]}]


def _create_topic_xml(
    parent: ET.Element,
    title: str,
    *,
    children: Optional[List[Dict]] = None,
    note: Optional[str] = None,
    fields: Optional[Dict[str, str]] = None,
    markers: Optional[List[str]] = None,
) -> ET.Element:
    """
    创建主题节点（XMind 8 XML），与 xmind_generator._create_topic_xml 逻辑一致。
    支持备注、字段（前置条件→测试步骤→预期结果 嵌套子节点）、标记。
    """
    topic = ET.SubElement(parent, f"{{{NS}}}topic")
    topic.set("id", _topic_id())
    title_elem = ET.SubElement(topic, f"{{{NS}}}title")
    title_elem.text = title or ""

    if markers:
        marker_refs = ET.SubElement(topic, f"{{{NS}}}marker-refs")
        for marker_id in markers:
            marker_ref = ET.SubElement(marker_refs, f"{{{NS}}}marker-ref")
            marker_ref.set("marker-id", marker_id)

    if note:
        notes = ET.SubElement(topic, f"{{{NS}}}notes")
        plain = ET.SubElement(notes, f"{{{NS}}}plain")
        plain.text = note

    if fields:
        if not children:
            children = []
        priority = fields.get("priority", "P1")
        expected_val = fields.get("expected_result", "")
        steps_val = fields.get("test_steps", "")
        precond_val = fields.get("preconditions", "")

        current_node = None
        if expected_val:
            current_node = {
                "title": f"期望结果：{expected_val}",
                "children": [],
            }
        if steps_val:
            current_node = {
                "title": f"{priority}操作步骤：{steps_val}",
                "children": [current_node] if current_node else [],
            }
        if precond_val:
            current_node = {
                "title": f"预置条件：{precond_val}",
                "children": [current_node] if current_node else [],
            }
        if current_node:
            children = [current_node] + list(children)

    if children:
        children_elem = ET.SubElement(topic, f"{{{NS}}}children")
        topics_elem = ET.SubElement(children_elem, f"{{{NS}}}topics")
        topics_elem.set("type", "attached")
        for child in children:
            if isinstance(child, dict) and "title" in child:
                _create_topic_xml(
                    topics_elem,
                    child.get("title", ""),
                    children=child.get("children"),
                    note=child.get("note"),
                    fields=child.get("fields"),
                    markers=child.get("markers"),
                )
            else:
                _create_topic_xml(topics_elem, str(child) if child else "")

    return topic


def _prettify_xml(elem: ET.Element) -> str:
    """与 xmind_generator._prettify_xml 一致：生成 XML 字符串并在根元素添加 xmlns。"""
    rough = ET.tostring(elem, encoding="utf-8", xml_declaration=True)
    xml_str = rough.decode("utf-8")
    if "xmlns=" not in xml_str:
        xml_str = xml_str.replace(
            "<xmap-content",
            '<xmap-content xmlns="urn:xmind:xmap:xmlns:content:2.0"',
            1,
        )
    return xml_str


def _create_content_xml(structure: List[Dict], root_title: str, sheet_title: str) -> bytes:
    """生成 XMind 8 content.xml（与 xmind_generator.generate_xmind 中 XML 结构一致）。"""
    ET.register_namespace("", NS)
    xmap_content = ET.Element(f"{{{NS}}}xmap-content")
    xmap_content.set("version", "2.0")

    sheet = ET.SubElement(xmap_content, f"{{{NS}}}sheet")
    sheet.set("id", _topic_id())
    sheet.set("theme", "plain")
    sheet_title_el = ET.SubElement(sheet, f"{{{NS}}}title")
    sheet_title_el.text = sheet_title

    root_topic = ET.SubElement(sheet, f"{{{NS}}}topic")
    root_topic.set("id", _topic_id())
    root_title_el = ET.SubElement(root_topic, f"{{{NS}}}title")
    root_title_el.text = root_title

    root_node = structure[0] if structure else {"title": root_title, "children": []}
    root_children = root_node.get("children") or []
    if root_children:
        children_elem = ET.SubElement(root_topic, f"{{{NS}}}children")
        topics_elem = ET.SubElement(children_elem, f"{{{NS}}}topics")
        topics_elem.set("type", "attached")
        for item in root_children:
            _create_topic_xml(
                topics_elem,
                item.get("title", ""),
                children=item.get("children"),
                note=item.get("note"),
                fields=item.get("fields"),
                markers=item.get("markers"),
            )

    return _prettify_xml(xmap_content).encode("utf-8")


def _create_manifest() -> bytes:
    """与 xmind_generator._create_manifest 一致。"""
    return b"""<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<manifest xmlns="urn:xmind:xmap:xmlns:manifest:1.0">
    <file-entry full-path="content.xml" media-type="text/xml"/>
    <file-entry full-path="META-INF/" media-type=""/>
    <file-entry full-path="META-INF/manifest.xml" media-type="text/xml"/>
    <file-entry full-path="styles.xml" media-type="text/xml"/>
    <file-entry full-path="meta.xml" media-type="text/xml"/>
</manifest>"""


def _create_styles_xml() -> bytes:
    """与 xmind_generator._create_styles_xml 一致。"""
    return b"""<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<xmap-styles xmlns="urn:xmind:xmap:xmlns:style:2.0" version="2.0">
</xmap-styles>"""


def _create_meta_xml() -> bytes:
    """与 xmind_generator._create_meta_xml 一致。"""
    t = int(time.time() * 1000)
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<meta xmlns="urn:xmind:xmap:xmlns:meta:2.0" version="2.0">
    <Author>
        <Name>TestSpec</Name>
    </Author>
    <Create>{t}</Create>
    <Modified>{t}</Modified>
</meta>""".encode(
        "utf-8"
    )


def create_xmind_xmind8(
    structure: List[Dict],
    output_path: str,
    root_title: str,
    sheet_title: str = "测试用例",
) -> None:
    """生成 XMind 8 格式 .xmind（与 xmind_generator 输出结构一致）。"""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    content_bytes = _create_content_xml(structure, root_title, sheet_title)
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("META-INF/manifest.xml", _create_manifest())
        zf.writestr("content.xml", content_bytes)
        zf.writestr("styles.xml", _create_styles_xml())
        zf.writestr("meta.xml", _create_meta_xml())


def main() -> None:
    configure_logging()

    parser = argparse.ArgumentParser(description="Generate XMind test cases from JSON")
    parser.add_argument("--input", "-i", required=True, help="Path to testcases.json")
    parser.add_argument("--output", "-o", required=True, help="Output .xmind path")
    parser.add_argument("--title", "-t", default="测试用例", help="Root topic / sheet title")
    args = parser.parse_args()

    test_cases = load_and_validate_testcases(args.input)
    structure = build_xmind_structure(test_cases, args.title)
    create_xmind_xmind8(structure, args.output, args.title, sheet_title=args.title)
    print(f"已生成：{args.output}")


if __name__ == "__main__":
    main()
