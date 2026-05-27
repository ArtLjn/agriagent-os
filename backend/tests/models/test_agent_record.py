"""Tests for AgentRecord 合并模型。"""

from app.models.agent_record import AgentRecord


class TestAgentRecord:
    def test_create_minimal_record(self) -> None:
        """最小化创建：仅必填字段。"""
        record = AgentRecord(
            farm_id=1,
            record_type="chat",
            content="这是一条测试内容",
        )
        assert record.farm_id == 1
        assert record.record_type == "chat"
        assert record.content == "这是一条测试内容"

    def test_create_full_record(self) -> None:
        """完整字段创建。"""
        record = AgentRecord(
            farm_id=2,
            user_id="user-123",
            conversation_id=10,
            cycle_id=5,
            record_type="daily",
            content="每日农事建议",
            meta='{"token_usage": 150, "latency_ms": 200}',
        )
        assert record.farm_id == 2
        assert record.user_id == "user-123"
        assert record.conversation_id == 10
        assert record.cycle_id == 5
        assert record.record_type == "daily"
        assert record.content == "每日农事建议"
        assert record.meta == '{"token_usage": 150, "latency_ms": 200}'

    def test_record_type_variants(self) -> None:
        """record_type 支持 chat / daily / report 等值。"""
        for rt in ("chat", "daily", "report"):
            record = AgentRecord(farm_id=1, record_type=rt, content="x")
            assert record.record_type == rt

    def test_optional_fields_default_none(self) -> None:
        """可选字段默认应为 None。"""
        record = AgentRecord(
            farm_id=1,
            record_type="chat",
            content="test",
        )
        assert record.user_id is None
        assert record.conversation_id is None
        assert record.cycle_id is None
        assert record.meta is None
        assert record.id is None
        assert record.created_at is None

    def test_tablename(self) -> None:
        """确认表名正确。"""
        assert AgentRecord.__tablename__ == "agent_records"
