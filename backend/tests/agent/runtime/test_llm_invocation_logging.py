"""Agent Runtime LLM 调用生命周期日志测试。"""

import asyncio
import logging
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import SystemMessage

from app.agent.runtime.llm_invocation import _invoke_llm_with_retry

pytestmark = pytest.mark.no_db


class _SlowLlm:
    model_name = "slow-model"

    async def ainvoke(self, _messages):
        await asyncio.sleep(1)


@pytest.mark.asyncio
async def test_llm_invocation_logs_started_and_timeout(caplog) -> None:
    collector = MagicMock()
    raw_llm = _SlowLlm()

    with (
        patch("app.agent.runtime.llm_invocation._build_circuit_key", return_value="slow/model"),
        patch("app.agent.runtime.llm_invocation._record_llm_failure"),
        patch("app.agent.runtime.llm_invocation._llm_attempt_timeout_seconds", return_value=0.01),
        caplog.at_level(logging.INFO, logger="app.agent.runtime.llm_invocation"),
    ):
        with pytest.raises(TimeoutError):
            await _invoke_llm_with_retry(
                model_role="lightweight",
                raw_llm=raw_llm,
                llm=raw_llm,
                selected_tools=[],
                system=SystemMessage(content="system"),
                messages=[],
                collector=collector,
                input_summary="summary",
                get_llm_func=MagicMock(),
                bind_llm_func=MagicMock(),
                max_retries=1,
            )

    assert "event=llm_call_started" in caplog.text
    assert "event=llm_call_timeout" in caplog.text
    assert "key=slow/model" in caplog.text
    assert "model=slow-model" in caplog.text
    trace_call = collector.record.call_args.kwargs
    assert trace_call["node_type"] == "llm_call"
    assert trace_call["node_name"] == "slow-model"
    assert trace_call["status"] == "timeout"
    assert trace_call["input_data"]["provider"] == "slow"
    assert trace_call["input_data"]["model"] == "slow-model"
    assert trace_call["input_data"]["role"] == "lightweight"
    assert trace_call["input_data"]["tool_choice"] == "none"
    assert trace_call["output_data"]["error"]["code"] == "llm_call_timeout"
