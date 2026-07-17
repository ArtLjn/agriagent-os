"""Data Flywheel judge service 兼容入口。

真实实现已迁到 ``app.platforms.shared.judge_service``。
"""

from app.platforms.shared.judge_service import (
    ALLOWED_JUDGE_LABELS,
    ALLOWED_SEVERITIES,
    DEBUG_EXPORT_REQUEST_ID_LIMIT,
    DEFAULT_PROMPT_VERSION,
    JUDGE_SYSTEM_PROMPT,
    LABEL_DEFINITIONS,
    LABEL_SELECTION_RULES,
    DataFlywheelJudgeClient,
    OpenAIDataFlywheelJudgeClient,
    build_judge_input,
    normalize_judge_output,
)

__all__ = [
    "ALLOWED_JUDGE_LABELS",
    "ALLOWED_SEVERITIES",
    "DEBUG_EXPORT_REQUEST_ID_LIMIT",
    "DEFAULT_PROMPT_VERSION",
    "JUDGE_SYSTEM_PROMPT",
    "LABEL_DEFINITIONS",
    "LABEL_SELECTION_RULES",
    "DataFlywheelJudgeClient",
    "OpenAIDataFlywheelJudgeClient",
    "build_judge_input",
    "normalize_judge_output",
]
