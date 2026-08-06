"""Agent 领域异常。"""


class FarmIdMissingError(RuntimeError):
    """缺少可信 farm_id 时终止 Agent 流程。"""


__all__ = ["FarmIdMissingError"]
