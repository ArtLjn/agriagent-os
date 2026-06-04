"""Agent 输入输出安全审核模块。"""

import logging
import re

logger = logging.getLogger(__name__)

_INJECTION_PATTERNS = [
    r"忽略(之前|上述|以上).*?指令",
    r"ignore\s+(previous|above|prior)\s+instructions?",
    r"system\s*:\s*",
    r"你(现在|现在起|现在开始).*?(是|作为|扮演)",
    r"forget\s+(everything|all|previous)",
    r"DAN\s*(模式|mode)",
    r"jailbreak",
]

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
_TOOL_CALL_LEAK_RE = re.compile(r"\[\s*[a-zA-Z_][a-zA-Z0-9_]*\s*\([^\]]*\)\s*\]")
_JSON_TOOL_CALL_RE = re.compile(
    r'\{\s*"name"\s*:\s*"[^"]+"\s*,\s*"parameters"\s*:\s*\{[^}]*\}\s*\}',
    re.DOTALL,
)
_PY_DICT_TOOL_CALL_RE = re.compile(
    r"\{\s*'name'\s*:\s*'[^']+'\s*,\s*'parameters'\s*:\s*\{[^}]*\}\s*\}",
    re.DOTALL,
)
_JSON_ACTION_RE = re.compile(
    r'\{\s*"(?:name|action|tool|function)"\s*:\s*"[^"]+"\s*,'
    r'\s*"(?:parameters|params|args|arguments)"\s*:\s*\{',
    re.DOTALL,
)

_FALLBACK_TOOL_CALL_REPLY = "检测到工具调用格式异常，正在重新处理。请稍等片刻。"


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


def filter_output(text: str) -> str:
    """过滤输出中的不安全内容和 PII 信息。"""
    if not text or not isinstance(text, str):
        return text

    result = _filter_tool_leaks(text)
    for name, (pattern, replacement) in _PII_PATTERNS.items():
        result, count = pattern.subn(replacement, result)
        if count:
            logger.info(
                "Guardrails 过滤输出 PII | category=pii_%s | count=%d", name, count
            )
    return result


def cleanup_old_logs(db=None, days: int = 30) -> None:
    """删除 N 天前的 guardrails_logs 记录。"""
    if db is None:
        return
    try:
        from datetime import datetime, timedelta

        from app.models.guardrails_log import GuardrailsLog

        cutoff = datetime.now() - timedelta(days=days)
        db.query(GuardrailsLog).filter(GuardrailsLog.created_at < cutoff).delete(
            synchronize_session=False
        )
        db.commit()
        logger.info("Guardrails 日志清理完成 | cutoff=%s", cutoff)
    except Exception:
        logger.exception("Guardrails 日志清理失败")


def _filter_tool_leaks(text: str) -> str:
    result, count = _TOOL_CALL_LEAK_RE.subn("", text)
    if count:
        logger.info(
            "Guardrails 过滤工具调用泄漏 | category=tool_leak_bracket | count=%d", count
        )
        result = re.sub(r"\n{3,}", "\n\n", result).strip()

    if (
        _JSON_TOOL_CALL_RE.search(result)
        or _PY_DICT_TOOL_CALL_RE.search(result)
        or _JSON_ACTION_RE.search(result)
    ):
        logger.warning(
            "Guardrails 检测到 JSON 工具调用泄漏 | category=tool_leak_json | text=%s",
            result[:200],
        )
        if _is_mostly_json_tool_call(result):
            logger.warning(
                "Guardrails 拦截纯 JSON 工具调用回复，返回 fallback | category=tool_leak_json_pure"
            )
            return _FALLBACK_TOOL_CALL_REPLY
        result, count = _JSON_TOOL_CALL_RE.subn("", result)
        py_result, py_count = _PY_DICT_TOOL_CALL_RE.subn("", result)
        result = py_result
        count += py_count
        if count:
            logger.info(
                "Guardrails 移除部分 JSON 工具调用 | category=tool_leak_json_partial | count=%d",
                count,
            )
            result = re.sub(r"\n{3,}", "\n\n", result).strip()
    return result


def _is_mostly_json_tool_call(text: str) -> bool:
    """判断文本是否主要由 JSON 工具调用组成。"""
    if not text:
        return False
    cleaned = _JSON_TOOL_CALL_RE.sub("", text).strip()
    cleaned = _PY_DICT_TOOL_CALL_RE.sub("", cleaned).strip()
    cleaned = re.sub(r"[\s -⁯⸀-⹿\\'!\"#$%&()*+,./:;<=>?@[\]^_`{|}~]", "", cleaned)
    return len(cleaned) < 10


__all__ = ["check_input", "filter_output", "cleanup_old_logs"]
