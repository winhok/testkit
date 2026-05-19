#!/usr/bin/env python3
"""
校验 TestSpec skill 契约与跨文件一致性。

用途：
- 检查 testspec-* 主流程技能、阶段 references 与 shared 规则源是否齐全
- 检查 shared 引用是否统一使用 ../_testspec-shared/references/ 相对路径
- 检查 SKILL.md 行数是否符合精简约束（<= 500）
- 检查 analysis-modes / test-type-strategies 的关键 ID
- 检查 output-contracts 兼容性声明
- 检查 generate 脚本调用路径是否与仓库结构一致
- 检查 review 深度策略文案是否统一（auto + --deep）
"""
from __future__ import annotations

import re
import sys
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SKILLS_DIR = ROOT / "skills"
SHARED_DIR = SKILLS_DIR / "_testspec-shared"
SHARED_REFERENCES_DIR = SHARED_DIR / "references"

ACTIVE_SKILL_PATHS = [
    SKILLS_DIR / "testspec-new" / "SKILL.md",
    SKILLS_DIR / "testspec-update" / "SKILL.md",
    SKILLS_DIR / "testspec-analysis" / "SKILL.md",
    SKILLS_DIR / "testspec-points" / "SKILL.md",
    SKILLS_DIR / "testspec-generate" / "SKILL.md",
    SKILLS_DIR / "testspec-review" / "SKILL.md",
    SKILLS_DIR / "testspec-publish" / "SKILL.md",
]

SHARED_RULE_PATHS = [
    SHARED_REFERENCES_DIR / "common.md",
    SHARED_REFERENCES_DIR / "thinking-protocol.md",
    SHARED_REFERENCES_DIR / "reflection-protocol.md",
    SHARED_REFERENCES_DIR / "context-protocol.md",
    SHARED_REFERENCES_DIR / "output-contracts.md",
    SHARED_REFERENCES_DIR / "naming-contract.md",
]

STAGE_REFERENCE_PATHS = [
    SKILLS_DIR / "testspec-new" / "references" / "proposal-template.md",
    SKILLS_DIR / "testspec-new" / "references" / "requirements-template.md",
    SKILLS_DIR / "testspec-analysis" / "references" / "analysis-modes.md",
    SKILLS_DIR / "testspec-analysis" / "references" / "requirements-analysis-template.md",
    SKILLS_DIR / "testspec-points" / "references" / "testpoints-template.md",
    SKILLS_DIR / "testspec-generate" / "references" / "test-type-strategies.md",
    SKILLS_DIR / "testspec-publish" / "references" / "testlib-contracts.md",
]

REVIEW_REFERENCE_PATHS = [
    SKILLS_DIR / "testspec-review" / "review-report-template.md",
    SKILLS_DIR / "testspec-review" / "references" / "review-dimensions.md",
]

WORKFLOW_EVAL_PATHS = [
    SKILLS_DIR / "testspec-new" / "evals" / "evals.json",
    SKILLS_DIR / "testspec-update" / "evals" / "evals.json",
]

TESTLIB_TOOL_PATHS = [
    SHARED_DIR / "scripts" / "validate_testcases.py",
    SHARED_DIR / "scripts" / "validate_testlib.py",
    SHARED_DIR / "scripts" / "rebuild_testlib_index.py",
    SHARED_DIR / "tests" / "test_testlib_tools.py",
]

INTEGRATION_EVAL_PATH = SHARED_DIR / "evals" / "evals.json"
WORKFLOW_DIAGRAM_JSON_PATH = SHARED_DIR / "diagrams" / "testspec-workflow.json"

BARE_SHARED_NAMES_PATTERN = re.compile(
    r"`(common\.md|thinking-protocol\.md|reflection-protocol\.md|context-protocol\.md|"
    r"analysis-modes\.md|test-type-strategies\.md|output-contracts\.md|"
    r"naming-contract\.md|testlib-contracts\.md)`"
)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def heading_ids(markdown: str) -> set[str]:
    return set(re.findall(r"^##\s+([a-z0-9_-]+)\s*$", markdown, flags=re.MULTILINE))


def referenced_relative_paths(markdown: str) -> set[str]:
    refs = set(re.findall(r"`(\.\./_testspec-shared/[^`]+)`", markdown))
    refs.update(re.findall(r"`(references/[^`]+)`", markdown))
    if "`review-report-template.md`" in markdown:
        refs.add("review-report-template.md")
    return refs


