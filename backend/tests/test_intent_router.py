"""测试意图路由 — 问候/查询/写操作分类。"""

import pytest

from app.agent.intent_router import (
    IntentType,
    classify_intent,
    get_greeting_reply,
)


class TestClassifyIntent:
    """测试 classify_intent 函数。"""

    @pytest.mark.parametrize(
        "message",
        ["你好", "在吗", "嗨", "hello", "您好", "谢谢你", "辛苦啦", "你是谁"],
    )
    def test_greeting(self, message: str):
        assert classify_intent(message) == IntentType.GREETING

    @pytest.mark.parametrize(
        "message",
        ["记一笔账", "买了200块化肥", "卖西瓜收入5000", "赊账", "记录浇水"],
    )
    def test_write(self, message: str):
        assert classify_intent(message) == IntentType.WRITE

    @pytest.mark.parametrize(
        "message",
        [
            "上个月花了多少钱",
            "天气预报",
            "成本分析",
            "当前茬口状态",
            "赊账还欠多少",
            "我欠别人多少钱",
            "我还欠多少钱",
            "欠款统计",
        ],
    )
    def test_query(self, message: str):
        assert classify_intent(message) == IntentType.QUERY

    @pytest.mark.parametrize(
        "message",
        ["看看我的账", "农场怎么样", "帮我看看"],
    )
    def test_ambiguous_goes_agent(self, message: str):
        assert classify_intent(message) == IntentType.AGENT

    def test_empty_string(self):
        assert classify_intent("") == IntentType.AGENT


class TestGreetingResponses:
    """测试问候语直接回复。"""

    def test_greeting_reply_is_friendly(self):
        reply = get_greeting_reply("你好")
        assert isinstance(reply, str)
        assert len(reply) > 0
        assert "芽芽" in reply
        assert "茬口" not in reply
        assert "花费" not in reply

    def test_greeting_reply_deterministic(self):
        """同一输入应产生相同的回复。"""
        reply1 = get_greeting_reply("你好")
        reply2 = get_greeting_reply("你好")
        assert reply1 == reply2

    def test_different_inputs_may_differ(self):
        """不同输入可能产生不同回复（不强制，但验证函数逻辑正确）。"""
        reply = get_greeting_reply("hello")
        assert isinstance(reply, str)
        assert len(reply) > 0

    def test_cute_greeting_suffix_is_classified_as_greeting(self):
        """轻松问候不应进入 Agent 主链路触发农场摘要。"""
        assert classify_intent("你好呀") == IntentType.GREETING

    def test_identity_reply_introduces_yaya_without_business_summary(self):
        """问身份时介绍芽芽，不主动输出农场业务摘要。"""
        reply = get_greeting_reply("你是谁")
        assert "芽芽" in reply
        assert "农场管理助手" in reply
        assert "茬口" not in reply
        assert "花费" not in reply

    def test_thanks_reply_has_light_emotional_value(self):
        """感谢类输入给轻松回应，不触发业务汇报。"""
        reply = get_greeting_reply("谢谢你")
        assert "芽芽" in reply
        assert "不客气" in reply or "随时" in reply
        assert "收支" not in reply
