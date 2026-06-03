"""文本上下文压缩策略。"""


def compress_text(text: str, max_chars: int) -> str:
    """按字符预算压缩文本，保留稳定的省略标记。"""
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    if max_chars == 1:
        return "…"
    return text[: max_chars - 1].rstrip() + "…"
