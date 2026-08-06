import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from langchain_core.messages import AIMessage, HumanMessage

from app.agent.executor.models import PendingActionDecision
from app.context.task_state.store import AgentTaskStateStore, TaskStateStatus
from app.domains.conversation.models import Conversation, ConversationMessage
from app.infra.pending_actions import remove_pending, store_pending_plan
from app.shared.compatibility import UTC


class TestBuildAdvisorAgent:
    """测试建议 Agent 构建。"""

    @patch("app.agent.runtime.nodes.get_llm")
    def test_build_advisor_agent_returns_loop(self, mock_get_llm: MagicMock) -> None:
        """验证 build_advisor_agent 返回运行 loop。"""
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm

        from app.application.advice.advisor import build_advisor_agent

        result = build_advisor_agent()

        assert result is not None


class TestBuildHistoryMessages:
    """测试 _build_history_messages 辅助函数。"""

    def test_returns_empty_when_no_conversation_id(self) -> None:
        """conversation_id 为 None 时返回空列表。"""
        from app.application.advice.advisor import _build_history_messages

        result = _build_history_messages(MagicMock(), None)

        assert result == []

    def test_returns_empty_when_db_is_none(self) -> None:
        """db 为 None 时返回空列表。"""
        from app.application.advice.advisor import _build_history_messages

        result = _build_history_messages(None, 1)

        assert result == []

    @patch("app.application.advice.advisor.get_recent_messages")
    def test_builds_history_from_db_records(self, mock_get_recent: MagicMock) -> None:
        """验证从数据库记录构建 LangChain 消息列表。"""
        from app.application.advice.advisor import _build_history_messages

        rec_user = MagicMock(role="user", content="你好")
        rec_asst = MagicMock(role="assistant", content="你好！")
        mock_get_recent.return_value = [rec_user, rec_asst]

        mock_db = MagicMock()
        result = _build_history_messages(mock_db, 42)

        assert len(result) == 2
        assert isinstance(result[0], HumanMessage)
        assert result[0].content == "你好"
        assert isinstance(result[1], AIMessage)
        assert result[1].content == "你好！"
        mock_get_recent.assert_called_once_with(mock_db, 42, limit=20)

    @patch("app.application.advice.advisor.get_recent_messages")
    def test_ignores_system_role_records(self, mock_get_recent: MagicMock) -> None:
        """验证 system 角色的记录被忽略。"""
        from app.application.advice.advisor import _build_history_messages

        rec_sys = MagicMock(role="system", content="系统消息")
        mock_get_recent.return_value = [rec_sys]

        mock_db = MagicMock()
        result = _build_history_messages(mock_db, 1)

        assert result == []

    @patch("app.application.advice.advisor.get_recent_messages")
    def test_custom_limit(self, mock_get_recent: MagicMock) -> None:
        """验证自定义 limit 参数传递。"""
        from app.application.advice.advisor import _build_history_messages

        mock_get_recent.return_value = []
        mock_db = MagicMock()

        _build_history_messages(mock_db, 5, limit=50)

        mock_get_recent.assert_called_once_with(mock_db, 5, limit=50)

    @patch("app.application.advice.advisor.get_recent_messages")
    def test_long_history_keeps_summary_and_recent_messages(
        self, mock_get_recent: MagicMock
    ) -> None:
        """长会话历史应摘要早期内容，并完整保留最近消息。"""
        from app.application.advice.advisor import _build_history_messages

        mock_get_recent.return_value = [
            MagicMock(role="user", content="你的功能"),
            MagicMock(
                role="assistant", content="我是芽芽，可以查数据、记账、管理种植。"
            ),
            MagicMock(role="user", content="我的茬口"),
            MagicMock(
                role="assistant", content="活跃茬口有夏季水稻、夏季苹果、夏季玉米。"
            ),
            MagicMock(role="user", content="水稻今天打药了"),
            MagicMock(role="assistant", content="已记录水稻打药。"),
            MagicMock(role="user", content="我想种橘子"),
            MagicMock(role="assistant", content="需要我帮你创建橘子茬口吗？"),
        ]

        result = _build_history_messages(
            MagicMock(),
            42,
            recent_message_limit=2,
        )

        assert len(result) == 3
        assert isinstance(result[0], AIMessage)
        assert "早期对话摘要" in result[0].content
        assert "你的功能" in result[0].content
        assert "夏季水稻" in result[0].content
        assert isinstance(result[1], HumanMessage)
        assert result[1].content == "我想种橘子"

    @patch("app.application.advice.advisor.get_recent_messages")
    def test_current_user_input_removed_before_history_summary(
        self, mock_get_recent: MagicMock
    ) -> None:
        """当前用户输入如果已写入数据库，应先去重再做历史摘要。"""
        from app.application.advice.advisor import _build_history_messages

        mock_get_recent.return_value = [
            MagicMock(role="user", content="你的功能"),
            MagicMock(role="assistant", content="我是芽芽。"),
            MagicMock(role="user", content="第一个问题是"),
        ]

        result = _build_history_messages(
            MagicMock(),
            42,
            current_user_input="第一个问题是",
            recent_message_limit=1,
        )

        assert all(message.content != "第一个问题是" for message in result)

    @pytest.mark.asyncio
    async def test_async_history_prefers_context_pack_recent_messages(
        self,
        db_session,
    ) -> None:
        """Advisor history 应优先使用 ContextPack 的边界后原文窗口。"""
        from app.application.advice.advisor import _async_build_history_messages

        conversation = Conversation(
            farm_id=1,
            user_id="test-user-001",
            session_id="advisor-pack",
            summary="完整新版摘要：用户关注西棚预算。",
        )
        db_session.add(conversation)
        db_session.commit()
        db_session.refresh(conversation)
        messages = []
        for index in range(6):
            message = ConversationMessage(
                conversation_id=conversation.id,
                role="user" if index % 2 == 0 else "assistant",
                content=f"第 {index + 1} 条消息",
            )
            db_session.add(message)
            messages.append(message)
        db_session.commit()
        for message in messages:
            db_session.refresh(message)
        boundary_message = messages[3]
        conversation.meta_json = {
            "context_cursor": {
                "summary_version": 2,
                "summarized_until_message_id": boundary_message.id,
                "summarized_until_created_at": boundary_message.created_at.replace(
                    tzinfo=UTC
                ).isoformat(),
                "summary_hash": "sha256:advisor",
            }
        }
        db_session.commit()

        result = await _async_build_history_messages(
            db_session,
            conversation.id,
            current_user_input="第 5 条消息",
        )

        assert [message.content for message in result] == ["第 6 条消息"]
        assert isinstance(result[0], AIMessage)


