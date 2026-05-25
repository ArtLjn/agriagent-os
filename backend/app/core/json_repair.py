"""JSON 解析容错 — 提取 Markdown 代码块 + 自动修复常见格式错误。"""

import json
import logging
import re

logger = logging.getLogger(__name__)

_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```")


def extract_json(text: str) -> str | None:
    """从文本中提取 JSON 内容（支持 Markdown 代码块）。"""
    text = text.strip()
    match = _JSON_BLOCK_RE.search(text)
    if match:
        return match.group(1).strip()
    return text


def repair_json(json_str: str) -> str:
    """自动修复常见 JSON 格式错误。

    - 补全缺失的括号
    - 删除末尾多余逗号
    """
    s = json_str.strip()
    if not s:
        return s

    # 补全缺失的括号
    open_braces = s.count("{")
    close_braces = s.count("}")
    missing = open_braces - close_braces
    if missing > 0:
        s += "}" * missing

    open_brackets = s.count("[")
    close_brackets = s.count("]")
    missing_brackets = open_brackets - close_brackets
    if missing_brackets > 0:
        s += "]" * missing_brackets

    # 移除末尾多余逗号（对象和数组）
    s = re.sub(r",(\s*[}\]])", r"\1", s)

    return s


def safe_parse_json(text: str) -> dict:
    """安全解析 JSON：提取 → 修复 → 解析。

    Returns:
        解析后的 dict。

    Raises:
        ValueError: 所有修复手段都失败时。
    """
    raw = extract_json(text)
    if not raw:
        raise ValueError("无法提取 JSON 内容")

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        repaired = repair_json(raw)
        try:
            return json.loads(repaired)
        except json.JSONDecodeError as e:
            logger.error("JSON 解析失败 | raw=%s error=%s", raw[:100], e)
            raise ValueError(f"AI 返回格式异常: {raw[:100]}")


__all__ = ["extract_json", "repair_json", "safe_parse_json"]
