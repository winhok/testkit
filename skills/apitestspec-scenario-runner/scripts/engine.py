"""Self-contained API test execution engine.

Models, HTTP client, template renderer, JSONPath extractor,
assertion engine, case executor, and result reporting.
"""
from __future__ import annotations

import json
import re
import time
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import requests

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class StepSpec:
    name: str | None = None
    use: str | None = None
    inputs: dict[str, Any] | None = None
    save_as: str | None = None
    request: dict[str, Any] | None = None
    extract: dict[str, str] | None = None
    validate: list[dict[str, Any]] | None = None
    sleep: int | float | None = None


@dataclass(slots=True)
class CaseSpec:
    id: str
    name: str
    tags: list[str] = field(default_factory=list)
    continue_on_failure: bool = False
    on_failure: str = "stop"
    setup: list[StepSpec] = field(default_factory=list)
    steps: list[StepSpec] = field(default_factory=list)
    teardown: list[StepSpec] = field(default_factory=list)


@dataclass(slots=True)
class FlowSpec:
    name: str
    steps: list[StepSpec] = field(default_factory=list)


@dataclass(slots=True)
class CaseDocument:
    cases: list[CaseSpec] = field(default_factory=list)
    flows: dict[str, FlowSpec] = field(default_factory=dict)
    source: str | None = None


@dataclass(slots=True)
class ProjectSpec:
    name: str
    base_url: str
    vars: dict[str, Any] = field(default_factory=dict)
    defaults: dict[str, Any] = field(default_factory=dict)
    report: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class _RuntimeContext:
    env: dict[str, str]
    project_vars: dict[str, Any]
    project_defaults: dict[str, Any] = field(default_factory=dict)
    runtime_vars: dict[str, Any] = field(default_factory=dict)
    step_outputs: dict[str, Any] = field(default_factory=dict)
    last_response: Any | None = None


@dataclass(slots=True)
class StepExecutionResult:
    phase: str
    name: str | None
    alias: str | None
    status: str
    request: dict[str, Any] = field(default_factory=dict)
    response: dict[str, Any] = field(default_factory=dict)
    extracted: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(slots=True)
class CaseExecutionResult:
    case_id: str
    case_name: str
    status: str
    failed_step: str | None = None
    reason: str | None = None
    steps: list[StepExecutionResult] = field(default_factory=list)

# ---------------------------------------------------------------------------
# HTTP client
# ---------------------------------------------------------------------------

class HttpClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

    def send(self, **req: Any) -> dict[str, Any]:
        resp = self.session.request(
            method=str(req["method"]).upper(),
            url=f"{self.base_url}{req['url']}",
            params=req.get("params"),
            json=req.get("json"),
            data=req.get("data"),
            headers=req.get("headers"),
            timeout=req.get("timeout", 30),
        )
        try:
            body = resp.json()
        except Exception:
            body = None
        return {"status_code": resp.status_code, "json": body, "headers": dict(resp.headers), "text": resp.text}

# ---------------------------------------------------------------------------
# Template renderer
# ---------------------------------------------------------------------------

_TPL = re.compile(r"\$\{([^}]+)\}")
_PFX = {"ENV.": 4, "vars.": 5, "project.": 8, "steps.": 6}


def _resolve_nested(value: Any, path: str) -> Any:
    cur = value
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part, "")
        else:
            return ""
    return cur


def _render(value: str, env: dict, project: dict, runtime: dict, steps: dict) -> str:
    resolvers = {
        "ENV.": lambda e: env.get(e[4:], ""),
        "vars.": lambda e: runtime.get(e[5:], ""),
        "project.": lambda e: project.get(e[8:], ""),
        "steps.": lambda e: _resolve_nested(steps, e[6:]),
    }
    def _repl(m: re.Match) -> str:
        expr = m.group(1)
        for pfx, fn in resolvers.items():
            if expr.startswith(pfx):
                return str(fn(expr))
        return ""
    return _TPL.sub(_repl, value)


def _render_value(v: Any, *, env: dict, project: dict, runtime: dict, steps: dict) -> Any:
    if isinstance(v, str):
        return _render(v, env, project, runtime, steps)
    if isinstance(v, dict):
        return {k: _render_value(i, env=env, project=project, runtime=runtime, steps=steps) for k, i in v.items()}
    if isinstance(v, list):
        return [_render_value(i, env=env, project=project, runtime=runtime, steps=steps) for i in v]
    return v

# ---------------------------------------------------------------------------
# JSONPath extractor
# ---------------------------------------------------------------------------

def extract_path(payload: dict[str, Any], expression: str) -> Any:
    if not expression.startswith("$."):
        return None
    cur: Any = payload
    for part in expression[2:].split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
        if cur is None:
            return None
    return cur

# ---------------------------------------------------------------------------
# Assertion engine
# ---------------------------------------------------------------------------

_NUM_OPS = {
    "gt": lambda a, e: a > e,
    "gte": lambda a, e: a >= e,
    "lt": lambda a, e: a < e,
    "lte": lambda a, e: a <= e,
}


def _get_actual(resp: dict, field: str) -> Any:
    if field == "status_code":
        return resp.get("status_code")
    if field.startswith("$."):
        return extract_path(resp.get("json") or {}, field)
    return resp.get(field)


