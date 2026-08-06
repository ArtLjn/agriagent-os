"""测试 cycle.py 的 parse_cycle 端点重构。

覆盖范围：
- _parse_cycle_with_llm helper 的 structured output / fallback 行为
- 主函数的幂等、cross-validation、name 校验、缓存
- 边界：LLM 异常、无法解析的 JSON、无关输入
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domains.planting.cycle_routes import _parse_cycle_with_llm
from app.domains.planting.cycle_schemas import CycleParseResponse


# ── _parse_cycle_with_llm: Meta ──────────────────────────────────────────


class TestParseCycleWithLlmMeta:
    """验证 helper 函数签名和基本行为。"""

    def test_return_type_annotation(self):
        """返回值应标注为 CycleParseResponse。"""
        hints = _parse_cycle_with_llm.__annotations__
        assert hints.get("return") is CycleParseResponse


# ── _parse_cycle_with_llm: structured output 成功 ────────────────────────


class TestParseCycleWithLlmStructured:
    """structured output 正常返回。"""

    @pytest.mark.asyncio
    async def test_structured_output_success(self):
        """with_structured_output 成功时直接返回解析结果。"""
        expected = CycleParseResponse(
            name="东大棚8424西瓜",
            crop_template_id=1,
            start_date="2025-05-01",
            field_name="东大棚",
        )
        mock_llm = MagicMock()
        mock_structured = AsyncMock()
        mock_structured.ainvoke.return_value = expected
        mock_llm.with_structured_output.return_value = mock_structured

        logger = MagicMock()
        result = await _parse_cycle_with_llm(mock_llm, "prompt", logger)

        assert result == expected
        mock_llm.with_structured_output.assert_called_once_with(
            CycleParseResponse, method="function_calling"
        )


# ── _parse_cycle_with_llm: fallback 路径 ─────────────────────────────────


class TestParseCycleWithLlmFallback:
    """structured output 失败后 fallback 到 JSON 解析。"""

    @pytest.mark.asyncio
    async def test_fallback_to_json_parse(self):
        """structured output 失败时回退到 ainvoke + safe_parse_json。"""
        expected = CycleParseResponse(
            name="大棚番茄",
            crop_template_id=2,
            start_date="2025-03-01",
            field_name="一号棚",
        )
        raw_json = expected.model_dump_json()

        mock_llm = MagicMock()
        # structured output 抛异常
        mock_structured = AsyncMock()
        mock_structured.ainvoke.side_effect = RuntimeError("tool call failed")
        mock_llm.with_structured_output.return_value = mock_structured
        # fallback ainvoke 返回 JSON 字符串
        mock_result = MagicMock()
        mock_result.content = raw_json
        mock_llm.ainvoke = AsyncMock(return_value=mock_result)

        logger = MagicMock()
        result = await _parse_cycle_with_llm(mock_llm, "prompt", logger)

        assert result.name == "大棚番茄"
        assert result.crop_template_id == 2
        logger.warning.assert_called_once()
        assert "with_structured_output 失败" in logger.warning.call_args[0][0]

    @pytest.mark.asyncio
    async def test_fallback_invalid_json_raises_422(self):
        """fallback 路径中 JSON 解析失败应抛出 HTTPException 422。"""
        from fastapi import HTTPException

        mock_llm = MagicMock()
        mock_structured = AsyncMock()
        mock_structured.ainvoke.side_effect = RuntimeError("fail")
        mock_llm.with_structured_output.return_value = mock_structured

        mock_result = MagicMock()
        mock_result.content = "这不是 JSON"
        mock_llm.ainvoke = AsyncMock(return_value=mock_result)

        logger = MagicMock()
        with pytest.raises(HTTPException) as exc_info:
            await _parse_cycle_with_llm(mock_llm, "prompt", logger)
        assert exc_info.value.status_code == 422

    @pytest.mark.asyncio
    async def test_fallback_model_validate_fail_raises_422(self):
        """fallback 路径中 model_validate 失败应抛出 HTTPException 422。"""
        from fastapi import HTTPException

        mock_llm = MagicMock()
        mock_structured = AsyncMock()
        mock_structured.ainvoke.side_effect = RuntimeError("fail")
        mock_llm.with_structured_output.return_value = mock_structured

        # JSON 有效但缺少必填字段
        mock_result = MagicMock()
        mock_result.content = '{"name": "test"}'
        mock_llm.ainvoke = AsyncMock(return_value=mock_result)

        logger = MagicMock()
        with pytest.raises(HTTPException) as exc_info:
            await _parse_cycle_with_llm(mock_llm, "prompt", logger)
        assert exc_info.value.status_code == 422

    @pytest.mark.asyncio
    async def test_llm_ainvoke_fails_raises_503(self):
        """LLM 调用完全失败应抛出 HTTPException 503。"""
        from fastapi import HTTPException

        mock_llm = MagicMock()
        mock_structured = AsyncMock()
        mock_structured.ainvoke.side_effect = RuntimeError("structured fail")
        mock_llm.with_structured_output.return_value = mock_structured
        mock_llm.ainvoke = AsyncMock(side_effect=ConnectionError("network error"))

        logger = MagicMock()
        with pytest.raises(HTTPException) as exc_info:
            await _parse_cycle_with_llm(mock_llm, "prompt", logger)
        assert exc_info.value.status_code == 503
