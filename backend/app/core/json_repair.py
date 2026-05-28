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

    - 去除尾随多余闭合括号（LLM 常输出 }} 等）
    - 补全缺失的括号
    - 删除末尾多余逗号
    """
    s = json_str.strip()
    if not s:
        return s

    # 去除尾随多余 } 或 ]
    s = _strip_trailing_brackets(s)

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


def _strip_trailing_brackets(s: str) -> str:
    """去除 JSON 末尾多余的闭合括号。

    LLM 有时输出 {"key": "val"}} 这类多了一个 } 的 JSON。
    通过逐个尝试解析来找到最短的合法 JSON 前缀。
    """
    # 只处理末尾有额外 } 或 ] 的情况
    stripped = s.rstrip()
    if not stripped:
        return s

    # 快速检查：如果直接能解析就不处理
    try:
        json.loads(stripped)
        return stripped
    except json.JSONDecodeError:
        pass

    # 尝试逐个去掉末尾的 } 或 ]
    while stripped and stripped[-1] in ("}", "]"):
        stripped = stripped[:-1].rstrip()
        try:
            json.loads(stripped)
            return stripped
        except json.JSONDecodeError:
            continue

    # 所有尝试都失败，返回原始字符串
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
