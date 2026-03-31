#!/usr/bin/env python3
"""
校验 TestSpec agentic skill 的共享规则源与引用关系。

用途：
- 检查新增的 shared rule files 是否存在
- 检查 testspec-analysis / testspec-generate 中引用的共享文件是否存在
- 检查分析模式和测试类型策略中的关键 ID 是否齐全
- 检查输出契约中是否声明 Excel / XMind 的兼容性约束
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SKILLS_DIR = ROOT / "skills"
SHARED_DIR = SKILLS_DIR / "testspec-shared"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def heading_ids(markdown: str) -> set[str]:
    return set(re.findall(r"^##\s+([a-z0-9_-]+)\s*$", markdown, flags=re.MULTILINE))


def referenced_relative_paths(markdown: str) -> set[str]:
    return set(re.findall(r"`(\.\./testspec-shared/[^`]+)`", markdown))


def check(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []

    analysis_skill = SKILLS_DIR / "testspec-analysis" / "SKILL.md"
    generate_skill = SKILLS_DIR / "testspec-generate" / "SKILL.md"
    analysis_modes = SHARED_DIR / "analysis-modes.md"
    test_type_strategies = SHARED_DIR / "test-type-strategies.md"
    output_contracts = SHARED_DIR / "output-contracts.md"

    required_files = [
        analysis_skill,
        generate_skill,
        analysis_modes,
        test_type_strategies,
        output_contracts,
    ]
    for path in required_files:
        check(path.exists(), f"缺少文件：{path}", errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    analysis_modes_text = read_text(analysis_modes)
    strategy_text = read_text(test_type_strategies)
    output_contracts_text = read_text(output_contracts)
    analysis_skill_text = read_text(analysis_skill)
    generate_skill_text = read_text(generate_skill)

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

    for owner, text in {
        str(analysis_skill): analysis_skill_text,
        str(generate_skill): generate_skill_text,
    }.items():
        for rel_path in referenced_relative_paths(text):
            target = Path(owner).parent / rel_path
            check(target.exists(), f"{owner} 引用了不存在的文件：{rel_path}", errors)

    check("Excel 输出契约" in output_contracts_text, "output-contracts 缺少 Excel 输出契约章节", errors)
    check("XMind 输出契约" in output_contracts_text, "output-contracts 缺少 XMind 输出契约章节", errors)
    check("不得擅自改动历史 schema" in output_contracts_text, "output-contracts 未声明历史 schema 兼容性", errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("OK: skill contracts validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
