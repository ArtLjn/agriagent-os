"""日志配置测试。"""

import json
import logging
from io import StringIO

from app.shared.logging import JsonLineFormatter, log_event, setup_logging


def test_setup_logging_suppresses_watchfiles_info_noise():
    """watchfiles 的 reload 变更提示不应污染业务控制台日志。"""
    setup_logging()

    assert logging.getLogger("watchfiles").level >= logging.WARNING
    assert logging.getLogger("watchfiles.main").level >= logging.WARNING


def test_setup_logging_reenables_project_loggers_disabled_by_alembic():
    """Alembic fileConfig 可能禁用已导入业务 logger，重建日志时应恢复。"""
    agent_logger = logging.getLogger("app.shared.llm")
    agent_logger.disabled = True

    setup_logging()

    assert agent_logger.disabled is False


def test_log_event_outputs_stable_key_value_fields(caplog):
    """结构化人读日志应输出稳定 event/code/status 字段并压平成单行。"""
    logger = logging.getLogger("tests.structured")

    with caplog.at_level(logging.WARNING, logger="tests.structured"):
        log_event(
            logger,
            logging.WARNING,
            "pending_plan_contract_blocked",
            code="pending_plan_contract_blocked",
            step_id="pending-plan-contract-1",
            status="blocked",
            data={
                "tool": "manage_workers",
                "missing_fields": ["name"],
                "message": "第一行\n第二行",
            },
        )

    assert len(caplog.records) == 1
    message = caplog.records[0].getMessage()
    assert message.startswith("event=pending_plan_contract_blocked")
    assert "code=pending_plan_contract_blocked" in message
    assert "step_id=pending-plan-contract-1" in message
    assert "status=blocked" in message
    assert "tool=manage_workers" in message
    assert "missing_fields=name" in message
    assert "message=第一行 第二行" in message


def test_json_line_formatter_outputs_single_json_line():
    """JSONL formatter 应输出单行 JSON，并保留 event/code/request_id。"""
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonLineFormatter())
    logger = logging.getLogger("tests.jsonl")
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)

    log_event(
        logger,
        logging.INFO,
        "agent_stream_completed",
        code="ok",
        trace_id="trace-1",
        request_id="req-1",
        step_id="response-output-1",
        status="success",
        duration_ms=123,
        data={"reply_preview": "第一行\n第二行"},
    )

    payload = json.loads(stream.getvalue())
    assert payload["event"] == "agent_stream_completed"
    assert payload["code"] == "ok"
    assert payload["trace_id"] == "trace-1"
    assert payload["request_id"] == "req-1"
    assert payload["step_id"] == "response-output-1"
    assert payload["status"] == "success"
    assert payload["duration_ms"] == 123
    assert payload["data"] == {"reply_preview": "第一行 第二行"}
