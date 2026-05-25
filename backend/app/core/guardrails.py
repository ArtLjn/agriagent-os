"""Agent 输入输出安全审核模块 — 注入检测 + 敏感词 + PII + 英文输出检测。"""

import logging
import re

from app.core.term_whitelist import is_whitelisted

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

# PII 正则模式
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

# 英文句子检测：连续 3+ 个英文单词（排除白名单单词）
_ENGLISH_WORD_RE = re.compile(r"[a-zA-Z]{2,}")


def _has_english_sentence(text: str) -> bool:
    """检测文本中是否包含英文句子（连续 3+ 英文单词）。

    先移除 PII 模式（email、API key 等），避免其中的英文片段误判。
    """
    cleaned = text
    for _name, (pattern, _replacement) in _PII_PATTERNS.items():
        cleaned = pattern.sub("", cleaned)
    words = _ENGLISH_WORD_RE.findall(cleaned)
    non_whitelisted = [w for w in words if not is_whitelisted(w)]
    return len(non_whitelisted) >= 3


def check_input(text: str) -> tuple[bool, str | None]:
    """检测输入是否包含注入攻击或敏感词。"""
    if not text or not isinstance(text, str):
        return True, None

    for pattern in _INJECTION_REGEX:
        if pattern.search(text):
            reason = "检测到潜在注入模式"
            logger.warning("Guardrails 拦截输入 | reason=%s", reason)
            return False, reason

    lower = text.lower()
    for keyword in _SENSITIVE_KEYWORDS:
        if keyword in lower:
            reason = f"检测到敏感关键词: {keyword}"
            logger.warning("Guardrails 拦截输入 | reason=%s", reason)
            return False, reason

    return True, None


def _is_json_like(text: str) -> bool:
    """判断文本是否看起来像 JSON（结构化数据不进行英文检测）。"""
    import json

    stripped = text.strip()

    # 直接 JSON
    if stripped.startswith(("{", "[")):
        try:
            json.loads(stripped)
            return True
        except (json.JSONDecodeError, ValueError):
            pass

    # Markdown 代码块包裹的 JSON
    if "```" in stripped:
        import re
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", stripped)
        if match:
            try:
                json.loads(match.group(1).strip())
                return True
            except (json.JSONDecodeError, ValueError):
                pass

    return False


def filter_output(text: str) -> str:
    """过滤输出中的 PII 信息和英文句子。"""
    if not text or not isinstance(text, str):
        return text

    # JSON 结构化输出跳过英文检测（如记账解析结果）
    if not _is_json_like(text):
        if _has_english_sentence(text):
            logger.warning("Guardrails 拦截输出英文 | text_preview=%s", text[:100])
            return "系统异常，请重试"

    # PII 过滤
    result = text
    for name, (pattern, replacement) in _PII_PATTERNS.items():
        result, count = pattern.subn(replacement, result)
        if count:
            logger.info("Guardrails 过滤输出 PII | type=%s, count=%d", name, count)

    return result


def cleanup_old_logs(db=None, days: int = 30) -> None:
    """删除 N 天前的 guardrails_logs 记录。"""
    if db is None:
        return
    try:
        from datetime import datetime, timedelta

        from app.models.guardrails_log import GuardrailsLog

        cutoff = datetime.now() - timedelta(days=days)
        db.query(GuardrailsLog).filter(GuardrailsLog.created_at < cutoff).delete(synchronize_session=False)
        db.commit()
        logger.info("Guardrails 日志清理完成 | cutoff=%s", cutoff)
    except Exception:
        logger.exception("Guardrails 日志清理失败")


__all__ = ["check_input", "filter_output", "cleanup_old_logs", "_has_english_sentence"]
