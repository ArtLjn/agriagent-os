"""业务上下文缓存失效入口（archive 兼容层）。

archive service 在写操作后会调用 invalidate_farm_context 触发缓存清理。
agri_backend_v2 当前未实现 farm 上下文缓存层，这里提供 no-op stub，让复用的 archive service
代码无需修改即可运行。后续接入缓存层时替换为真实实现。
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def invalidate_farm_context(farm_id: int) -> dict:
    """失效农场上下文缓存（当前为 no-op）。

    Args:
        farm_id: 农场 ID

    Returns:
        清理结果统计（当前空实现返回空 dict）。
    """
    logger.debug("invalidate_farm_context (no-op): farm_id=%s", farm_id)
    return {}


__all__ = ["invalidate_farm_context"]