def run_validations(resp: dict[str, Any], validations: list[dict[str, Any]]) -> None:
    for v in validations:
        if "eq" in v:
            fld, exp = v["eq"]
            act = _get_actual(resp, fld)
            assert act == exp, f"Expected {fld}={exp!r}, got {act!r}"
        elif "ne" in v:
            fld, exp = v["ne"]
            act = _get_actual(resp, fld)
            assert act != exp, f"{fld} = {act!r} == {exp!r}"
        elif (op := next((n for n in _NUM_OPS if n in v), None)):
            fld, exp = v[op]
            act = _get_actual(resp, fld)
            if not isinstance(act, (int, float)) or not isinstance(exp, (int, float)):
                raise AssertionError(f"{fld} numeric comparison requires numbers, got {act!r} and {exp!r}")
            if not _NUM_OPS[op](act, exp):
                raise AssertionError(f"{fld} = {act!r} !{op} {exp!r}")
        elif "contains" in v:
            fld, exp = v["contains"]
            act = _get_actual(resp, fld)
            assert act is not None and str(exp) in str(act), f"{fld} does not contain {exp!r}"
        elif "exists" in v:
            act = _get_actual(resp, v["exists"])
            assert act is not None, f"Expected {v['exists']} to exist"
        else:
            raise AssertionError(f"Unsupported validation: {v}")

# ---------------------------------------------------------------------------
# Case executor
# ---------------------------------------------------------------------------

def _rctx(rt: _RuntimeContext) -> dict:
    return dict(env=rt.env, project=rt.project_vars, runtime=rt.runtime_vars, steps=rt.step_outputs)


def _execute_steps(
    steps: list[StepSpec], *, phase: str, rt: _RuntimeContext, client: HttpClient,
    flows: dict[str, FlowSpec], cont: bool, results: list[StepExecutionResult],
) -> tuple[bool, str | None, str | None]:
    first_fail = first_reason = None
    for step in steps:
        if step.use and step.use.startswith("flow:"):
            flow = flows.get(step.use.split(":", 1)[1])
            if flow is None:
                raise AssertionError(f"Unknown flow: {step.use}")
            rendered_inputs = _render_value(deepcopy(step.inputs or {}), **_rctx(rt))
            saved = {k: rt.runtime_vars[k] for k in rendered_inputs if k in rt.runtime_vars}
            rt.runtime_vars.update(rendered_inputs)
            try:
                ok, fs, fr = _execute_steps(flow.steps, phase=phase, rt=rt, client=client, flows=flows, cont=cont, results=results)
            finally:
                for k in rendered_inputs:
                    if k in saved:
                        rt.runtime_vars[k] = saved[k]
                    else:
                        rt.runtime_vars.pop(k, None)
            if not ok and first_fail is None:
                first_fail, first_reason = fs, fr
            if not ok and not cont:
                return False, first_fail, first_reason
            continue

        if step.sleep is not None:
            time.sleep(float(step.sleep))
            if not step.request:
                continue

        if not step.request:
            continue
        req = _render_value(deepcopy(step.request), **_rctx(rt))
        default_headers = rt.project_defaults.get("headers") or {}
        if default_headers:
            merged = dict(_render_value(deepcopy(default_headers), **_rctx(rt)))
            merged.update(req.get("headers") or {})
            req["headers"] = merged
        resp = client.send(**req)
        rt.last_response = resp
        key = step.name or f"step_{len(rt.step_outputs)+1}"
        rt.step_outputs[key] = resp
        if step.save_as:
            rt.step_outputs[step.save_as] = resp

        extracted: dict[str, Any] = {}
        for k, expr in (step.extract or {}).items():
            val = extract_path(resp.get("json") or {}, expr)
            rt.runtime_vars[k] = val
            extracted[k] = val

        sr = StepExecutionResult(
            phase=phase, name=step.name, alias=step.save_as, status="passed",
            request={"method": req.get("method"), "url": req.get("url")},
            response={"status_code": resp.get("status_code")},
            extracted=extracted,
        )
        try:
            run_validations(resp, step.validate or [])
        except AssertionError as exc:
            sr.status = "failed"
            sr.error = str(exc)
            results.append(sr)
            if first_fail is None:
                first_fail, first_reason = step.name, str(exc)
            if not cont:
                return False, first_fail, first_reason
            continue
        results.append(sr)

    return (first_fail is None), first_fail, first_reason


def execute_case(
    project: ProjectSpec, case: CaseSpec, *,
    client: HttpClient | None = None, env: dict[str, str] | None = None,
    flows: dict[str, FlowSpec] | None = None,
) -> CaseExecutionResult:
    rt = _RuntimeContext(env=env or {}, project_vars=dict(project.vars), project_defaults=dict(project.defaults))
    api = client or HttpClient(project.base_url)
    fl = flows or {}
    cont = case.continue_on_failure or case.on_failure == "continue"
    step_results: list[StepExecutionResult] = []

    ok, fs, fr = _execute_steps(case.setup, phase="setup", rt=rt, client=api, flows=fl, cont=False, results=step_results)
    if not ok:
        _execute_steps(case.teardown, phase="teardown", rt=rt, client=api, flows=fl, cont=False, results=step_results)
        return CaseExecutionResult(case_id=case.id, case_name=case.name, status="failed", failed_step=fs, reason=fr, steps=step_results)

    ok, fs, fr = _execute_steps(case.steps, phase="steps", rt=rt, client=api, flows=fl, cont=cont, results=step_results)
    _execute_steps(case.teardown, phase="teardown", rt=rt, client=api, flows=fl, cont=False, results=step_results)
    if not ok:
        return CaseExecutionResult(case_id=case.id, case_name=case.name, status="failed", failed_step=fs, reason=fr, steps=step_results)
    return CaseExecutionResult(case_id=case.id, case_name=case.name, status="passed", steps=step_results)

# ---------------------------------------------------------------------------
# Result writer
# ---------------------------------------------------------------------------

def write_results(results: list[CaseExecutionResult], output_path: Path) -> None:
    payload = {
        "summary": {
            "total": len(results),
            "passed": sum(r.status == "passed" for r in results),
            "failed": sum(r.status == "failed" for r in results),
        },
        "cases": [asdict(r) for r in results],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
