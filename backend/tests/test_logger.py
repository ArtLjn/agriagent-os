"""日志配置测试。"""

import logging

from app.core.logger import setup_logging


def test_setup_logging_suppresses_watchfiles_info_noise():
    """watchfiles 的 reload 变更提示不应污染业务控制台日志。"""
    setup_logging()

    assert logging.getLogger("watchfiles").level >= logging.WARNING
    assert logging.getLogger("watchfiles.main").level >= logging.WARNING


def test_setup_logging_reenables_project_loggers_disabled_by_alembic():
    """Alembic fileConfig 可能禁用已导入业务 logger，重建日志时应恢复。"""
    agent_logger = logging.getLogger("app.agent.llm")
    agent_logger.disabled = True

    setup_logging()

    assert agent_logger.disabled is False
