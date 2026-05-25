"""Agent 输入输出安全审核模块 — 轻量级正则 + 关键词黑名单。"""

import logging
import re

logger = logging.getLogger(__name__)

# 输入注入检测模式
_INJECTION_PATTERNS = [
    r"忽略(之前|上述|以上).*?指令",
    r"ignore\s+(previous|above|prior)\s+instructions?",
    r"system\s*:\s*",
    r"你(现在|现在起|现在开始).*?(是|作为|扮演)",
    r"forget\s+(everything|all|previous)",
    r"DAN\s*(模式|mode)",
    r"jailbreak",
]

# 敏感词黑名单
_SENSITIVE_KEYWORDS = [
    "密码",
    "password",
    "token",
    "密钥",
    "secret",
    "api_key",
    "信用卡",
    "身份证号",
    "银行卡",
    "cvv",
    "pin",
]

# PII 正则模式（按优先级排序，长模式优先避免短模式误匹配）
_PII_PATTERNS = {
    "id_card": (re.compile(r"\d{17}[\dXx]|\d{15}"), "[身份证号已隐藏]"),
    "mobile": (re.compile(r"1[3-9]\d{9}"), "[手机号已隐藏]"),
    "api_key": (re.compile(r"sk-[a-zA-Z0-9]{32,48}"), "[API_KEY已隐藏]"),
    "email": (
        re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
        "[邮箱已隐藏]",
    ),
}

_INJECTION_REGEX = [re.compile(p, re.IGNORECASE) for p in _INJECTION_PATTERNS]


def check_input(text: str) -> tuple[bool, str | None]:
    """检测输入是否包含注入攻击或敏感词。

    Args:
        text: 用户输入文本。

    Returns:
        (是否通过, 拦截原因)。通过时原因返回 None。
    """
    if not text or not isinstance(text, str):
        return True, None

    for pattern in _INJECTION_REGEX:
        if pattern.search(text):
            reason = f"检测到潜在注入模式: {pattern.pattern[:30]}..."
            logger.warning("Guardrails 拦截输入 | reason=%s", reason)
            return False, reason

    lower = text.lower()
    for keyword in _SENSITIVE_KEYWORDS:
        if keyword in lower:
            reason = f"检测到敏感关键词: {keyword}"
            logger.warning("Guardrails 拦截输入 | reason=%s", reason)
            return False, reason

    return True, None


def filter_output(text: str) -> str:
    """过滤输出中的 PII 信息。

    Args:
        text: Agent 输出文本。

    Returns:
        过滤后的文本。
    """
    if not text or not isinstance(text, str):
        return text

    result = text
    for name, (pattern, replacement) in _PII_PATTERNS.items():
        result, count = pattern.subn(replacement, result)
        if count:
            logger.info("Guardrails 过滤输出 PII | type=%s, count=%d", name, count)

    return result


__all__ = ["check_input", "filter_output"]
