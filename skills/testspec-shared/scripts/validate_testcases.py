#!/usr/bin/env python3
"""
testcases.json 自检工具 —— Agent 生成用例后自主调用，返回结构化 JSON 结果。

用途：
- 格式合规检查（必填字段、枚举值、编号格式）
- 步骤↔预期结果编号连续性
- 重复检测（标题+步骤相似度）
- 覆盖度报告（对照 testpoints.md 中的 TP_ID）
- 优先级/类型分布统计

返回 JSON 格式结果，Agent 据此决定是否自动修复。

用法:
    python validate_testcases.py --input testcases.json [--testpoints specs/testpoints.md]
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path


# ── 常量 ──────────────────────────────────────────────────────────

REQUIRED_FIELDS = {"id", "title", "steps", "expected_result", "priority"}
VALID_PRIORITIES = {"P1", "P2", "P3"}
VALID_TYPES = {"冒烟", "正向", "负向", "边界", "异常", "其他"}
ACTION_VERBS = [
    "点击", "输入", "选择", "等待", "查看", "校验",
    "打开", "提交", "确认", "删除", "修改", "搜索",
    "上传", "下载", "切换", "拖拽", "长按", "滑动",
]
MIN_FIELD_LEN = 10
SIMILARITY_THRESHOLD = 0.75


# ── 工具函数 ──────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    """去除空白和标点，用于相似度比较。"""
    return re.sub(r"[\s\d、.。，,；;：:！!？?（）()\[\]【】{}\"'""'']+", "", text)


def _simple_similarity(a: str, b: str) -> float:
    """基于字符级 Jaccard 的简单相似度。"""
    na, nb = _normalize(a), _normalize(b)
    if not na or not nb:
        return 0.0
    sa, sb = set(na), set(nb)
    intersection = len(sa & sb)
    union = len(sa | sb)
    return intersection / union if union else 0.0


def _count_numbered_items(text: str) -> int:
    """统计形如 '1、xxx' 或 '1. xxx' 的编号行数。"""
    if not text:
        return 0
    return len(re.findall(r"(?:^|\n)\s*\d+[、.]", text))


def _extract_tp_ids_from_md(md_text: str) -> set[str]:
    """从 testpoints.md 中提取所有 TP_ID。"""
    return set(re.findall(r"\bTP_[A-Z0-9_]+\b", md_text))


# ── 校验函数 ──────────────────────────────────────────────────────

def check_required_fields(cases: list[dict]) -> list[dict]:
    """检查必填字段是否存在且非空。"""
    issues = []
    for tc in cases:
        missing = []
        for field in REQUIRED_FIELDS:
            val = tc.get(field, "")
            if not val or (isinstance(val, str) and not val.strip()):
                missing.append(field)
        if missing:
            issues.append({
                "type": "MISSING_FIELD",
                "severity": "error",
                "case_id": tc.get("id", "UNKNOWN"),
                "title": tc.get("title", ""),
                "fields": missing,
                "fix_hint": f"补充以下字段: {', '.join(missing)}",
            })
    return issues


def check_field_quality(cases: list[dict]) -> list[dict]:
    """检查字段内容质量：长度、动作动词、模糊表述。"""
    issues = []
    vague_words = ["正常", "成功", "正确", "显示", "提示"]

    for tc in cases:
        case_id = tc.get("id", "UNKNOWN")
        title = tc.get("title", "")

        # 步骤长度
        steps = tc.get("steps", "")
        if steps and len(steps.strip()) < MIN_FIELD_LEN:
            issues.append({
                "type": "SHORT_STEPS",
                "severity": "warning",
                "case_id": case_id,
                "title": title,
                "value_len": len(steps.strip()),
                "fix_hint": "操作步骤过短，补充具体操作描述",
            })

        # 步骤中是否有动作动词
        if steps and not any(v in steps for v in ACTION_VERBS):
            issues.append({
                "type": "NO_ACTION_VERB",
                "severity": "warning",
                "case_id": case_id,
                "title": title,
                "fix_hint": "操作步骤中缺少动作动词（点击/输入/选择等）",
            })

        # 预期结果长度
        expected = tc.get("expected_result", "") or tc.get("expected", "")
        if expected and len(expected.strip()) < MIN_FIELD_LEN:
            issues.append({
                "type": "SHORT_EXPECTED",
                "severity": "warning",
                "case_id": case_id,
                "title": title,
                "value_len": len(expected.strip()),
                "fix_hint": "预期结果过短，补充具体验证标准",
            })

        # 模糊表述检测
        if expected:
            found_vague = [w for w in vague_words if w in expected]
            # 只在模糊词是预期结果的主体时报告（如"操作成功"整句只有模糊词）
            stripped = _normalize(expected)
            if found_vague and len(stripped) < 15:
                issues.append({
                    "type": "VAGUE_EXPECTED",
                    "severity": "warning",
                    "case_id": case_id,
                    "title": title,
                    "vague_words": found_vague,
                    "fix_hint": f"预期结果含模糊表述 {found_vague}，改为可验证的具体状态/数值/文案",
                })

    return issues


def check_enum_values(cases: list[dict]) -> list[dict]:
    """检查枚举字段值是否合法。"""
    issues = []
    for tc in cases:
        case_id = tc.get("id", "UNKNOWN")
        title = tc.get("title", "")

        priority = tc.get("priority", "")
        if priority and priority not in VALID_PRIORITIES:
            issues.append({
                "type": "INVALID_PRIORITY",
                "severity": "error",
                "case_id": case_id,
                "title": title,
                "value": priority,
                "valid_values": sorted(VALID_PRIORITIES),
                "fix_hint": f"优先级 '{priority}' 不合法，应为 P1/P2/P3",
            })

        tc_type = tc.get("type", "")
        if tc_type and tc_type not in VALID_TYPES:
            issues.append({
                "type": "INVALID_TYPE",
                "severity": "warning",
                "case_id": case_id,
                "title": title,
                "value": tc_type,
                "valid_values": sorted(VALID_TYPES),
                "fix_hint": f"用例类型 '{tc_type}' 不在标准列表中",
            })

    return issues


def check_naming_contract(cases: list[dict]) -> list[dict]:
    """检查用例标题是否符合三段式命名契约。"""
    issues = []
    for tc in cases:
        case_id = tc.get("id", "UNKNOWN")
        title = tc.get("title", "")
        feature = tc.get("feature", "")

        if not title:
            continue

        parts = title.split("_")
        if len(parts) < 3:
            issues.append({
                "type": "NAMING_FORMAT",
                "severity": "warning",
                "case_id": case_id,
                "title": title,
                "fix_hint": "标题应为 {模块}_{功能点}_{场景} 三段式",
            })
        elif feature and parts[0] != feature:
            issues.append({
                "type": "NAMING_FEATURE_MISMATCH",
                "severity": "warning",
                "case_id": case_id,
                "title": title,
                "feature": feature,
                "title_module": parts[0],
                "fix_hint": f"标题前缀 '{parts[0]}' 与 feature '{feature}' 不一致",
            })

    return issues


def check_step_expected_alignment(cases: list[dict]) -> list[dict]:
    """检查步骤和预期结果编号数量是否对齐。"""
    issues = []
    for tc in cases:
        case_id = tc.get("id", "UNKNOWN")
        steps = tc.get("steps", "")
        expected = tc.get("expected_result", "") or tc.get("expected", "")

        step_count = _count_numbered_items(steps)
        expected_count = _count_numbered_items(expected)

        # 只在两边都有编号且差异明显时报告
        if step_count > 0 and expected_count > 0 and abs(step_count - expected_count) > 2:
            issues.append({
                "type": "STEP_EXPECTED_MISMATCH",
                "severity": "warning",
                "case_id": case_id,
                "title": tc.get("title", ""),
                "step_count": step_count,
                "expected_count": expected_count,
                "fix_hint": f"步骤 {step_count} 条 vs 预期 {expected_count} 条，差异较大",
            })

    return issues


def check_duplicates(cases: list[dict]) -> list[dict]:
    """检测疑似重复用例（标题+步骤相似度）。"""
    issues = []
    n = len(cases)
    for i in range(n):
        for j in range(i + 1, n):
            title_sim = _simple_similarity(
                cases[i].get("title", ""), cases[j].get("title", "")
            )
            steps_sim = _simple_similarity(
                cases[i].get("steps", ""), cases[j].get("steps", "")
            )
            # 标题高度相似 且 步骤也相似
            if title_sim > 0.8 and steps_sim > SIMILARITY_THRESHOLD:
                issues.append({
                    "type": "DUPLICATE",
                    "severity": "warning",
                    "case_ids": [
                        cases[i].get("id", f"index-{i}"),
                        cases[j].get("id", f"index-{j}"),
                    ],
                    "titles": [
                        cases[i].get("title", ""),
                        cases[j].get("title", ""),
                    ],
                    "title_similarity": round(title_sim, 2),
                    "steps_similarity": round(steps_sim, 2),
                    "fix_hint": "疑似重复用例，考虑合并或区分测试场景",
                })
    return issues


def check_tp_coverage(cases: list[dict], tp_ids: set[str]) -> dict:
    """检查测试点覆盖度。"""
    if not tp_ids:
        return {
            "available": False,
            "reason": "未提供 testpoints.md 或未找到 TP_ID",
        }

    covered = set()
    for tc in cases:
        refs = tc.get("tp_refs", [])
        if isinstance(refs, list):
            covered.update(refs)

    uncovered = sorted(tp_ids - covered)
    coverage_rate = len(tp_ids - set(uncovered)) / len(tp_ids) if tp_ids else 0

    return {
        "available": True,
        "total_tp": len(tp_ids),
        "covered_tp": len(tp_ids) - len(uncovered),
        "coverage_rate": round(coverage_rate, 4),
        "uncovered": uncovered,
        "pass": coverage_rate >= 0.95,
    }


def compute_distribution(cases: list[dict]) -> dict:
    """计算优先级和类型分布。"""
    total = len(cases)
    priority_counter = Counter(tc.get("priority", "UNKNOWN") for tc in cases)
    type_counter = Counter(tc.get("type", "UNKNOWN") for tc in cases)
    smoke_count = sum(1 for tc in cases if tc.get("type") == "冒烟")

    distribution = {
        "total": total,
        "priority": {k: {"count": v, "ratio": round(v / total, 2) if total else 0}
                     for k, v in sorted(priority_counter.items())},
        "type": {k: {"count": v, "ratio": round(v / total, 2) if total else 0}
                 for k, v in sorted(type_counter.items())},
        "smoke": {
            "count": smoke_count,
            "ratio": round(smoke_count / total, 2) if total else 0,
            "all_p1": all(
                tc.get("priority") == "P1"
                for tc in cases
                if tc.get("type") == "冒烟"
            ),
        },
    }

    # 分布异常检测（只检测极端异常信号，不设固定比例目标）
    warnings = []
    p1_ratio = priority_counter.get("P1", 0) / total if total else 0
    p3_ratio = priority_counter.get("P3", 0) / total if total else 0
    distinct_priorities = len([k for k in priority_counter if k in VALID_PRIORITIES])
    if total > 5:  # 用例太少时不检查比例
        if distinct_priorities < 2:
            warnings.append(f"只有单一优先级 {list(priority_counter.keys())}，缺乏优先级区分")
        if p1_ratio > 0.80:
            warnings.append(f"P1 占比 {p1_ratio:.0%} 过高（>80%），可能缺乏优先级区分")
        if p3_ratio > 0.50:
            warnings.append(f"P3 占比 {p3_ratio:.0%} 过高（>50%），可能低估了核心功能的重要性")

    distribution["warnings"] = warnings
    return distribution


# ── 主流程 ──────────────────────────────────────────────────────

def validate(testcases_path: str, testpoints_path: str | None = None) -> dict:
    """执行全量校验，返回结构化 JSON 结果。"""

    # 加载 testcases.json
    tc_path = Path(testcases_path)
    if not tc_path.exists():
        return {"status": "ERROR", "message": f"文件不存在: {testcases_path}"}

    try:
        data = json.loads(tc_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return {"status": "ERROR", "message": f"JSON 解析失败: {e}"}

    cases = data.get("testcases", data if isinstance(data, list) else [])
    if not cases:
        return {"status": "ERROR", "message": "testcases 为空"}

    # 加载 testpoints（可选）
    tp_ids: set[str] = set()
    if testpoints_path:
        tp_path = Path(testpoints_path)
        if tp_path.exists():
            tp_ids = _extract_tp_ids_from_md(tp_path.read_text(encoding="utf-8"))

    # 执行所有检查
    errors = []
    warnings = []

    for issue in check_required_fields(cases):
        (errors if issue["severity"] == "error" else warnings).append(issue)

    for issue in check_enum_values(cases):
        (errors if issue["severity"] == "error" else warnings).append(issue)

    for issue in check_naming_contract(cases):
        warnings.append(issue)

    for issue in check_field_quality(cases):
        warnings.append(issue)

    for issue in check_step_expected_alignment(cases):
        warnings.append(issue)

    for issue in check_duplicates(cases):
        warnings.append(issue)

    # 覆盖度
    coverage = check_tp_coverage(cases, tp_ids)

    # 分布
    distribution = compute_distribution(cases)

    # 汇总
    status = "FAIL" if errors else ("WARN" if warnings else "PASS")

    return {
        "status": status,
        "summary": {
            "total_cases": len(cases),
            "error_count": len(errors),
            "warning_count": len(warnings),
        },
        "errors": errors,
        "warnings": warnings,
        "coverage": coverage,
        "distribution": distribution,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="TestSpec 用例自检工具")
    parser.add_argument("--input", required=True, help="testcases.json 路径")
    parser.add_argument("--testpoints", default=None, help="testpoints.md 路径（可选）")
    parser.add_argument("--pretty", action="store_true", help="格式化 JSON 输出")
    args = parser.parse_args()

    result = validate(args.input, args.testpoints)

    indent = 2 if args.pretty else None
    print(json.dumps(result, ensure_ascii=False, indent=indent))

    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
