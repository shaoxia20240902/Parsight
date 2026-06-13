"""JSON 提取工具 — 集中处理 LLM 返回文本中的 JSON 容错解析。"""

import json
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def extract_json(text: str, *, max_preview: int = 500) -> Dict[str, Any]:
    """从 LLM 返回文本中提取 JSON 对象，含容错修复。

    处理流程：
    1. 去除首尾空白
    2. 去除 markdown 代码块包裹（```json / ```）
    3. 尝试直接 json.loads
    4. 尝试定位最外层花括号并解析
    5. 仍失败则抛出 ValueError

    Args:
        text: LLM 原始返回文本
        max_preview: 错误信息中保留的原文最大长度

    Returns:
        解析后的 JSON 对象
    """
    if not isinstance(text, str):
        raise ValueError(f"extract_json 期望输入字符串，实际为 {type(text).__name__}")

    text = text.strip()
    if not text:
        raise ValueError("extract_json 输入为空字符串")

    # 去除 markdown 代码块包裹
    if text.startswith("```"):
        lines = text.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    # 直接解析
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # 定位最外层花括号
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
        try:
            parsed = json.loads(text[brace_start : brace_end + 1])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    preview = text[:max_preview]
    raise ValueError(f"无法从 LLM 输出中提取 JSON 对象，原始内容: {preview}")


def safe_extract_json(text: str, *, fallback: Any = None, max_preview: int = 500) -> Any:
    """安全版本的 extract_json，失败时返回 fallback 而不是抛出异常。"""
    try:
        return extract_json(text, max_preview=max_preview)
    except Exception as e:
        logger.warning(f"safe_extract_json 解析失败: {e}")
        return fallback
