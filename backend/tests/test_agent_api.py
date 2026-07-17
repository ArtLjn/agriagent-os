from datetime import datetime
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestAgentChat:
    """测试 Agent 对话接口。"""

    @patch("app.api.agent.chat")
    def test_chat_endpoint(self, mock_chat) -> None:
        """验证 POST /agent/chat 返回回复。"""
        from app.schemas.agent import ChatResponse

        mock_chat.return_value = ChatResponse(reply="建议：浇水。")

        response = client.post("/agent/chat", json={"message": "今天做什么？"})

        assert response.status_code == 200
        assert response.json()["reply"] == "建议：浇水。"

    @patch("app.api.agent.chat")
    def test_chat_endpoint_passes_session_id(self, mock_chat) -> None:
        """验证 POST /agent/chat 传递 session_id 给 use case。"""
        from app.schemas.agent import ChatResponse

        mock_chat.return_value = ChatResponse(reply="回复")

        response = client.post(
            "/agent/chat",
            json={"message": "你好", "session_id": "sess-abc"},
        )

        assert response.status_code == 200
        mock_chat.assert_called_once()
        chat_request = mock_chat.call_args.args[1]
        assert chat_request.session_id == "sess-abc"

    @patch("app.api.agent.chat")
    def test_chat_endpoint_without_session_id(self, mock_chat) -> None:
        """验证 POST /agent/chat 无 session_id 时传 None。"""
        from app.schemas.agent import ChatResponse

        mock_chat.return_value = ChatResponse(reply="回复")

        response = client.post("/agent/chat", json={"message": "你好"})

        assert response.status_code == 200
        chat_request = mock_chat.call_args.args[1]
        assert chat_request.session_id is None

    async def test_chat_use_case_observes_memory_after_completion(self, db_session):
        """验证聊天完成后提交 Memory observation event。"""
        from app.application.chat_use_case import chat
        from app.agent.executor.models import PendingActionDecision
        from app.models.farm import Farm
        from app.schemas.agent import ChatRequest

        farm = db_session.query(Farm).filter(Farm.id == 1).first()
        memory_service = AsyncMock()

        with (
            patch(
                "app.application.chat_use_case.handle_pending_action",
                new_callable=AsyncMock,
                return_value=PendingActionDecision.unhandled(),
            ),
            patch(
                "app.application.chat_use_case.invoke_advisor",
                new_callable=AsyncMock,
                return_value="建议：今天浇水。",
            ),
            patch(
                "app.application.chat_use_case.get_memory_service",
                return_value=memory_service,
            ),
            patch("app.application.chat_use_case.schedule_session_summary"),
        ):
            response = await chat(
                db_session,
                ChatRequest(message="今天做什么？", session_id="sess-1"),
                farm,
                request_id="req-1",
            )

        assert response.reply == "建议：今天浇水。"
        memory_service.observe_chat_completion.assert_awaited_once_with(
            user_id=farm.user_id,
            farm_id=farm.id,
            session_id="sess-1",
            user_input="今天做什么？",
            assistant_reply="建议：今天浇水。",
            skills_called=[],
            metadata={"request_id": "req-1"},
        )


class TestAgentChatStream:
    """测试流式对话接口。"""

    @patch("app.application.stream_chat_use_case._schedule_stream_background_finalization")
    @patch("app.application.stream_chat_use_case.SessionFlywheelRecorder")
    @patch("app.application.stream_chat_use_case.handle_pending_action")
    @patch("app.application.stream_chat_use_case.stream_advisor")
    def test_stream_endpoint_passes_session_id(
        self,
        mock_stream,
        mock_pending,
        mock_recorder_cls,
        mock_schedule_finalization,
    ) -> None:
        """验证 POST /agent/chat/stream 传递 session_id。"""
        from app.agent.executor.models import PendingActionDecision

        async def _fake_stream(*args, **kwargs):
            yield "chunk1"

        mock_pending.return_value = PendingActionDecision.unhandled()
        mock_stream.side_effect = _fake_stream
        recorder = mock_recorder_cls.return_value
        recorder.start_turn.return_value = object()

        response = client.post(
            "/agent/chat/stream",
            json={"message": "你好", "session_id": "sess-stream"},
        )

        assert response.status_code == 200
        mock_stream.assert_called_once()
        assert mock_stream.call_args.kwargs["session_id"] == "sess-stream"
        mock_schedule_finalization.assert_called_once()


class TestAgentDaily:
    """测试每日建议接口。"""

    @patch("app.application.advice_use_case.get_daily_advice")
    def test_daily_advice_endpoint(self, mock_daily) -> None:
        """验证 GET /agent/daily 返回建议。"""
        from app.schemas.agent import AdviceItem, DailyAdviceResponse

        items = [AdviceItem(title="施肥", detail="追施复合肥", priority=1)]
        mock_daily.return_value = DailyAdviceResponse(
            cycle_id=1, preview="今日有雨", items=items, created_at=datetime.now()
        )

        response = client.get("/agent/daily?cycle_id=1")

        assert response.status_code == 200
        data = response.json()
        assert "施肥" in data["advice"]
        assert data["preview"] == "今日有雨"


