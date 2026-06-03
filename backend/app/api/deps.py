"""FastAPI 依赖注入兼容入口。"""

from app.core.dependencies import get_db

from app.modules.auth.dependencies import get_current_user, require_admin  # noqa: E402
from app.modules.farm.dependencies import (  # noqa: E402
    get_current_farm,
    verify_resource_owner,
)

__all__ = [
    "get_current_farm",
    "get_current_user",
    "get_db",
    "require_admin",
    "verify_resource_owner",
]
