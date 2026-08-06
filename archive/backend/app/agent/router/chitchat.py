"""Chitchat/教程兜底分类器(封闭短语集)。

朴素路由模式下,在 RouterPolicy 之前识别寒暄/教程类无工具输入,
命中后直接走 fallback no_tools,跳过 LLM 工具调用,降低延迟与成本。

设计约束(详见 docs/specs/2026-07-31-agent-harness-design.md §5.0):
- 短语集封闭(~20 个),不堆业务关键词
- 严禁把"重试/继续/不对"等上下文短输入识别为寒暄,
  那些交给 LLM + chat history 处理(缺陷 #8 的修复)
- 当输入含写动作词时,不识别为寒暄,交给 RuleIntentClassifier 写意图识别
- 当输入含强业务查询词时,不识别为寒暄,交给全量注入
"""

from __future__ import annotations

import re

_GREETING_PATTERNS = re.compile(
    r"^(你好|您好|在吗|在不在|嗨|hi|hello|hey|早上好|晚上好|下午好|"
    r"谢谢|谢谢你|谢谢啦|辛苦了|辛苦啦|你是谁|你叫什么|介绍一下自己)"
    r"(呀|啊|哈|哇)?[\s!！.。?？～~]*$",
    re.IGNORECASE,
)

_GREETING_PREFIXES = (
    "你好",
    "您好",
    "hi",
    "hello",
    "hey",
    "nihao",
    "ni hao",
)

_CHITCHAT_KEYWORDS = (
    "随便聊",
    "闲聊",
    "聊聊",
    "安排点啥",
    "安排什么",
    "啥活",
    "什么活",
    "建议安排",
    "适合干",
)

# 教程/解释类问句开头词,明确非业务信号。
# 注意:这里是子串匹配,"检查" 会匹配 "帮我检查代码" — 这是有意的,
# 这类输入属于"非业务",应走 no_tools 兜底。
_TUTORIAL_PREFIXES = (
    "为什么",
    "如何",
    "检查",
    "排查",
    "审查",
)

# 强业务查询意图词,出现这些词时不识别为寒暄,交给全量注入让 LLM 自选。
# 刻意不含"什么/看看/查一下"等泛词 — 它们容易 substring 误匹配
# (例:"排查一下这个问题" 含 "查一下" 子串)。
_STRONG_QUERY_KEYWORDS = (
    "查询",
    "查一下账",
    "统计",
    "汇总",
    "列表",
    "明细",
    "多少",
    "最近",
    "余额",
    "账务",
    "财务",
    "成本",
    "利润",
    "欠款",
    "茬口",
    "工人",
    "作业",
    "农事",
    "天气",
    "农场",
)

_WRITE_ACTION_HINTS = (
    "买",
    "卖",
    "采购",
    "购入",
    "销售",
    "新增",
    "添加",
    "创建",
    "记录",
    "记一笔",
    "删除",
    "删掉",
    "修改",
    "更新",
    "安排",
    "支付",
    "结算",
)


class ChitchatClassifier:
    """封闭短语集识别寒暄/教程类无工具输入。

    纯函数实现,无状态,线程安全。
    """

    def is_chitchat(self, message: str) -> bool:
        """判断输入是否为寒暄/教程类无需工具的对话。

        returns:
            True  - 寒暄/教程类,应走 fallback no_tools 分支
            False - 业务输入或写意图,继续走 RuleIntentClassifier + RouterPolicy
        """
        stripped = message.strip()
        if not stripped:
            return True
        if _GREETING_PATTERNS.match(stripped):
            return True

        normalized = stripped.lower()

        # 写动作词存在时,不识别为寒暄 — 交给 RuleIntentClassifier 识别写意图
        if _has_any(normalized, _WRITE_ACTION_HINTS):
            return False

        # "怎么 X" 但不是 "怎么样" → 教程问句
        if "怎么" in normalized and "怎么样" not in normalized:
            return True

        if normalized.startswith(_GREETING_PREFIXES):
            return True

        # 教程/解释类明确信号
        if _has_any(normalized, _TUTORIAL_PREFIXES):
            return True

        # 强业务查询意图词 → 不识别为寒暄,交给全量注入
        if _has_any(normalized, _STRONG_QUERY_KEYWORDS):
            return False

        # 其他寒暄短语
        return _has_any(normalized, _CHITCHAT_KEYWORDS)


def _has_any(message: str, hints: tuple[str, ...]) -> bool:
    return any(hint in message for hint in hints)


__all__ = ["ChitchatClassifier"]