class TestAdvisorInvoke:
    """测试建议 Agent 调用。"""

    @patch(
        "app.application.advice.advisor.handle_pending_action",
        new_callable=AsyncMock,
    )
    @patch("app.application.advice.advisor.run_agent_loop", new_callable=AsyncMock)
    def test_invoke_advisor_returns_response(
        self, mock_loop: AsyncMock, mock_pending: AsyncMock
    ) -> None:
        """验证 invoke_advisor 返回 LLM 响应文本。"""
        mock_pending.return_value = PendingActionDecision.unhandled()
        mock_msg = MagicMock()
        mock_msg.content = "建议：今天适合浇水。"
        mock_loop.return_value = {"messages": [mock_msg]}

        from app.application.advice.advisor import invoke_advisor

        result = asyncio.run(invoke_advisor("今天该做什么？", farm_id=1))

        assert result == "建议：今天适合浇水。"
        mock_loop.assert_awaited_once()
        call_args = mock_loop.await_args.args[0]
        assert call_args["farm_id"] == 1

    @patch(
        "app.application.advice.advisor.handle_pending_action",
        new_callable=AsyncMock,
    )
    @patch("app.application.advice.advisor.run_agent_loop", new_callable=AsyncMock)
    def test_invoke_advisor_passes_farm_id(
        self, mock_loop: AsyncMock, mock_pending: AsyncMock
    ) -> None:
        """验证 invoke_advisor 正确传递 farm_id。"""
        mock_pending.return_value = PendingActionDecision.unhandled()
        mock_msg = MagicMock()
        mock_msg.content = "建议内容"
        mock_loop.return_value = {"messages": [mock_msg]}

        from app.application.advice.advisor import invoke_advisor

        result = asyncio.run(invoke_advisor("问题", farm_id=42))

        assert result == "建议内容"
        call_args = mock_loop.await_args.args[0]
        assert call_args["farm_id"] == 42

    @patch(
        "app.application.advice.advisor.handle_pending_action",
        new_callable=AsyncMock,
    )
    @patch("app.application.advice.advisor._async_build_history_messages")
    @patch("app.application.advice.advisor.run_agent_loop", new_callable=AsyncMock)
    def test_invoke_advisor_with_history(
        self,
        mock_loop: AsyncMock,
        mock_build_history: MagicMock,
        mock_pending: AsyncMock,
    ) -> None:
        """验证 invoke_advisor 注入历史消息。"""
        mock_pending.return_value = PendingActionDecision.unhandled()
        mock_msg = MagicMock()
        mock_msg.content = "回复内容"
        mock_loop.return_value = {"messages": [mock_msg]}
        mock_build_history.return_value = [
            HumanMessage(content="之前的问题"),
            AIMessage(content="之前的回复"),
        ]

        mock_db = MagicMock()
        from app.application.advice.advisor import invoke_advisor

        result = asyncio.run(
            invoke_advisor("新问题", farm_id=1, db=mock_db, conversation_id=10)
        )

        assert result == "回复内容"
        call_args = mock_loop.await_args.args[0]
        messages = call_args["messages"]
        # 历史 2 条 + 当前 1 条
        assert len(messages) == 3
        assert isinstance(messages[0], HumanMessage)
        assert messages[0].content == "之前的问题"
        assert isinstance(messages[1], AIMessage)
        assert messages[1].content == "之前的回复"
        assert isinstance(messages[2], HumanMessage)
        assert messages[2].content == "新问题"

    @patch(
        "app.application.advice.advisor.handle_pending_action",
        new_callable=AsyncMock,
    )
    @patch("app.application.advice.advisor.run_agent_loop", new_callable=AsyncMock)
    def test_invoke_advisor_no_history_when_no_db(
        self, mock_loop: AsyncMock, mock_pending: AsyncMock
    ) -> None:
        """验证 db 为 None 时只有当前消息（无历史注入）。"""
        mock_pending.return_value = PendingActionDecision.unhandled()
        mock_msg = MagicMock()
        mock_msg.content = "回复"
        mock_loop.return_value = {"messages": [mock_msg]}

        from app.application.advice.advisor import invoke_advisor

        result = asyncio.run(invoke_advisor("问题", farm_id=1))

        assert result == "回复"
        call_args = mock_loop.await_args.args[0]
        messages = call_args["messages"]
        # 无历史时只有当前消息 1 条
        assert len(messages) == 1
        assert isinstance(messages[0], HumanMessage)
        assert messages[0].content == "问题"

    @patch(
        "app.agent.executor.pending_actions._execute_write_skill",
        new_callable=AsyncMock,
    )
    @patch("app.application.advice.advisor.stream_agent_loop")
    @patch("app.application.advice.advisor.get_collector", create=True)
    @patch("app.application.advice.advisor.run_agent_loop", new_callable=AsyncMock)
    def test_invoke_advisor_pending_confirmation_preempts_task_state_load(
        self,
        mock_loop: AsyncMock,
        mock_get_collector: MagicMock,
        mock_stream_loop: MagicMock,
        mock_execute_skill: AsyncMock,
        db_session,
        monkeypatch,
    ) -> None:
        """真实 pending plan 确认优先于 active task 承接，不进入 runtime。"""
        session_id = "sess-task"
        monkeypatch.setattr(
            "app.infra.pending_actions.SessionLocal",
            lambda: db_session,
            raising=False,
        )
        monkeypatch.setattr(
            "app.agent.executor.pending_actions.SessionLocal",
            lambda: db_session,
            raising=False,
        )
        remove_pending(1, session_id=session_id)
        AgentTaskStateStore(db_session).upsert_active_task(
            farm_id=1,
            user_id="test-user-001",
            session_id=session_id,
            task_type="crop_cycle_setup",
            goal="帮我创建西瓜8424茬口，再新增20亩地",
            entities={
                "crop_name": "西瓜",
                "variety": "8424",
                "area_mu": 20,
            },
            missing_information=[],
            next_action="等待用户确认创建茬口和种植单元",
            status=TaskStateStatus.WAITING_USER,
        )
        store_pending_plan(
            farm_id=1,
            session_id=session_id,
            raw_user_input="帮我创建西瓜8424茬口，再新增20亩地",
            router_decision={"selected_tools": ["manage_crop_cycle"]},
            steps=[
                {
                    "step_id": "create_crop_cycle",
                    "tool_name": "manage_crop_cycle",
                    "params": {
                        "action": "create",
                        "crop_name": "西瓜",
                        "variety": "8424",
                    },
                }
            ],
        )
        mock_execute_skill.return_value = "已创建茬口"

        from app.application.advice.advisor import invoke_advisor

        try:
            result = asyncio.run(
                invoke_advisor(
                    "确认",
                    farm_id=1,
                    db=db_session,
                    session_id=session_id,
                    user_id="test-user-001",
                )
            )
        finally:
            remove_pending(1, session_id=session_id)

        assert "已执行" in result
        assert "已创建茬口" in result
        mock_loop.assert_not_awaited()
        mock_stream_loop.assert_not_called()
        mock_get_collector.assert_not_called()
        mock_execute_skill.assert_awaited_once()

    @patch(
        "app.application.advice.advisor.handle_pending_action",
        new_callable=AsyncMock,
    )
    @patch("app.application.advice.advisor.get_collector", create=True)
    @patch("app.application.advice.advisor.run_agent_loop", new_callable=AsyncMock)
    def test_invoke_advisor_loads_active_task_state_before_agent_loop(
        self,
        mock_loop: AsyncMock,
        mock_get_collector: MagicMock,
        mock_pending: AsyncMock,
        db_session,
    ) -> None:
        """有 db 时，advisor 在进入 runtime 前加载 active task 并评估相关性。"""
        store = AgentTaskStateStore(db_session)
        task = store.upsert_active_task(
            farm_id=1,
            user_id="test-user-001",
            session_id="sess-task",
            task_type="planting_plan",
            goal="帮我规划玉米种植",
            entities={"crop": "玉米"},
            missing_information=["种植面积"],
            next_action="等待用户补充：种植面积",
            status=TaskStateStatus.WAITING_USER,
        )
        mock_pending.return_value = PendingActionDecision.unhandled()
        mock_msg = MagicMock()
        mock_msg.content = "收到，按 20 亩继续。"
        mock_loop.return_value = {"messages": [mock_msg]}
        collector = MagicMock()
        mock_get_collector.return_value = collector

        from app.application.advice.advisor import invoke_advisor

        result = asyncio.run(
            invoke_advisor(
                "20亩",
                farm_id=1,
                db=db_session,
                session_id="sess-task",
                user_id="test-user-001",
            )
        )

        assert result == "收到，按 20 亩继续。"
        initial_state = mock_loop.await_args.args[0]
        assert initial_state["active_task_state"]["task_id"] == task.task_id
        assert initial_state["active_task_state"]["task_type"] == "planting_plan"
        assert initial_state["task_state_relevance"]["should_inject"] is True
        assert initial_state["task_state_relevance"]["decision"] == "inject"
        assert initial_state["task_state_context_should_inject"] is True

        recorded_node_names = [
            call.kwargs["node_name"] for call in collector.record.call_args_list
        ]
        assert "task_state.load" in recorded_node_names
        assert "task_state.relevance" in recorded_node_names
        load_trace = next(
            call.kwargs
            for call in collector.record.call_args_list
            if call.kwargs["node_name"] == "task_state.load"
        )
        assert load_trace["output_data"]["task"] == {
            "task_id": task.task_id,
            "task_type": "planting_plan",
            "status": TaskStateStatus.WAITING_USER,
            "missing_information_count": 1,
            "has_entities": True,
            "has_observations": False,
            "has_next_action": True,
            "expires_at": task.expires_at.isoformat(),
        }
        assert "goal" not in load_trace["output_data"]["task"]
        assert "entities" not in load_trace["output_data"]["task"]

    @patch(
        "app.application.advice.advisor.handle_pending_action",
        new_callable=AsyncMock,
    )
    @patch("app.application.advice.advisor.get_collector", create=True)
    @patch("app.application.advice.advisor.run_agent_loop", new_callable=AsyncMock)
    def test_invoke_advisor_disables_task_state_context_when_irrelevant(
        self,
        mock_loop: AsyncMock,
        mock_get_collector: MagicMock,
        mock_pending: AsyncMock,
        db_session,
    ) -> None:
        """低相关输入不应让旧 TaskState 进入 prompt context。"""
        AgentTaskStateStore(db_session).upsert_active_task(
            farm_id=1,
            user_id="test-user-001",
            session_id="sess-task-weather",
            task_type="planting_plan",
            goal="帮我规划玉米种植",
            entities={"crop": "玉米"},
            missing_information=["种植面积"],
            next_action="等待用户补充：种植面积",
            status=TaskStateStatus.WAITING_USER,
        )
        mock_pending.return_value = PendingActionDecision.unhandled()
        mock_msg = MagicMock()
        mock_msg.content = "今天适合看天气。"
        mock_loop.return_value = {"messages": [mock_msg]}
        mock_get_collector.return_value = MagicMock()

        from app.application.advice.advisor import invoke_advisor

        result = asyncio.run(
            invoke_advisor(
                "天气怎么样？",
                farm_id=1,
                db=db_session,
                session_id="sess-task-weather",
                user_id="test-user-001",
            )
        )

        assert result == "今天适合看天气。"
        initial_state = mock_loop.await_args.args[0]
        assert initial_state["active_task_state"]["task_type"] == "planting_plan"
        assert initial_state["task_state_relevance"]["should_inject"] is False
        assert initial_state["task_state_context_should_inject"] is False
        assert "task_state_routing_input" not in initial_state


