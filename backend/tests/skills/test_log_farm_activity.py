"""农事日志聚合 Skill 单元测试。"""

import importlib
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from skillify.core.context import SkillContext

_mod = importlib.import_module("app.skills.manage-farm-logs.scripts.main")
ManageFarmLogsSkill = _mod.ManageFarmLogsSkill


@pytest.fixture
def ctx():
    return SkillContext(farm_id=1)


def _make_active_cycle(cycle_id=1, name="春季西瓜", status="active") -> MagicMock:
    """构造模拟的活跃 CropCycle 对象。"""
    cycle = MagicMock()
    cycle.id = cycle_id
    cycle.name = name
    cycle.status = status
    return cycle


def _make_farm_log(
    log_id=1,
    cycle_id=1,
    operation_type="浇水",
    operation_date=None,
    note=None,
) -> MagicMock:
    """构造模拟的 FarmLog 对象。"""
    log = MagicMock()
    log.id = log_id
    log.cycle_id = cycle_id
    log.operation_type = operation_type
    log.operation_date = operation_date or date(2026, 5, 26)
    log.note = note
    return log


# ── 元信息测试 ──────────────────────────────────────────────────


class TestManageFarmLogsMeta:
    """Skill 元信息测试。"""

    def test_name(self):
        skill = ManageFarmLogsSkill()
        assert skill.name() == "manage_farm_logs"

    def test_description_contains_trigger_words(self):
        skill = ManageFarmLogsSkill()
        desc = skill.description()
        assert "浇水" in desc
        assert "施肥" in desc
        assert "打药" in desc
        assert "农事" in desc
        assert "查询" in desc
        assert "删除" in desc

    def test_parameters_schema_required_fields(self):
        skill = ManageFarmLogsSkill()
        schema = skill.parameters_schema()
        assert "operation" in schema["properties"]
        assert schema["properties"]["operation"]["enum"] == [
            "create_log",
            "query_logs",
            "manage_log",
        ]
        assert "operation_type" in schema["properties"]
        assert "operation_date" in schema["properties"]
        assert "note" in schema["properties"]
        assert "cycle_id" in schema["properties"]
        assert set(schema["required"]) == {"operation"}


# ── 正常场景 ──────────────────────────────────────────────────


class TestLogFarmActivityNormal:
    """正常记农事场景。"""

    @pytest.mark.asyncio
    @patch.object(_mod, "SessionLocal")
    @patch.object(_mod, "log_service")
    async def test_basic_log_with_cycle_id(self, mock_log_svc, mock_session, ctx):
        """指定 cycle_id 时直接记录农事。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        farm_log = _make_farm_log(
            operation_type="浇水",
            operation_date=date(2026, 5, 26),
            cycle_id=5,
        )
        mock_log_svc.create_log.return_value = farm_log

        skill = ManageFarmLogsSkill()
        result = await skill.execute(
            {
                "operation": "create_log",
                "operation_type": "浇水",
                "operation_date": "2026-05-26",
                "cycle_id": 5,
            },
            ctx,
        )

        assert result.status.value == "success"
        assert "浇水" in result.reply
        mock_db.close.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(_mod, "SessionLocal")
    @patch.object(_mod, "log_service")
    async def test_auto_associate_first_active_cycle(
        self, mock_log_svc, mock_session, ctx
    ):
        """不传 cycle_id 时自动关联第一个活跃茬口。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        active_cycle = _make_active_cycle(cycle_id=3, name="春季西瓜")
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = active_cycle

        farm_log = _make_farm_log(
            operation_type="施肥",
            cycle_id=3,
        )
        mock_log_svc.create_log.return_value = farm_log

        skill = ManageFarmLogsSkill()
        result = await skill.execute(
            {"operation": "create_log", "operation_type": "施肥"},
            ctx,
        )

        assert result.status.value == "success"
        assert "施肥" in result.reply
        # 验证 create_log 被调用时 cycle_id=3
        call_args = mock_log_svc.create_log.call_args
        log_create = call_args[0][1]
        assert log_create.cycle_id == 3

    @pytest.mark.asyncio
    @patch.object(_mod, "SessionLocal")
    @patch.object(_mod, "log_service")
    async def test_default_date_is_today(self, mock_log_svc, mock_session, ctx):
        """不传 operation_date 时默认今天。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        farm_log = _make_farm_log(operation_date=date.today())
        mock_log_svc.create_log.return_value = farm_log

        skill = ManageFarmLogsSkill()
        result = await skill.execute(
            {"operation": "create_log", "operation_type": "浇水", "cycle_id": 1},
            ctx,
        )

        assert result.status.value == "success"
        call_args = mock_log_svc.create_log.call_args
        log_create = call_args[0][1]
        assert log_create.operation_date == date.today()

    @pytest.mark.asyncio
    @patch.object(_mod, "SessionLocal")
    @patch.object(_mod, "log_service")
    async def test_explicit_date(self, mock_log_svc, mock_session, ctx):
        """指定 operation_date 时使用指定日期。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        farm_log = _make_farm_log(operation_date=date(2026, 6, 1))
        mock_log_svc.create_log.return_value = farm_log

        skill = ManageFarmLogsSkill()
        result = await skill.execute(
            {
                "operation": "create_log",
                "operation_type": "打药",
                "operation_date": "2026-06-01",
                "cycle_id": 1,
            },
            ctx,
        )

        assert result.status.value == "success"
        call_args = mock_log_svc.create_log.call_args
        log_create = call_args[0][1]
        assert log_create.operation_date == date(2026, 6, 1)

    @pytest.mark.asyncio
    @patch.object(_mod, "SessionLocal")
    @patch.object(_mod, "log_service")
    async def test_with_note(self, mock_log_svc, mock_session, ctx):
        """带备注信息时正确传递。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        farm_log = _make_farm_log(note="追施复合肥 10kg")
        mock_log_svc.create_log.return_value = farm_log

        skill = ManageFarmLogsSkill()
        result = await skill.execute(
            {
                "operation": "create_log",
                "operation_type": "施肥",
                "cycle_id": 1,
                "note": "追施复合肥 10kg",
            },
            ctx,
        )

        assert result.status.value == "success"
        call_args = mock_log_svc.create_log.call_args
        log_create = call_args[0][1]
        assert log_create.note == "追施复合肥 10kg"

    @pytest.mark.asyncio
    @patch.object(_mod, "SessionLocal")
    @patch.object(_mod, "log_service")
    async def test_uses_context_farm_id(self, mock_log_svc, mock_session, ctx):
        """使用 context 中的 farm_id。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        farm_log = _make_farm_log()
        mock_log_svc.create_log.return_value = farm_log

        skill = ManageFarmLogsSkill()
        await skill.execute(
            {"operation": "create_log", "operation_type": "浇水", "cycle_id": 1},
            ctx,
        )

        call_args = mock_log_svc.create_log.call_args
        farm_id = call_args[1].get("farm_id") or call_args[0][2]
        assert farm_id == 1


