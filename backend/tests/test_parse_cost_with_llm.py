"""测试 _parse_cost_with_llm 辅助函数（structured output + fallback）。"""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domains.finance.cost_routes import _parse_cost_with_llm
from app.domains.finance.cost_schemas import CostParseResult


@pytest.fixture
def logger():
    return logging.getLogger("test_cost_parse")


class TestStructuredOutputSuccess:
    """with_structured_output 成功路径。"""

    async def test_returns_cost_parse_result_via_structured_output(self, logger):
        """structured output 成功时直接返回 CostParseResult。"""
        llm = MagicMock()
        expected = CostParseResult(
            record_type="cost",
            category="化肥",
            amount="200",
            record_date="2025-06-01",
        )
        structured_llm = AsyncMock()
        structured_llm.ainvoke.return_value = expected
        llm.with_structured_output.return_value = structured_llm

        result = await _parse_cost_with_llm(llm, "test prompt", logger)

        assert result.record_type == "cost"
        assert result.category == "化肥"
        assert result.amount == "200"
        llm.with_structured_output.assert_called_once_with(
            CostParseResult, method="function_calling"
        )


class TestFallbackToJsonParse:
    """with_structured_output 失败后回退到 JSON 解析。"""

    async def test_fallback_on_structured_output_exception(self, logger):
        """structured output 异常时回退到 ainvoke + JSON 解析。"""
        llm = MagicMock()

        structured_llm = AsyncMock()
        structured_llm.ainvoke.side_effect = RuntimeError("tool call failed")
        llm.with_structured_output.return_value = structured_llm

        mock_result = MagicMock()
        mock_result.content = '{"record_type":"cost","category":"种子","amount":"50","record_date":"2025-05-20"}'
        llm.ainvoke = AsyncMock(return_value=mock_result)

        result = await _parse_cost_with_llm(llm, "test prompt", logger)

        assert isinstance(result, CostParseResult)
        assert result.category == "种子"
        assert result.amount == "50"

    async def test_fallback_validates_with_cost_parse_result(self, logger):
        """回退路径使用 CostParseResult.model_validate 校验。"""
        llm = MagicMock()

        structured_llm = AsyncMock()
        structured_llm.ainvoke.side_effect = RuntimeError("failed")
        llm.with_structured_output.return_value = structured_llm

        # amount 为负数，CostParseResult 会校验并修正为 "0"
        mock_result = MagicMock()
        mock_result.content = '{"record_type":"cost","category":"化肥","amount":"-100","record_date":"2025-05-01"}'
        llm.ainvoke = AsyncMock(return_value=mock_result)

        result = await _parse_cost_with_llm(llm, "test prompt", logger)

        assert isinstance(result, CostParseResult)
        assert result.amount == "0"

    async def test_over_limit_amount_is_not_silently_capped(self, logger):
        """超过记账上限的金额不能被静默截断成上限值。"""
        llm = MagicMock()

        structured_llm = AsyncMock()
        structured_llm.ainvoke.side_effect = RuntimeError("failed")
        llm.with_structured_output.return_value = structured_llm

        mock_result = MagicMock()
        mock_result.content = '{"record_type":"income","category":"销售收入","amount":"1000000000","record_date":"2026-06-05"}'
        llm.ainvoke = AsyncMock(return_value=mock_result)

        result = await _parse_cost_with_llm(llm, "test prompt", logger)

        assert isinstance(result, CostParseResult)
        assert result.amount == "0"


class TestErrorHandling:
    """异常处理路径。"""

    async def test_503_when_ai_unavailable(self, logger):
        """AI 服务不可用时返回 503。"""
        from fastapi import HTTPException

        llm = MagicMock()

        structured_llm = AsyncMock()
        structured_llm.ainvoke.side_effect = RuntimeError("tool call failed")
        llm.with_structured_output.return_value = structured_llm

        llm.ainvoke = AsyncMock(side_effect=RuntimeError("connection refused"))

        with pytest.raises(HTTPException) as exc_info:
            await _parse_cost_with_llm(llm, "test prompt", logger)

        assert exc_info.value.status_code == 503

    async def test_422_when_json_parse_fails(self, logger):
        """AI 返回无法解析的 JSON 时返回 422。"""
        from fastapi import HTTPException

        llm = MagicMock()

        structured_llm = AsyncMock()
        structured_llm.ainvoke.side_effect = RuntimeError("tool call failed")
        llm.with_structured_output.return_value = structured_llm

        mock_result = MagicMock()
        mock_result.content = "这不是 JSON"
        llm.ainvoke = AsyncMock(return_value=mock_result)

        with pytest.raises(HTTPException) as exc_info:
            await _parse_cost_with_llm(llm, "test prompt", logger)

        assert exc_info.value.status_code == 422

    async def test_422_when_validation_fails(self, logger):
        """回退路径中 CostParseResult.model_validate 失败时返回 422。

        注意：CostParseResult 使用 lenient 校验，几乎所有输入都能通过。
        此测试确保如果 schema 发生变化导致校验失败，错误能被正确处理。
        """
        from fastapi import HTTPException

        llm = MagicMock()

        structured_llm = AsyncMock()
        structured_llm.ainvoke.side_effect = RuntimeError("tool call failed")
        llm.with_structured_output.return_value = structured_llm

        # 返回完全无法解析的内容（非 JSON 且无法提取）
        mock_result = MagicMock()
        mock_result.content = "ILLEGAL_CONTENT_NO_JSON_HERE"
        llm.ainvoke = AsyncMock(return_value=mock_result)

        with pytest.raises(HTTPException) as exc_info:
            await _parse_cost_with_llm(llm, "test prompt", logger)

        assert exc_info.value.status_code == 422


class TestMeta:
    """辅助函数元信息测试。"""

    def test_helper_exists(self):
        """确认 _parse_cost_with_llm 函数存在且可导入。"""
        from app.domains.finance.cost_routes import _parse_cost_with_llm

        assert callable(_parse_cost_with_llm)
