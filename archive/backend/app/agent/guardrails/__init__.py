"""Agent 安全护栏包。

保留 `app.agent.guardrails` 旧导入路径，真实规则放在 `rules.py`。
"""

from app.agent.guardrails.rules import check_input, cleanup_old_logs, filter_output

__all__ = ["check_input", "filter_output", "cleanup_old_logs"]