# ── 无活跃茬口场景 ──────────────────────────────────────────────────


class TestLogFarmActivityNoCycle:
    """无活跃茬口时的处理。"""

    @pytest.mark.asyncio
    @patch.object(_mod, "SessionLocal")
    async def test_no_active_cycle_returns_need_clarify(self, mock_session, ctx):
        """无活跃茬口时返回 need_clarify 提示。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        # 查询返回 None（无活跃茬口）
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        skill = ManageFarmLogsSkill()
        result = await skill.execute(
            {"operation": "create_log", "operation_type": "浇水"},
            ctx,
        )

        assert result.status.value == "need_clarify"
        assert "茬口" in result.reply
        mock_db.close.assert_called_once()


# ── 异常与边界场景 ──────────────────────────────────────────────────


class TestLogFarmActivityError:
    """异常与边界场景。"""

    @pytest.mark.asyncio
    async def test_missing_operation_type(self, ctx):
        """缺少 operation_type 时返回错误。"""
        skill = ManageFarmLogsSkill()
        result = await skill.execute({"operation": "create_log"}, ctx)

        assert result.status.value == "failed"
        assert "操作类型" in result.reply

    @pytest.mark.asyncio
    @patch.object(_mod, "SessionLocal")
    @patch.object(_mod, "log_service")
    async def test_empty_operation_type(self, mock_log_svc, mock_session, ctx):
        """operation_type 为空字符串时返回错误。"""
        skill = ManageFarmLogsSkill()
        result = await skill.execute(
            {"operation": "create_log", "operation_type": ""}, ctx
        )

        assert result.status.value == "failed"
        assert "操作类型" in result.reply

    @pytest.mark.asyncio
    @patch.object(_mod, "SessionLocal")
    @patch.object(_mod, "log_service")
    async def test_invalid_date_falls_back_to_today(
        self, mock_log_svc, mock_session, ctx
    ):
        """无效日期格式回退到今天。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        farm_log = _make_farm_log(operation_date=date.today())
        mock_log_svc.create_log.return_value = farm_log

        skill = ManageFarmLogsSkill()
        await skill.execute(
            {
                "operation": "create_log",
                "operation_type": "浇水",
                "cycle_id": 1,
                "operation_date": "不是日期",
            },
            ctx,
        )

        call_args = mock_log_svc.create_log.call_args
        log_create = call_args[0][1]
        assert log_create.operation_date == date.today()

    @pytest.mark.asyncio
    @patch.object(_mod, "SessionLocal")
    @patch.object(_mod, "log_service")
    async def test_db_error_returns_failure(self, mock_log_svc, mock_session, ctx):
        """数据库异常时返回失败并关闭连接。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        mock_log_svc.create_log.side_effect = Exception("DB error")

        skill = ManageFarmLogsSkill()
        result = await skill.execute(
            {"operation": "create_log", "operation_type": "浇水", "cycle_id": 1},
            ctx,
        )

        assert result.status.value == "failed"
        assert "失败" in result.reply
        mock_db.close.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(_mod, "SessionLocal")
    @patch.object(_mod, "log_service")
    async def test_missing_context_farm_id_fails_without_db_access(
        self, mock_log_svc, mock_session, ctx
    ):
        """context 无 farm_id 时必须失败，不能默认写到 1 号农场。"""
        empty_ctx = SkillContext()

        skill = ManageFarmLogsSkill()
        result = await skill.execute(
            {"operation": "create_log", "operation_type": "浇水", "cycle_id": 1},
            empty_ctx,
        )

        assert result.status.value == "failed"
        assert "农场上下文" in result.reply
        mock_session.assert_not_called()
        mock_log_svc.create_log.assert_not_called()

    @pytest.mark.asyncio
    @patch.object(_mod, "SessionLocal")
    @patch.object(_mod, "log_service")
    async def test_db_close_called_on_success(self, mock_log_svc, mock_session, ctx):
        """成功时也关闭数据库连接。"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        farm_log = _make_farm_log()
        mock_log_svc.create_log.return_value = farm_log

        skill = ManageFarmLogsSkill()
        await skill.execute(
            {"operation": "create_log", "operation_type": "浇水", "cycle_id": 1},
            ctx,
        )

        mock_db.close.assert_called_once()