def check(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []

    required_files = [
        *ACTIVE_SKILL_PATHS,
        *SHARED_RULE_PATHS,
        *STAGE_REFERENCE_PATHS,
        *REVIEW_REFERENCE_PATHS,
        *WORKFLOW_EVAL_PATHS,
        *TESTLIB_TOOL_PATHS,
        INTEGRATION_EVAL_PATH,
        WORKFLOW_DIAGRAM_JSON_PATH,
        ROOT / "README.md",
    ]
    for path in required_files:
        check(path.exists(), f"缺少文件：{path}", errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    analysis_modes_text = read_text(SKILLS_DIR / "testspec-analysis" / "references" / "analysis-modes.md")
    strategy_text = read_text(SKILLS_DIR / "testspec-generate" / "references" / "test-type-strategies.md")
    output_contracts_text = read_text(SHARED_REFERENCES_DIR / "output-contracts.md")
    integration_eval = json.loads(read_text(INTEGRATION_EVAL_PATH))

    required_mode_ids = {
        "completeness",
        "testability",
        "feasibility",
        "clarity",
        "consistency",
        "logic",
    }
    actual_mode_ids = heading_ids(analysis_modes_text)
    missing_mode_ids = sorted(required_mode_ids - actual_mode_ids)
    check(not missing_mode_ids, f"analysis-modes 缺少模式：{', '.join(missing_mode_ids)}", errors)

    required_strategy_ids = {
        "smoke",
        "functional",
        "boundary",
        "exception",
        "permission",
        "security",
        "compatibility",
        "usability",
        "performance",
        "reliability",
        "tracking",
        "maintainability",
        "portability",
        "effect_ai",
        "effect_hardware",
    }
    actual_strategy_ids = heading_ids(strategy_text)
    missing_strategy_ids = sorted(required_strategy_ids - actual_strategy_ids)
    check(not missing_strategy_ids, f"test-type-strategies 缺少策略：{', '.join(missing_strategy_ids)}", errors)

    check("Excel 输出契约" in output_contracts_text, "output-contracts 缺少 Excel 输出契约章节", errors)
    check("XMind 输出契约" in output_contracts_text, "output-contracts 缺少 XMind 输出契约章节", errors)
    check("requirements.md" in output_contracts_text, "output-contracts 缺少 requirements.md 输出契约章节", errors)
    check("功能必须带验收条件" in output_contracts_text, "output-contracts 未声明 requirements.md 验收条件约束", errors)
    check("REQ-001" in output_contracts_text, "output-contracts 未声明 requirements.md REQ-ID 追溯约束", errors)
    check("RISK-001" in output_contracts_text, "output-contracts 未声明 requirements.md RISK-ID 风险约束", errors)
    check("需求质量复核" in output_contracts_text, "output-contracts 缺少 requirements.md 质量复核契约", errors)
    check("ready_for_analysis" in output_contracts_text, "output-contracts 缺少 requirements.md readiness 结论", errors)
    check("阻塞澄清项" in output_contracts_text, "output-contracts 缺少阻塞澄清项契约", errors)
    check("执行期动态跟进" in output_contracts_text, "output-contracts 缺少执行期动态跟进契约", errors)
    check("stale" in output_contracts_text, "output-contracts 缺少旧口径下游产物标记契约", errors)
    check("JSON 只能更新 `_context` 字段" in output_contracts_text, "output-contracts 缺少 JSON stale 标记契约", errors)
    check("Excel/XMind" in output_contracts_text, "output-contracts 缺少二进制导出 stale 标记契约", errors)
    check("接口真相源" in output_contracts_text, "output-contracts 缺少最新接口真相源契约", errors)
    check("可直接复制给产品" in output_contracts_text, "output-contracts 缺少产品问题清单契约", errors)
    check("不得擅自改动历史 schema" in output_contracts_text, "output-contracts 未声明历史 schema 兼容性", errors)
    context_protocol_text = read_text(SHARED_REFERENCES_DIR / "context-protocol.md")
    check("blocking_open_questions" in context_protocol_text, "context-protocol 缺少 blocking_open_questions 字段", errors)
    check("dynamic_followups" in context_protocol_text, "context-protocol 缺少 dynamic_followups 字段", errors)
    check("source_revision" in context_protocol_text, "context-protocol 缺少 source_revision 字段", errors)
    check("stale_downstream_artifacts" in context_protocol_text, "context-protocol 缺少 stale_downstream_artifacts 字段", errors)
    check("| `requirement_quality.readiness` | string | ready_for_analysis / needs_clarification / needs_revision / blocked | new/update |" in context_protocol_text, "context-protocol 未声明 update 会刷新 readiness", errors)
    update_skill_text = read_text(SKILLS_DIR / "testspec-update" / "SKILL.md")
    update_evals_text = read_text(SKILLS_DIR / "testspec-update" / "evals" / "evals.json")
    new_skill_text = read_text(SKILLS_DIR / "testspec-new" / "SKILL.md")
    requirements_template_text = read_text(SKILLS_DIR / "testspec-new" / "references" / "requirements-template.md")
    check("可复制给产品的问题清单" in new_skill_text, "testspec-new 缺少产品问题清单输出规则", errors)
    check("可复制给产品的问题清单" in requirements_template_text, "requirements-template 缺少产品问题清单小节", errors)
    check("Interface Replacement Mode" in update_skill_text, "testspec-update 缺少接口替换模式", errors)
    check("旧口径，仅供历史参考" in update_skill_text, "testspec-update 缺少旧 analysis 明确提示", errors)
    check("旧口径历史记录" in update_skill_text, "testspec-update 缺少旧 analysis 冲突清理规则", errors)
    check("可复制给产品的问题清单" in update_skill_text, "testspec-update 缺少产品问题清单输出规则", errors)
    check("artifacts/source-prd.md" in update_skill_text, "testspec-update 缺少 UI/source-prd 沉淀规则", errors)
    check("Do not add Markdown stale notices to JSON" in update_skill_text, "testspec-update 缺少非 Markdown stale 保护规则", errors)
    check("create or update" in update_skill_text, "testspec-update 必须声明 requirements.md create or update 规则", errors)
    check("old_version + 1" in update_skill_text, "testspec-update 必须声明 source_revision.version 递增规则", errors)
    check("source_revision.updated_by_skill` to `testspec-update" in update_skill_text, "testspec-update 必须声明 updated_by_skill 写为 testspec-update", errors)
    check("stale_downstream_artifacts" in update_skill_text and "stale_reason" in update_skill_text and "next_skill" in update_skill_text, "testspec-update 必须回写 requirements.md stale context", errors)
    check("stale_downstream_artifacts" in update_evals_text and "requirements-analysis.md" in update_evals_text, "testspec-update eval 必须检查 requirements.md context stale 标记", errors)
    check("blocking_open_questions" in new_skill_text, "testspec-new 上下文播种缺少 blocking_open_questions", errors)
    check("dynamic_followups" in new_skill_text, "testspec-new 上下文播种缺少 dynamic_followups", errors)
    check("source_revision" in new_skill_text, "testspec-new 上下文播种缺少 source_revision", errors)
    readme_text = read_text(ROOT / "README.md")
    check("testspec-update" in readme_text, "README 缺少 testspec-update", errors)
    workflow_json_text = read_text(WORKFLOW_DIAGRAM_JSON_PATH)
    check("update(optional/repeatable)" in workflow_json_text, "testspec workflow diagram JSON 缺少 testspec-update", errors)
    workflow_diagram = json.loads(workflow_json_text)
    workflow_node_ids = {node.get("id") for node in workflow_diagram.get("nodes", [])}
    workflow_arrows = {
        (arrow.get("source"), arrow.get("target"))
        for arrow in workflow_diagram.get("arrows", [])
    }
    check("update" in workflow_node_ids, "testspec workflow diagram JSON 缺少 testspec-update 实际节点", errors)
    check("source_artifacts" in workflow_node_ids, "testspec workflow diagram JSON 缺少 source artifact 节点", errors)
    check(
        ("proposal", "update") in workflow_arrows or ("new", "update") in workflow_arrows,
        "testspec workflow diagram JSON 缺少进入 testspec-update 的边",
        errors,
    )
    check(
        ("update", "analysis") in workflow_arrows or ("source_artifacts", "analysis") in workflow_arrows,
        "testspec workflow diagram JSON 缺少 testspec-update 到 analysis 的收敛路径",
        errors,
    )
    check(
        re.search(r"\bopen_questions\b", "\n".join([
            context_protocol_text,
            new_skill_text,
            update_skill_text,
            update_evals_text,
            requirements_template_text,
            read_text(SKILLS_DIR / "testspec-analysis" / "SKILL.md"),
            read_text(SKILLS_DIR / "testspec-points" / "SKILL.md"),
            read_text(SKILLS_DIR / "testspec-generate" / "SKILL.md"),
            read_text(SKILLS_DIR / "testspec-review" / "SKILL.md"),
        ])) is None,
        "active TestSpec 文档仍包含旧 open_questions 字段，请使用 blocking_open_questions",
        errors,
    )
    testlib_contracts_text = read_text(SKILLS_DIR / "testspec-publish" / "references" / "testlib-contracts.md")
    check(
        "validate_testlib.py" in testlib_contracts_text,
        "testlib-contracts 缺少 validate_testlib.py 维护脚本说明",
        errors,
    )
    check(
        "rebuild_testlib_index.py" in testlib_contracts_text,
        "testlib-contracts 缺少 rebuild_testlib_index.py 维护脚本说明",
        errors,
    )

    check(
        integration_eval.get("skill_name") == "testspec-chain",
        "_testspec-shared integration eval 的 skill_name 必须是 testspec-chain",
        errors,
    )
    integration_cases = integration_eval.get("evals") or [{}]
    integration_assertions = integration_cases[0].get("assertions", [])
    programmatic_count = sum(1 for item in integration_assertions if item.get("check") == "programmatic")
    check(
        programmatic_count >= 4,
        "testspec-chain integration eval 至少需要 4 个 programmatic 断言",
        errors,
    )

    for skill_path in ACTIVE_SKILL_PATHS:
        text = read_text(skill_path)

        line_count = len(text.splitlines())
        check(line_count <= 500, f"{skill_path} 超过 500 行（当前 {line_count} 行）", errors)

        check(
            BARE_SHARED_NAMES_PATTERN.search(text) is None,
            f"{skill_path} 存在裸 shared 引用，需改为 ../_testspec-shared/references/ 相对路径",
            errors,
        )

        for rel_path in referenced_relative_paths(text):
            target = (skill_path.parent / rel_path).resolve()
            check(target.exists(), f"{skill_path} 引用了不存在的文件：{rel_path}", errors)

    generate_skill_text = read_text(SKILLS_DIR / "testspec-generate" / "SKILL.md")
    check(
        "python ./scripts/generate_excel.py" not in generate_skill_text,
        "testspec-generate 仍在使用错误脚本路径 ./scripts/generate_excel.py",
        errors,
    )
    check(
        "python ./scripts/generate_xmind.py" not in generate_skill_text,
        "testspec-generate 仍在使用错误脚本路径 ./scripts/generate_xmind.py",
        errors,
    )
    check(
        "python skills/testspec-generate/scripts/generate_excel.py" in generate_skill_text,
        "testspec-generate 缺少正确的 Excel 脚本调用路径",
        errors,
    )
    check(
        "python skills/testspec-generate/scripts/generate_xmind.py" in generate_skill_text,
        "testspec-generate 缺少正确的 XMind 脚本调用路径",
        errors,
    )

    publish_skill_text = read_text(SKILLS_DIR / "testspec-publish" / "SKILL.md")
    check(
        "artifacts/testcases.json" in publish_skill_text,
        "testspec-publish 未声明 artifacts/testcases.json 兜底输入路径",
        errors,
    )

    review_skill_text = read_text(SKILLS_DIR / "testspec-review" / "SKILL.md")
    check(
        "默认执行 `auto` 模式" in review_skill_text,
        "testspec-review 缺少 auto 深度模式声明",
        errors,
    )
    check(
        "`--deep`（显式）：强制加深深度" in review_skill_text,
        "testspec-review 缺少 --deep 强制加深语义声明",
        errors,
    )

    review_template_text = read_text(SKILLS_DIR / "testspec-review" / "review-report-template.md")
    check(
        "**评审深度**" in review_template_text,
        "review-report-template 缺少评审深度字段",
        errors,
    )
    check(
        "**深度触发原因**" in review_template_text,
        "review-report-template 缺少深度触发原因字段",
        errors,
    )
    check(
        "### 深度决策记录" in review_template_text,
        "review-report-template 缺少深度决策记录小节",
        errors,
    )

    review_dimensions_text = read_text(SKILLS_DIR / "testspec-review" / "references" / "review-dimensions.md")
    check(
        "### 三段评估定义" in review_dimensions_text,
        "review-dimensions 缺少 H3 三段评估定义",
        errors,
    )
    check(
        "### Oracle 审查维度" in review_dimensions_text,
        "review-dimensions 缺少 H7 Oracle 审查维度",
        errors,
    )
    check(
        "### 仪式感用例识别" in review_dimensions_text,
        "review-dimensions 缺少 H7 仪式感用例识别",
        errors,
    )

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("OK: skill contracts validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
