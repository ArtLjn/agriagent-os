"""测试写操作确认机制 — pending action 存取、超时、确认/取消/修正流程。"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infra.pending_actions import (
    PendingAction,
    _pending,
    get_pending,
    is_write_skill,
    remove_pending,
    store_pending,
)


class TestPendingActionStorage:
    """测试 pending action 存储与获取。"""

    def setup_method(self):
        """每个测试前清空内存字典。"""
        _pending.clear()

    def test_store_and_get_pending(self):
        """存储后能正确获取。"""
        action_id = store_pending(
            farm_id=1,
            skill_name="create_cost_record",
            params={"amount": 200, "category": "化肥"},
        )

        result = get_pending(farm_id=1)
        assert result is not None
        assert result.action_id == action_id
        assert result.skill_name == "create_cost_record"
        assert result.params == {"amount": 200, "category": "化肥"}
        assert result.farm_id == 1

    def test_get_pending_nonexistent_farm(self):
        """获取不存在的 farm_id 返回 None。"""
        result = get_pending(farm_id=999)
        assert result is None

    def test_remove_pending(self):
        """删除后获取返回 None。"""
        store_pending(farm_id=1, skill_name="create_cost_record", params={})
        remove_pending(farm_id=1)
        assert get_pending(farm_id=1) is None

    def test_remove_pending_nonexistent(self):
        """删除不存在的 farm_id 不报错。"""
        remove_pending(farm_id=999)

    def test_store_overwrites_previous(self):
        """同一 farm_id 再次存储会覆盖。"""
        store_pending(
            farm_id=1, skill_name="create_cost_record", params={"amount": 100}
        )
        store_pending(farm_id=1, skill_name="settle_debt", params={"debt_id": 5})

        result = get_pending(farm_id=1)
        assert result is not None
        assert result.skill_name == "settle_debt"
        assert result.params == {"debt_id": 5}

    def test_different_farms_independent(self):
        """不同 farm_id 的 pending action 互不影响。"""
        store_pending(
            farm_id=1, skill_name="create_cost_record", params={"amount": 100}
        )
        store_pending(
            farm_id=2, skill_name="log_farm_activity", params={"activity": "浇水"}
        )

        result1 = get_pending(farm_id=1)
        result2 = get_pending(farm_id=2)
        assert result1 is not None
        assert result1.skill_name == "create_cost_record"
        assert result2 is not None
        assert result2.skill_name == "log_farm_activity"

    def test_store_returns_uuid_format(self):
        """store_pending 返回有效的唯一标识符。"""
        action_id = store_pending(farm_id=1, skill_name="create_cost_record", params={})
        # uuid4().hex 返回 32 字符的十六进制字符串
        assert len(action_id) == 32
        assert all(c in "0123456789abcdef" for c in action_id)

    def test_store_with_context(self):
        """存储带上下文的 pending action。"""
        store_pending(
            farm_id=1,
            skill_name="create_cost_record",
            params={"amount": 200, "category": "化肥"},
            original_input="昨天买了200块化肥",
        )
        result = get_pending(farm_id=1)
        assert result is not None
        assert result.original_input == "昨天买了200块化肥"


class TestPendingActionTimeout:
    """测试 pending action 超时清理。"""

    def setup_method(self):
        _pending.clear()

    def test_expired_pending_returns_none(self):
        """超时的 pending action 自动清理并返回 None。"""
        _pending[1] = PendingAction(
            action_id="test-id",
            skill_name="create_cost_record",
            params={"amount": 200},
            created_at=time.time() - 600,  # 10分钟前，已超时
            farm_id=1,
        )

        result = get_pending(farm_id=1)
        assert result is None
        assert 1 not in _pending  # 应被删除

    def test_fresh_pending_returns_value(self):
        """未超时的 pending action 正常返回。"""
        _pending[1] = PendingAction(
            action_id="test-id",
            skill_name="create_cost_record",
            params={"amount": 200},
            created_at=time.time() - 60,  # 1分钟前，未超时
            farm_id=1,
        )

        result = get_pending(farm_id=1)
        assert result is not None
        assert result.skill_name == "create_cost_record"


class TestIsWriteSkill:
    """测试写操作 Skill 判断。"""

    @pytest.mark.parametrize(
        "skill_name,expected",
        [
            ("create_cost_record", True),
            ("create_crop_cycle", True),
            ("log_farm_activity", True),
            ("settle_debt", True),
            ("update_crop_stage", True),
            ("get_cost_summary", False),
            ("weather", False),
            ("crop_cycle", False),
            ("farm_logs", False),
            ("cost_analytics", False),
            ("unknown_skill", False),
        ],
    )
    def test_write_skill_detection(self, skill_name: str, expected: bool):
        """验证各 Skill 名称的写/读分类。"""
        assert is_write_skill(skill_name) is expected


class TestConfirmationFlow:
    """测试确认流程 — 确认/取消/修正。"""

    def setup_method(self):
        _pending.clear()

    @pytest.mark.asyncio
    @patch("app.services.agent_service.invoke_advisor", new_callable=AsyncMock)
    async def test_user_confirms_executes_action(self, mock_invoke: AsyncMock):
        """用户说"确认"时执行 pending action 并返回结果。"""
        from app.services.agent_service import chat_with_agent

        # 先存储一个 pending action
        store_pending(
            farm_id=1,
            skill_name="create_cost_record",
            params={"amount": 200, "category": "化肥"},
        )

        mock_db = MagicMock()
        mock_invoke.return_value = "已记录：化肥 200元"

        result = await chat_with_agent(mock_db, "确认", farm_id=1)

        # pending action 应已被删除
        assert get_pending(farm_id=1) is None
        # 结果应包含执行信息
        assert result.pending_action is None

    @pytest.mark.asyncio
    async def test_user_cancels_removes_action(self):
        """用户说"算了"时删除 pending action 并返回取消消息。"""
        from app.services.agent_service import chat_with_agent

        store_pending(
            farm_id=1, skill_name="create_cost_record", params={"amount": 200}
        )

        mock_db = MagicMock()

        with patch("app.services.agent_service.invoke_advisor", new_callable=AsyncMock):
            result = await chat_with_agent(mock_db, "算了", farm_id=1)

        # pending action 应已被删除
        assert get_pending(farm_id=1) is None
        # 回复包含取消信息
        assert "取消" in result.reply

    @pytest.mark.asyncio
    @patch("app.services.agent_service.invoke_advisor", new_callable=AsyncMock)
    async def test_user_modification_goes_to_llm(self, mock_invoke: AsyncMock):
        """用户修正参数（非确认非取消）时交给 LLM 处理。"""
        from app.services.agent_service import chat_with_agent

        store_pending(
            farm_id=1,
            skill_name="create_cost_record",
            params={"amount": 200, "category": "化肥"},
        )

        mock_db = MagicMock()
        mock_invoke.return_value = (
            "好的，已修正为赊账。请确认：化肥 200元，赊账。确认？"
        )

        result = await chat_with_agent(mock_db, "是赊账，农资店老王那", farm_id=1)

        # 应调用 LLM（不是直接执行）
        mock_invoke.assert_called_once()
        assert result.reply is not None

    @pytest.mark.asyncio
    @patch("app.services.agent_service.invoke_advisor", new_callable=AsyncMock)
    async def test_no_pending_action_goes_to_llm(self, mock_invoke: AsyncMock):
        """没有 pending action 时正常交给 LLM。"""
        from app.services.agent_service import chat_with_agent

        mock_db = MagicMock()
        mock_invoke.return_value = "你想记录什么支出？"

        result = await chat_with_agent(mock_db, "昨天买了200块化肥", farm_id=1)

        mock_invoke.assert_called_once()
        assert result.reply == "你想记录什么支出？"

    @pytest.mark.asyncio
    @patch("app.services.agent_service.invoke_advisor", new_callable=AsyncMock)
    async def test_expired_pending_goes_to_llm(self, mock_invoke: AsyncMock):
        """pending action 已超时时，按正常对话处理。"""
        from app.services.agent_service import chat_with_agent

        _pending[1] = PendingAction(
            action_id="test-id",
            skill_name="create_cost_record",
            params={"amount": 200},
            created_at=time.time() - 600,  # 已超时
            farm_id=1,
        )

        mock_db = MagicMock()
        mock_invoke.return_value = "抱歉，操作已超时。"

        await chat_with_agent(mock_db, "确认", farm_id=1)

        mock_invoke.assert_called_once()


class TestConfirmIntentDetection:
    """测试用户意图识别 — 确认词、取消词。"""

    def setup_method(self):
        _pending.clear()

    @pytest.mark.parametrize(
        "message,expected_intent",
        [
            ("确认", "confirm"),
            ("好的", "confirm"),
            ("是的", "confirm"),
            ("没问题", "confirm"),
            ("对", "confirm"),
            ("确认一下", "confirm"),
            ("好的，就这样", "confirm"),
            ("算了", "cancel"),
            ("取消", "cancel"),
            ("不要了", "cancel"),
            ("不需要了", "cancel"),
            ("取消吧", "cancel"),
            ("是赊账", "modify"),
            ("不对，是300元", "modify"),
            ("今天天气怎么样", "modify"),
            ("帮我查一下成本", "modify"),
        ],
    )
    def test_intent_detection(self, message: str, expected_intent: str):
        """验证各类消息的意图识别。"""
        from app.infra.pending_actions import detect_user_intent

        result = detect_user_intent(message)
        assert result == expected_intent


class TestGraphToolNodeIntegration:
    """测试 graph.py 中写操作 Skill 拦截。"""

    def setup_method(self):
        _pending.clear()

    @pytest.mark.asyncio
    async def test_write_skill_intercepted(self):
        """写操作 Skill 应被拦截，不直接执行。"""
        from app.agent.graph import _parallel_tool_node
        from langchain_core.messages import AIMessage

        ai_msg = AIMessage(
            content="",
            tool_calls=[
                {
                    "id": "tc1",
                    "name": "create_cost_record",
                    "args": {"amount": 200, "category": "化肥"},
                },
            ],
        )
        state = {"messages": [ai_msg]}

        result = await _parallel_tool_node(state)
        tool_msg = result["messages"][0]

        # 应存储为 pending action
        pending = get_pending(farm_id=1)
        assert pending is not None
        assert pending.skill_name == "create_cost_record"
        assert pending.params == {"amount": 200, "category": "化肥"}

        # ToolMessage 应包含确认提示
        assert "确认" in tool_msg.content or "记录" in tool_msg.content

    @pytest.mark.asyncio
    async def test_read_skill_executed_directly(self):
        """只读 Skill 应直接执行，不拦截。"""
        from app.agent.graph import _parallel_tool_node
        from langchain_core.messages import AIMessage

        ai_msg = AIMessage(
            content="",
            tool_calls=[
                {"id": "tc1", "name": "get_cost_summary", "args": {"period": "month"}},
            ],
        )
        state = {"messages": [ai_msg]}

        with patch("app.agent.runtime.tool_executor.get_langchain_tools") as mock_tools:
            mock_tool = MagicMock()
            mock_tool.name = "get_cost_summary"
            mock_tool.ainvoke = AsyncMock(return_value="本月支出：2000元")
            mock_tools.return_value = [mock_tool]

            await _parallel_tool_node(state)

        # 不应存储 pending action
        assert get_pending(farm_id=1) is None


class TestBuildConfirmMessageFormat:
    """测试 build_confirm_message 的 emoji + 可读格式。"""

    @pytest.mark.parametrize(
        "skill_name,params,expected_parts",
        [
            (
                "create_cost_record",
                {"amount": 50, "category": "化肥", "record_type": "cost"},
                ["💰", "化肥", "50元", "支出"],
            ),
            (
                "create_crop_cycle",
                {"crop_name": "西瓜", "season": "春季"},
                ["🌱", "西瓜", "春季"],
            ),
            (
                "create_crop_template",
                {"crop_name": "玉米"},
                ["📋", "玉米"],
            ),
            (
                "log_farm_activity",
                {"operation_type": "浇水"},
                ["📝", "浇水"],
            ),
            (
                "settle_debt",
                {"counterparty": "老王", "amount": 500},
                ["💳", "老王", "500元"],
            ),
            (
                "update_crop_stage",
                {"stage_name": "开花期"},
                ["🔄", "开花期"],
            ),
        ],
    )
    def test_confirm_message_has_emoji_and_readable_params(
        self, skill_name, params, expected_parts
    ):
        """确认文案包含 emoji 和可读参数。"""
        from app.infra.pending_actions import build_confirm_message

        msg = build_confirm_message(skill_name, params)
        for part in expected_parts:
            assert part in msg, f"expected '{part}' in '{msg}'"

    def test_confirm_message_ends_with_question(self):
        """确认文案以问号结尾。"""
        from app.infra.pending_actions import build_confirm_message

        msg = build_confirm_message(
            "create_cost_record",
            {"amount": 50, "category": "化肥", "record_type": "cost"},
        )
        assert msg.rstrip("。").endswith("确认吗？") or msg.endswith("？")

    def test_unknown_skill_uses_default_format(self):
        """未知 skill 使用默认格式。"""
        from app.infra.pending_actions import build_confirm_message

        msg = build_confirm_message("unknown_skill", {"foo": "bar"})
        assert "确认" in msg

    def test_confirm_message_with_context(self):
        """三层确认消息包含理解/参数/操作。"""
        from app.infra.pending_actions import build_confirm_message

        msg = build_confirm_message(
            "create_cost_record",
            {"amount": 200, "category": "化肥", "record_type": "cost"},
            original_input="昨天买了200块化肥",
        )
        assert "理解" in msg
        assert "昨天买了200块化肥" in msg
        assert "参数" in msg
        assert "200" in msg
        assert "化肥" in msg