class TestAgentReport:
    """测试报告接口。"""

    @patch("app.application.advice_use_case.generate_report")
    def test_report_endpoint(self, mock_report) -> None:
        """验证 POST /agent/report 返回报告。"""
        from app.schemas.agent import ReportResponse

        mock_report.return_value = ReportResponse(
            cycle_id=1,
            report_type="weekly",
            content="周报内容",
            created_at=datetime.now(),
        )

        response = client.post(
            "/agent/report", json={"cycle_id": 1, "report_type": "weekly"}
        )

        assert response.status_code == 200
        assert response.json()["content"] == "周报内容"


class TestAgentHistory:
    """测试历史记录接口。"""

    @patch("app.api.agent.get_advice_history")
    def test_advice_history_endpoint(self, mock_history) -> None:
        """验证 GET /agent/advice-history 返回列表。"""
        mock_history.return_value = []

        response = client.get("/agent/advice-history")

        assert response.status_code == 200
        assert response.json() == []

    @patch("app.application.history_use_case.get_report_history")
    def test_report_history_endpoint(self, mock_history) -> None:
        """验证 GET /agent/report-history 返回列表。"""
        mock_history.return_value = []

        response = client.get("/agent/report-history")

        assert response.status_code == 200
        assert response.json() == []

    def test_conversation_messages_include_pending_action(self, db_session) -> None:
        """历史会话消息应保留 pending_action，前端切回会话后继续显示按钮。"""
        import json

        from app.application.chat_use_case import build_pending_action_response
        from app.application.history_use_case import list_message_items
        from app.models.conversation import Conversation, ConversationMessage
        from app.models.farm import Farm
        from app.infra.pending_actions import remove_pending, store_pending

        farm = db_session.query(Farm).filter(Farm.id == 1).first()
        session_id = "sess-pending-history"
        remove_pending(farm.id, session_id=session_id)
        store_pending(
            farm.id,
            "create_crop_cycle",
            {"crop_name": "橘子"},
            original_input="我想种橘子",
            session_id=session_id,
        )
        pending = build_pending_action_response(farm.id, session_id=session_id)
        conversation = Conversation(
            farm_id=farm.id,
            user_id=farm.user_id,
            session_id=session_id,
        )
        db_session.add(conversation)
        db_session.commit()
        db_session.refresh(conversation)
        db_session.add(
            ConversationMessage(
                conversation_id=conversation.id,
                role="assistant",
                content="需要我帮你创建一个「橘子」茬口吗？",
                meta=json.dumps(
                    {"pending_action": pending.model_dump(mode="json")},
                    ensure_ascii=False,
                ),
            )
        )
        db_session.commit()

        items = list_message_items(db_session, farm=farm, session_id=session_id)

        assert items[0].pending_action is not None
        assert items[0].pending_action.skill_name == "create_crop_cycle"

        remove_pending(farm.id, session_id=session_id)

    def test_conversation_messages_include_pending_plan(self, db_session) -> None:
        """历史会话消息应保留 pending_plan，前端不再只靠文案正则判断。"""
        import json

        from app.application.history_use_case import list_message_items
        from app.models.conversation import Conversation, ConversationMessage
        from app.models.farm import Farm

        farm = db_session.query(Farm).filter(Farm.id == 1).first()
        session_id = "sess-pending-plan-history"
        conversation = Conversation(
            farm_id=farm.id,
            user_id=farm.user_id,
            session_id=session_id,
        )
        db_session.add(conversation)
        db_session.commit()
        db_session.refresh(conversation)
        pending_plan = {
            "plan_id": "plan-1",
            "status": "pending",
            "steps": [{"skill_name": "manage_workers"}],
        }
        db_session.add(
            ConversationMessage(
                conversation_id=conversation.id,
                role="assistant",
                content="请确认将执行 1 步",
                meta=json.dumps({"pending_plan": pending_plan}, ensure_ascii=False),
            )
        )
        db_session.commit()

        items = list_message_items(db_session, farm=farm, session_id=session_id)

        assert items[0].pending_plan is not None
        assert items[0].pending_plan.plan_id == "plan-1"


class TestAgentTraceFilter:
    """验证 trace 查询只查 skill_call 类型。"""

    def test_stream_trace_query_no_routing(self) -> None:
        """验证 event_generator 查询 skills 时不含 routing。"""
        import inspect
        from app.api import agent as agent_module

        source = inspect.getsource(agent_module)
        assert '"routing"' not in source
        assert "routing" not in [w for w in source.split() if w == '"routing"']
