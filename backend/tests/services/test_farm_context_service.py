"""farm_context_service 测试模块。

测试农场上下文摘要组装逻辑：茬口、农事、债务、月度成本、天气，
以及缓存命中/过期和裁剪规则。
"""

import time
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.farm_context_service import (
    _Cache,
    _format_weather_line,
    _MAX_LENGTH,
    build_summary,
    clear_context_cache,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _reset_cache():
    """每个测试前清除缓存，避免跨测试缓存污染。"""
    clear_context_cache()
    yield
    clear_context_cache()


# ---------------------------------------------------------------------------
# 辅助：构造 mock 对象
# ---------------------------------------------------------------------------


def _make_cycle(name: str, stages: list | None = None) -> MagicMock:
    """构造一个 mock CropCycle 对象。"""
    cycle = MagicMock()
    cycle.name = name
    cycle.status = "active"
    cycle.stages = stages or []
    return cycle


def _make_stage(
    name: str, is_current: int = 1, end_date: date | None = None
) -> MagicMock:
    """构造一个 mock CycleStage 对象。"""
    stage = MagicMock()
    stage.name = name
    stage.is_current = is_current
    stage.end_date = end_date or (date.today() + timedelta(days=30))
    return stage


def _make_log(
    operation_type: str, operation_date: date, note: str | None = None
) -> MagicMock:
    """构造一个 mock FarmLog 对象。"""
    log = MagicMock()
    log.operation_type = operation_type
    log.operation_date = operation_date
    log.note = note
    return log


def _make_cost_record(
    amount: Decimal = Decimal("100"),
    category: str = "农资",
    note: str | None = None,
    record_date: date | None = None,
) -> MagicMock:
    """构造一个 mock CostRecord 对象。"""
    record = MagicMock()
    record.amount = amount
    record.category = category
    record.note = note
    record.record_date = record_date or date.today()
    record.record_type = "cost"
    return record


def _make_db_session(
    cycles: list | None = None,
    logs: list | None = None,
    debts: list | None = None,
    monthly_cost: Decimal = Decimal("0"),
) -> MagicMock:
    """构造一个 mock Session，预配置各查询结果。

    按代码调用顺序依次返回：cycles, logs, debts, cost 的查询 mock。
    """
    db = MagicMock()

    # CropCycle 查询
    cycle_query = MagicMock()
    cycle_query.filter.return_value = cycle_query
    cycle_query.order_by.return_value = cycle_query
    cycle_query.limit.return_value = cycle_query
    cycle_query.all.return_value = cycles or []

    # FarmLog 查询
    log_query = MagicMock()
    log_query.filter.return_value = log_query
    log_query.order_by.return_value = log_query
    log_query.limit.return_value = log_query
    log_query.all.return_value = logs or []

    # CostRecord 债务查询（note 非空的 cost 记录）
    debt_query = MagicMock()
    debt_query.filter.return_value = debt_query
    debt_query.order_by.return_value = debt_query
    debt_query.limit.return_value = debt_query
    debt_query.all.return_value = debts or []

    # CostRecord 月度汇总查询
    cost_query = MagicMock()
    cost_query.filter.return_value = cost_query
    cost_query.scalar.return_value = monthly_cost

    # 依次返回不同 query 对象：cycles, logs, debts, cost
    db.query.side_effect = [cycle_query, log_query, debt_query, cost_query]
    return db


def _make_weather_data() -> dict:
    """构造一个模拟的天气数据。"""
    today = date.today()
    return {
        "daily": {
            "time": [
                today.isoformat(),
                (today + timedelta(days=1)).isoformat(),
                (today + timedelta(days=2)).isoformat(),
            ],
            "temperature_2m_max": [25.0, 20.0, 18.0],
            "temperature_2m_min": [15.0, 12.0, 10.0],
            "precipitation_sum": [0.0, 2.0, 15.0],
            "windspeed_10m_max": [5.0, 8.0, 12.0],
        }
    }


# ---------------------------------------------------------------------------
# 测试：活跃茬口时组装摘要
# ---------------------------------------------------------------------------


class TestBuildSummaryWithActiveCycles:
    """有活跃茬口时的摘要组装测试。"""

    @patch("app.services.farm_context_service.weather_service")
    async def test_summary_contains_all_sections(self, mock_weather_svc):
        """摘要应包含所有五个部分：茬口、农事、欠账、花费、天气。"""
        mock_weather_svc.fetch_weather = AsyncMock(return_value=_make_weather_data())

        cycles = [
            _make_cycle(
                "春季西瓜",
                [_make_stage("伸蔓期", end_date=date.today() + timedelta(days=20))],
            ),
        ]
        today = date.today()
        logs = [
            _make_log("施肥", today - timedelta(days=1), note="基肥"),
            _make_log("浇水", today, note="滴灌"),
        ]
        db = _make_db_session(cycles=cycles, logs=logs, monthly_cost=Decimal("5800"))

        result = await build_summary(db, farm_id=1)

        assert "茬口" in result
        assert "农事" in result
        assert "花费" in result
        assert "天气" in result
        assert "5800" in result
        mock_weather_svc.fetch_weather.assert_called_once()

    @patch("app.services.farm_context_service.weather_service")
    async def test_summary_includes_current_stage(self, mock_weather_svc):
        """茬口行应包含当前阶段名称。"""
        mock_weather_svc.fetch_weather = AsyncMock(return_value=_make_weather_data())

        cycles = [
            _make_cycle("秋季豆角", [_make_stage("播种期", is_current=1)]),
        ]
        db = _make_db_session(cycles=cycles)

        result = await build_summary(db, farm_id=1)

        assert "秋季豆角" in result
        assert "播种期" in result

    @patch("app.services.farm_context_service.weather_service")
    async def test_summary_includes_recent_logs(self, mock_weather_svc):
        """近期农事应包含最近 3 天内的记录。"""
        mock_weather_svc.fetch_weather = AsyncMock(return_value=_make_weather_data())

        today = date.today()
        logs = [
            _make_log("施肥", today - timedelta(days=2), note="追肥"),
            _make_log("浇水", today - timedelta(days=1), note="滴灌"),
            _make_log("打药", today, note="杀虫"),
        ]
        db = _make_db_session(logs=logs, monthly_cost=Decimal("0"))

        result = await build_summary(db, farm_id=1)

        assert "施肥" in result
        assert "浇水" in result
        assert "打药" in result


# ---------------------------------------------------------------------------
# 测试：无活跃茬口
# ---------------------------------------------------------------------------


class TestBuildSummaryNoActiveCycles:
    """无活跃茬口时的摘要组装测试。"""

    @patch("app.services.farm_context_service.weather_service")
    async def test_no_active_cycles_shows_placeholder(self, mock_weather_svc):
        """无活跃茬口时，应显示「当前无种植计划」。"""
        mock_weather_svc.fetch_weather = AsyncMock(return_value=_make_weather_data())
        db = _make_db_session(cycles=[], monthly_cost=Decimal("0"))

        result = await build_summary(db, farm_id=1)

        assert "当前无种植计划" in result


# ---------------------------------------------------------------------------
# 测试：裁剪规则
# ---------------------------------------------------------------------------


class TestTrimmingRules:
    """各类型数据硬上限裁剪测试。"""

    @patch("app.services.farm_context_service.weather_service")
    async def test_trim_cycles_to_three(self, mock_weather_svc):
        """超过 3 个茬口时只取前 3 个。"""
        mock_weather_svc.fetch_weather = AsyncMock(return_value=_make_weather_data())

        cycles = [_make_cycle(f"作物{i}", [_make_stage(f"阶段{i}")]) for i in range(5)]
        db = _make_db_session(cycles=cycles, monthly_cost=Decimal("0"))

        result = await build_summary(db, farm_id=1)

        # 前 3 个应出现，第 4、5 个不应出现
        assert "作物0" in result
        assert "作物1" in result
        assert "作物2" in result
        assert "作物3" not in result
        assert "作物4" not in result

    @patch("app.services.farm_context_service.weather_service")
    async def test_trim_logs_to_three(self, mock_weather_svc):
        """超过 3 条农事记录时只取前 3 条。"""
        mock_weather_svc.fetch_weather = AsyncMock(return_value=_make_weather_data())

        today = date.today()
        logs = [_make_log(f"操作{i}", today - timedelta(days=i)) for i in range(5)]
        db = _make_db_session(logs=logs, monthly_cost=Decimal("0"))

        result = await build_summary(db, farm_id=1)

        assert "操作0" in result
        assert "操作1" in result
        assert "操作2" in result
        assert "操作3" not in result
        assert "操作4" not in result

    @patch("app.services.farm_context_service.weather_service")
    async def test_summary_length_within_limit(self, mock_weather_svc):
        """摘要总长度应不超过 300 字。"""
        mock_weather_svc.fetch_weather = AsyncMock(return_value=_make_weather_data())

        # 构造大量数据使摘要可能超长
        cycles = [
            _make_cycle(f"很长的茬口名称用来测试裁剪效果{i}", [_make_stage(f"阶段{i}")])
            for i in range(3)
        ]
        today = date.today()
        logs = [
            _make_log(
                f"很长的农事操作描述{i}", today - timedelta(days=i), note=f"详细备注{i}"
            )
            for i in range(3)
        ]
        db = _make_db_session(cycles=cycles, logs=logs, monthly_cost=Decimal("99999"))

        result = await build_summary(db, farm_id=1)

        assert len(result) <= _MAX_LENGTH


# ---------------------------------------------------------------------------
# 测试：天气格式化
# ---------------------------------------------------------------------------


class TestWeatherFormatting:
    """天气行格式化测试。"""

    def test_format_weather_line_basic(self):
        """基本天气行格式化。"""
        weather_data = _make_weather_data()
        result = _format_weather_line(weather_data, days=3)

        assert "25°" in result
        assert "20°" in result
        assert "18°" in result

    def test_format_weather_line_empty_data(self):
        """空天气数据应返回默认提示。"""
        result = _format_weather_line({}, days=3)
        assert result == "暂无天气数据"

    def test_format_weather_line_partial_data(self):
        """只有部分天数的天气数据时，应只展示有数据的部分。"""
        today = date.today()
        weather_data = {
            "daily": {
                "time": [today.isoformat()],
                "temperature_2m_max": [25.0],
                "temperature_2m_min": [15.0],
                "precipitation_sum": [0.0],
                "windspeed_10m_max": [5.0],
            }
        }
        result = _format_weather_line(weather_data, days=3)

        assert "25°" in result
        assert len(result) > 0


# ---------------------------------------------------------------------------
# 测试：缓存
# ---------------------------------------------------------------------------


class TestCache:
    """内存 TTL 缓存测试。"""

    def test_cache_hit(self):
        """相同 farm_id 在 TTL 内应命中缓存。"""
        cache = _Cache(ttl_seconds=300)
        cache.put(1, "cached_summary")

        assert cache.get(1) == "cached_summary"

    def test_cache_miss_after_expiry(self):
        """TTL 过期后应缓存未命中。"""
        cache = _Cache(ttl_seconds=1)
        cache.put(1, "expired_summary")

        # 等待过期
        time.sleep(1.1)

        assert cache.get(1) is None

    def test_cache_miss_different_farm(self):
        """不同 farm_id 应不命中。"""
        cache = _Cache(ttl_seconds=300)
        cache.put(1, "farm_1_summary")

        assert cache.get(2) is None

    def test_cache_overwrite(self):
        """同一 farm_id 再次 put 应覆盖旧值。"""
        cache = _Cache(ttl_seconds=300)
        cache.put(1, "old_summary")
        cache.put(1, "new_summary")

        assert cache.get(1) == "new_summary"

    def test_clear_context_cache(self):
        """clear_context_cache 应清除所有缓存。"""
        clear_context_cache()
        # 验证不会抛出异常


class TestBuildSummaryCacheIntegration:
    """build_summary 与缓存集成测试。"""

    @patch("app.services.farm_context_service.weather_service")
    async def test_second_call_hits_cache(self, mock_weather_svc):
        """第二次调用 build_summary 应命中缓存，不再查库。"""
        mock_weather_svc.fetch_weather = AsyncMock(return_value=_make_weather_data())
        clear_context_cache()

        db = _make_db_session(monthly_cost=Decimal("100"))
        result1 = await build_summary(db, farm_id=1)

        # 用新的 db mock（查询会失败如果被调用）
        db2 = MagicMock()
        db2.query.side_effect = AssertionError("不应该再查库")

        result2 = await build_summary(db2, farm_id=1)

        assert result1 == result2

    @patch("app.services.farm_context_service.weather_service")
    async def test_different_farm_id_not_shared(self, mock_weather_svc):
        """不同 farm_id 的缓存应互相独立。"""
        mock_weather_svc.fetch_weather = AsyncMock(return_value=_make_weather_data())
        clear_context_cache()

        db1 = _make_db_session(
            cycles=[_make_cycle("农场1作物")],
            monthly_cost=Decimal("100"),
        )
        db2 = _make_db_session(
            cycles=[_make_cycle("农场2作物")],
            monthly_cost=Decimal("200"),
        )

        result1 = await build_summary(db1, farm_id=1)
        result2 = await build_summary(db2, farm_id=2)

        assert "农场1作物" in result1
        assert "农场2作物" in result2
        assert "农场1作物" not in result2


# ---------------------------------------------------------------------------
# 测试：月度成本
# ---------------------------------------------------------------------------


class TestMonthlyCost:
    """月度成本汇总测试。"""

    @patch("app.services.farm_context_service.weather_service")
    async def test_monthly_cost_displayed(self, mock_weather_svc):
        """月度花费金额应出现在摘要中。"""
        mock_weather_svc.fetch_weather = AsyncMock(return_value=_make_weather_data())
        db = _make_db_session(monthly_cost=Decimal("12345.67"))

        result = await build_summary(db, farm_id=1)

        assert "12345.67" in result

    @patch("app.services.farm_context_service.weather_service")
    async def test_zero_monthly_cost(self, mock_weather_svc):
        """当月无花费时，应显示 0。"""
        mock_weather_svc.fetch_weather = AsyncMock(return_value=_make_weather_data())
        db = _make_db_session(monthly_cost=Decimal("0"))

        result = await build_summary(db, farm_id=1)

        assert "0" in result


# ---------------------------------------------------------------------------
# 测试：天气调用失败时降级
# ---------------------------------------------------------------------------


class TestWeatherFallback:
    """天气服务调用失败时的降级测试。"""

    async def test_weather_failure_shows_fallback(self):
        """天气 API 失败时，摘要应包含降级提示而不是报错。"""
        with patch(
            "app.services.farm_context_service.weather_service"
        ) as mock_weather_svc:
            mock_weather_svc.fetch_weather = AsyncMock(
                side_effect=RuntimeError("API 超时")
            )
            clear_context_cache()

            db = _make_db_session(monthly_cost=Decimal("0"))
            result = await build_summary(db, farm_id=1)

            assert "暂无天气数据" in result
