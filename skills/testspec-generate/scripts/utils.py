#!/usr/bin/env python3
"""
TestSpec 共享工具函数模块。
"""
import json
import logging
import sys
from typing import Union

logger = logging.getLogger(__name__)


def configure_logging() -> None:
    """配置日志输出格式（用于独立脚本执行）。"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s: %(message)s',
        stream=sys.stderr
    )


def extract_testcases(data: Union[list, dict]) -> list:
    """从 testcases.json 中提取测试用例列表。

    Args:
        data: 包含 testcases 键的字典（schema v2）

    Returns:
        list: 测试用例列表，如果格式不支持则返回空列表
    """
    if isinstance(data, dict) and "testcases" in data:
        return data["testcases"]
    if isinstance(data, list):
        return data
    return []


def load_json_file(file_path: str) -> Union[list, dict]:
    """加载 JSON 文件并处理常见错误。

    Args:
        file_path: JSON 文件路径

    Returns:
        解析后的 JSON 数据（列表或字典）

    Raises:
        SystemExit: 文件不存在或 JSON 格式无效时退出
    """
    try:
        with open(file_path, encoding="utf-8-sig") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error("文件不存在: %s", file_path)
        sys.exit(1)
    except json.JSONDecodeError as e:
        logger.error("%s JSON 格式无效（行 %s 列 %s）。", file_path, e.lineno, e.colno)
        logger.error("常见原因：字符串值中包含未转义的双引号。请检查并将 \" 转义为 \\\" 或使用「」替代。")
        sys.exit(1)


def load_and_validate_testcases(file_path: str) -> list:
    """加载 JSON 文件并提取验证测试用例。

    Args:
        file_path: testcases.json 文件路径

    Returns:
        测试用例列表

    Raises:
        SystemExit: 文件无效或未找到测试用例时退出
    """
    raw_data = load_json_file(file_path)
    test_cases = extract_testcases(raw_data)
    if not test_cases:
        logger.error("JSON 格式不正确：应为用例数组或包含 testcases 字段的对象")
        sys.exit(1)
    return test_cases
