"""意图路由 — 基于规则的用户输入分类。"""

import enum
import hashlib
import logging
import re

logger = logging.getLogger(__name__)


class IntentType(enum.Enum):
    """意图类型。"""

    GREETING = "greeting"
    QUERY = "query"
    WRITE = "write"
    AGENT = "agent"


_GREETING_PATTERNS = re.compile(
    r"^(你好|您好|在吗|在不在|嗨|hi|hello|hey|早上好|晚上好|下午好|"
    r"谢谢|谢谢你|辛苦了|辛苦啦|你是谁|你叫什么|介绍一下自己)"
    r"(呀|啊|哈|哇)?[\s!！.。?？～~]*$",
    re.IGNORECASE,
)

_WRITE_KEYWORDS = {
    "记账",
    "记一笔",
    "买了",
    "卖了",
    "花了",
    "收入",
    "支出",
    "赊账",
    "付了",
    "收了",
    "创建",
    "建一个",
    "记录",
    "还了",
    "还钱",
    "浇水",
    "施肥",
    "打药",
    "除草",
    "播种",
}

_QUERY_KEYWORDS = {
    "花了多少",
    "赚了多少",
    "收支",
    "余额",
    "天气",
    "预报",
    "成本",
    "利润",
    "趋势",
    "茬口",
    "进度",
    "阶段",
    "账单",
    "日志",
    "状态",
    "综合",
}


def classify_intent(message: str) -> IntentType:
    """基于规则分类用户意图。保守策略：不确定时走 AGENT。"""
    stripped = message.strip()
    if not stripped:
        return IntentType.AGENT

    if _GREETING_PATTERNS.match(stripped):
        logger.debug("意图路由 | msg=%s | intent=greeting", stripped[:20])
        return IntentType.GREETING

    # QUERY 优先检查：QUERY 关键词是更具体的短语，
    # 避免被 WRITE 短词（如"花了"）提前匹配
    if any(kw in stripped for kw in _QUERY_KEYWORDS):
        logger.debug("意图路由 | msg=%s | intent=query", stripped[:20])
        return IntentType.QUERY

    if any(kw in stripped for kw in _WRITE_KEYWORDS):
        logger.debug("意图路由 | msg=%s | intent=write", stripped[:20])
        return IntentType.WRITE

    logger.debug("意图路由 | msg=%s | intent=agent", stripped[:20])
    return IntentType.AGENT


_GREETING_REPLIES = [
    "你好呀，我是芽芽。想查天气、记一笔，或者看看农场情况都可以找我。",
    "在呢，我是芽芽。今天想先看天气、收支，还是农事安排？",
    "嗨，芽芽在这儿。你说一句，我来帮你查或记。",
]

_IDENTITY_REPLIES = [
    "我是芽芽，你的农场管理助手。查天气、记账、看农事，我都可以陪你一起弄。",
]

_THANKS_REPLIES = [
    "不客气，芽芽随时在。",
    "收到，能帮上忙就好。",
]


def get_greeting_reply(message: str) -> str:
    """返回问候语回复。"""
    stripped = message.strip().lower()
    if any(word in stripped for word in ("你是谁", "你叫什么", "介绍一下自己")):
        return _IDENTITY_REPLIES[0]
    if any(word in stripped for word in ("谢谢", "辛苦")):
        idx = int(hashlib.md5(message.encode()).hexdigest()[:8], 16) % len(
            _THANKS_REPLIES
        )
        return _THANKS_REPLIES[idx]

    idx = int(hashlib.md5(message.encode()).hexdigest()[:8], 16) % len(
        _GREETING_REPLIES
    )
    return _GREETING_REPLIES[idx]
