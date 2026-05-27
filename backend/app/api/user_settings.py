"""用户设置 API 路由。"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_farm, get_db
from app.models.farm import Farm
from app.schemas.settings import UserSettings, UserSettingsUpdate

router = APIRouter(prefix="/settings", tags=["settings"])

__all__ = ["router"]


@router.get("", response_model=UserSettings)
def get_settings(farm: Farm = Depends(get_current_farm)) -> UserSettings:
    """获取当前用户设置。"""
    return UserSettings(display_name=farm.name or "农友")


@router.put("", response_model=UserSettings)
def update_settings(
    payload: UserSettingsUpdate,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> UserSettings:
    """更新用户设置。"""
    farm.name = payload.display_name
    db.commit()
    db.refresh(farm)
    return UserSettings(display_name=farm.name)
