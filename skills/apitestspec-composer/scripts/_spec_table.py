"""Shared helpers for converting structured YAML/JSON specs to tabular rows."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

COLUMNS = [
    "用例ID", "用例名称", "接口路径", "路径参数", "请求方法", "请求体/参数",
    "预期状态码", "预期响应校验", "优先级", "前置依赖", "依赖产出提取", "注入方式",
    "是否运行", "运行结果",
]


def load_spec(path: Path) -> dict[str, Any]:
    if path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _serialize_validate(validates: list | None) -> tuple[str, str]:
    """Return (预期状态码, 预期响应校验) from structured validate list."""
    if not validates:
        return ("200", "")
    status = "200"
    parts: list[str] = []
    op_map = {"gt": ">", "gte": ">=", "lt": "<", "lte": "<=", "ne": "!="}
    for v in validates:
        if "eq" in v:
            fld, exp = v["eq"]
            if fld == "status_code":
                status = str(exp)
            else:
                parts.append(f"{fld}=={exp}")
        elif "contains" in v:
            fld, exp = v["contains"]
            parts.append(f"{fld} contains {exp}")
        elif "exists" in v:
            parts.append(str(v["exists"]))
        else:
            for op, sym in op_map.items():
                if op in v:
                    fld, exp = v[op]
                    parts.append(f"{fld}{sym}{exp}")
                    break
    return (status, " && ".join(parts))


def _serialize_extract(extract: dict | None) -> str:
    if not extract:
        return ""
    return " ; ".join(f"{k}={v}" for k, v in extract.items())


def step_to_row(case_id: str, case_name: str, step: dict, phase: str) -> dict[str, str]:
    use = step.get("use", "")
    req = step.get("request") or {}
    status_code, check_expr = _serialize_validate(step.get("validate"))
    return {
        "用例ID": case_id,
        "用例名称": f"{case_name} / {step.get('name', 'step')}",
        "接口路径": str(req.get("url", "")),
        "路径参数": "",
        "请求方法": str(req.get("method", "")) if req else "",
        "请求体/参数": json.dumps(req["json"], ensure_ascii=False) if req.get("json") else str(req.get("raw_body", "")),
        "预期状态码": status_code,
        "预期响应校验": check_expr,
        "优先级": "",
        "前置依赖": use,
        "依赖产出提取": _serialize_extract(step.get("extract")),
        "注入方式": phase,
        "是否运行": "是",
        "运行结果": "",
    }


def spec_to_rows(spec: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for case in spec.get("cases", []):
        cid = case.get("id", "")
        cname = case.get("name", "")
        for step in case.get("setup") or []:
            rows.append(step_to_row(cid, cname, step, "setup"))
        for step in case.get("steps") or []:
            rows.append(step_to_row(cid, cname, step, ""))
        for step in case.get("teardown") or []:
            rows.append(step_to_row(cid, cname, step, "teardown"))
    return rows
