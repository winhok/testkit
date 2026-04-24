#!/usr/bin/env python3
"""
校验 TestSpec skill 契约与跨文件一致性。

用途：
- 检查 testspec-* 主流程技能与 shared 规则源是否齐全
- 检查 shared 引用是否统一使用 ../testspec-shared/references/ 相对路径
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
SHARED_DIR = SKILLS_DIR / "testspec-shared"
SHARED_REFERENCES_DIR = SHARED_DIR / "references"

ACTIVE_SKILL_PATHS = [
    SKILLS_DIR / "testspec-new" / "SKILL.md",
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
    SHARED_REFERENCES_DIR / "analysis-modes.md",
    SHARED_REFERENCES_DIR / "test-type-strategies.md",
    SHARED_REFERENCES_DIR / "output-contracts.md",
    SHARED_REFERENCES_DIR / "naming-contract.md",
    SHARED_REFERENCES_DIR / "testlib-contracts.md",
    SHARED_REFERENCES_DIR / "artifact-templates.md",
]

REVIEW_REFERENCE_PATHS = [
    SKILLS_DIR / "testspec-review" / "review-report-template.md",
    SKILLS_DIR / "testspec-review" / "references" / "review-dimensions.md",
]

INTEGRATION_EVAL_PATH = SHARED_DIR / "evals" / "evals.json"

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
    refs = set(re.findall(r"`(\.\./testspec-shared/[^`]+)`", markdown))
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
        *REVIEW_REFERENCE_PATHS,
        INTEGRATION_EVAL_PATH,
    ]
    for path in required_files:
        check(path.exists(), f"缺少文件：{path}", errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    analysis_modes_text = read_text(SHARED_REFERENCES_DIR / "analysis-modes.md")
    strategy_text = read_text(SHARED_REFERENCES_DIR / "test-type-strategies.md")
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
    check("不得擅自改动历史 schema" in output_contracts_text, "output-contracts 未声明历史 schema 兼容性", errors)

    check(
        integration_eval.get("skill_name") == "testspec-chain",
        "testspec-shared integration eval 的 skill_name 必须是 testspec-chain",
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
            f"{skill_path} 存在裸 shared 引用，需改为 ../testspec-shared/references/ 相对路径",
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
