"""API 边界可调用的 context 缓存失效用例。"""

from sqlalchemy.orm import Session

from app.context.invalidation import invalidate_farm_context
from app.modules.farm.service import get_farm_by_user_id


def invalidate_user_farm_context(
    db: Session, user_id: str
) -> dict[str, int | bool] | None:
    """清理当前用户关联农场的上下文缓存。"""
    farm = get_farm_by_user_id(db, user_id)
    if farm is None:
        return None
    return invalidate_farm_context(farm.id)


__all__ = ["invalidate_user_farm_context"]
