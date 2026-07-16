"""用户设置 API 路由。"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agent.application.chat_use_case_helpers import invalidate_user_farm_context
from app.agent.assistant_roles import DEFAULT_ASSISTANT_ROLE, normalize_assistant_role
from app.core.dependencies import get_db
from app.modules.auth.dependencies import get_current_user
from app.models.user import User
from app.models.user_setting import UserSetting
from app.schemas.settings import UserSettingsResponse, UserSettingsUpdate

router = APIRouter(prefix="/settings", tags=["settings"])

__all__ = ["router"]


def _get_or_none(db: Session, user_id: str) -> UserSetting | None:
    """获取用户设置记录，不存在返回 None。"""
    return db.query(UserSetting).filter(UserSetting.user_id == user_id).first()


@router.get("", response_model=UserSettingsResponse)
def get_settings(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UserSettingsResponse:
    """获取当前用户设置。"""
    setting = _get_or_none(db, user.id)
    return UserSettingsResponse(
        display_name=user.nickname or "农友",
        default_city=setting.default_city if setting else None,
        default_lat=setting.default_lat if setting else None,
        default_lon=setting.default_lon if setting else None,
        assistant_role=normalize_assistant_role(
            setting.assistant_role if setting else None
        ),
    )


@router.put("", response_model=UserSettingsResponse)
def update_settings(
    payload: UserSettingsUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UserSettingsResponse:
    """更新用户设置，首次写入时自动创建记录。"""
    # 更新 display_name（存 User.nickname）
    if payload.display_name is not None:
        user.nickname = payload.display_name

    # 获取或创建 user_setting 记录
    setting = _get_or_none(db, user.id)
    city_fields = {
        "default_city": payload.default_city,
        "default_lat": payload.default_lat,
        "default_lon": payload.default_lon,
    }
    has_city_update = any(v is not None for v in city_fields.values())
    has_role_update = payload.assistant_role is not None

    if setting is None and (has_city_update or has_role_update):
        setting = UserSetting(user_id=user.id, assistant_role=DEFAULT_ASSISTANT_ROLE)
        db.add(setting)

    if setting is not None:
        for field, value in city_fields.items():
            if value is not None:
                setattr(setting, field, value)
        if payload.assistant_role is not None:
            setting.assistant_role = payload.assistant_role

    db.commit()
    invalidate_user_farm_context(db, user.id)

    return UserSettingsResponse(
        display_name=user.nickname or "农友",
        default_city=setting.default_city if setting else None,
        default_lat=setting.default_lat if setting else None,
        default_lon=setting.default_lon if setting else None,
        assistant_role=normalize_assistant_role(
            setting.assistant_role if setting else None
        ),
    )