class TestAdvisorStream:
    """测试流式 Agent 调用。"""

    @patch(
        "app.application.advice.advisor.handle_pending_action",
        new_callable=AsyncMock,
    )
    @patch("app.application.advice.advisor._async_build_history_messages")
    @patch("app.application.advice.advisor.stream_agent_loop")
    @pytest.mark.asyncio
    async def test_stream_advisor_with_history(
        self,
        mock_stream_loop: MagicMock,
        mock_build_history: MagicMock,
        mock_pending: AsyncMock,
    ) -> None:
        """验证 stream_advisor 注入历史消息。"""
        from app.application.advice.advisor import stream_advisor

        mock_pending.return_value = PendingActionDecision.unhandled()

        async def _fake_astream(*args, **kwargs):
            yield {"llm": {"messages": [AIMessage(content="流式回复")]}}

        mock_stream_loop.side_effect = _fake_astream
        mock_build_history.return_value = [
            HumanMessage(content="历史问题"),
        ]

        mock_db = MagicMock()
        chunks = []
        async for chunk in stream_advisor(
            "新问题", farm_id=1, db=mock_db, conversation_id=5
        ):
            chunks.append(chunk)

        assert len(chunks) >= 1
        mock_build_history.assert_awaited_once_with(
            mock_db,
            5,
            current_user_input="新问题",
        )

    @patch(
        "app.application.advice.advisor.handle_pending_action",
        new_callable=AsyncMock,
    )
    @patch("app.application.advice.advisor.get_collector", create=True)
    @patch("app.application.advice.advisor._async_build_history_messages")
    @patch("app.application.advice.advisor.stream_agent_loop")
    @pytest.mark.asyncio
    async def test_stream_advisor_loads_active_task_state_before_agent_loop(
        self,
        mock_stream_loop: MagicMock,
        mock_build_history: MagicMock,
        mock_get_collector: MagicMock,
        mock_pending: AsyncMock,
        db_session,
    ) -> None:
        """流式入口也应在 runtime 前加载 active task，且 HumanMessage 保持原文。"""
        store = AgentTaskStateStore(db_session)
        task = store.upsert_active_task(
            farm_id=1,
            user_id="test-user-001",
            session_id="sess-stream-task",
            task_type="planting_plan",
            goal="帮我规划玉米种植",
            entities={"crop": "玉米"},
            missing_information=["种植面积"],
            next_action="等待用户补充：种植面积",
            status=TaskStateStatus.WAITING_USER,
        )
        mock_pending.return_value = PendingActionDecision.unhandled()
        mock_build_history.return_value = []
        collector = MagicMock()
        mock_get_collector.return_value = collector
        captured_state = {}

        async def _fake_astream(state, *args, **kwargs):
            captured_state.update(state)
            yield {"llm": {"messages": [AIMessage(content="收到，继续处理。")]}}

        mock_stream_loop.side_effect = _fake_astream

        from app.application.advice.advisor import stream_advisor

        chunks = []
        async for chunk in stream_advisor(
            "20亩",
            farm_id=1,
            db=db_session,
            session_id="sess-stream-task",
            user_id="test-user-001",
        ):
            chunks.append(chunk)

        assert "".join(chunks) == "收到，继续处理。"
        assert captured_state["active_task_state"]["task_id"] == task.task_id
        assert captured_state["active_task_state"]["task_type"] == "planting_plan"
        assert captured_state["task_state_relevance"]["should_inject"] is True
        assert captured_state["task_state_relevance"]["decision"] == "inject"
        assert captured_state["task_state_context_should_inject"] is True
        assert len(captured_state["messages"]) == 1
        assert isinstance(captured_state["messages"][0], HumanMessage)
        assert captured_state["messages"][0].content == "20亩"

        recorded_node_names = [
            call.kwargs["node_name"] for call in collector.record.call_args_list
        ]
        assert "task_state.load" in recorded_node_names
        assert "task_state.relevance" in recorded_node_names
        relevance_trace = next(
            call.kwargs
            for call in collector.record.call_args_list
            if call.kwargs["node_name"] == "task_state.relevance"
        )
        assert relevance_trace["input_data"]["missing_information_count"] == 1
        assert "missing_information" not in relevance_trace["input_data"]
