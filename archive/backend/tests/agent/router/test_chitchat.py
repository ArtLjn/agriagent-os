"""ChitchatClassifier 单元测试。

验证:
- 寒暄/教程类封闭短语集正确识别
- 业务 query 不误识别(避免误杀"查询账务"等)
- 上下文短输入("重试/继续/不对")不识别为寒暄(交给 LLM + chat history)
"""

from __future__ import annotations

import pytest

from app.agent.router.chitchat import ChitchatClassifier

pytestmark = pytest.mark.no_db


@pytest.fixture
def classifier() -> ChitchatClassifier:
    return ChitchatClassifier()


@pytest.mark.parametrize(
    "message",
    [
        "你好",
        "您好",
        "在吗",
        "嗨",
        "hi",
        "hello",
        "hey",
        "早上好",
        "晚上好",
        "谢谢",
        "谢谢你",
        "辛苦了",
        "你是谁",
        "你叫什么",
        "介绍一下自己",
    ],
)
def test_greeting_is_chitchat(classifier: ChitchatClassifier, message: str) -> None:
    assert classifier.is_chitchat(message) is True


@pytest.mark.parametrize(
    "message",
    [
        "为什么",
        "为什么会这样",
        "如何写代码",
        "检查代码",
        "帮我检查代码",
        "排查一下这个问题",
        "审查一下方案",
        "西瓜怎么种",
        "怎么种小麦",
    ],
)
def test_tutorial_or_debug_is_chitchat(
    classifier: ChitchatClassifier, message: str
) -> None:
    assert classifier.is_chitchat(message) is True


@pytest.mark.parametrize(
    "message",
    [
        "查询我的财务",
        "查一下账务",
        "我的财务情况",
        "今天苏州西瓜价格是",
        "农场最近怎么样",
        "今天天气",
        "最近有哪些茬口",
        "还欠多少人工钱",
        "你可以查询哪些",
        "你可以做啥",
        "你的功能是啥",
        "种小麦要注意什么",
        "今天适合做什么",
    ],
)
def test_business_query_is_not_chitchat(
    classifier: ChitchatClassifier, message: str
) -> None:
    """业务 query 不应识别为寒暄,需走全量注入让 LLM 自选。"""
    assert classifier.is_chitchat(message) is False


@pytest.mark.parametrize(
    "message",
    [
        "帮我记账200元",
        "今天卖西瓜收入10w",
        "新建茬口3号棚",
        "删除工人张三",
        "新增成本分类农药",
        "把默认天气城市改成苏州",
    ],
)
def test_write_intent_is_not_chitchat(
    classifier: ChitchatClassifier, message: str
) -> None:
    """写操作 message 含写动作词,不识别为寒暄,交给 RuleIntentClassifier + 写门禁。"""
    assert classifier.is_chitchat(message) is False


@pytest.mark.parametrize(
    "message",
    [
        "重试",
        "继续",
        "不对",
        "不对,是苏州",
        "刚才那个",
        "再来一次",
        "再试一次",
    ],
)
def test_context_short_input_is_not_chitchat(
    classifier: ChitchatClassifier, message: str
) -> None:
    """上下文短输入("重试/继续/不对")严禁识别为寒暄。

    修复缺陷 #8:朴素模式下交给 LLM + chat history 处理,不在 router 层加识别逻辑。
    """
    assert classifier.is_chitchat(message) is False


def test_empty_message_is_chitchat(classifier: ChitchatClassifier) -> None:
    assert classifier.is_chitchat("") is True
    assert classifier.is_chitchat("   ") is True
