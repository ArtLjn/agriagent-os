"""Farm 模块服务。"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.context.invalidation import invalidate_farm_context
from app.infra.repository_runtime import (
    get_agent_record_repository,
    run_maybe_awaitable,
)
from app.infra.skill_cache import clear_cache as clear_skill_cache
from app.models.farm import Farm
from app.models.user_setting import UserSetting
from app.modules.farm.city_coords import resolve_city_coords
from app.services.farm_context_service import clear_context_cache
from app.services.weather.cache import weather_cache

FARM_LOCATION_FORBIDDEN = "FARM_LOCATION_FORBIDDEN"


def create_default_farm(db: Session, user_id: str, nickname: str) -> Farm:
    """为新用户创建默认农场。"""
    farm = Farm(name=f"{nickname}的农场", user_id=user_id)
    db.add(farm)
    return farm


def get_farm_by_user_id(db: Session, user_id: str) -> Farm | None:
    """通过用户 ID 获取关联农场。"""
    return db.query(Farm).filter(Farm.user_id == user_id).first()


def backfill_default_farm_location_from_settings(
    db: Session, *, user_id: str
) -> Farm | None:
    """当默认农场缺少地区时，用旧用户设置城市回填一次。"""
    farm = get_farm_by_user_id(db, user_id)
    if farm is None or (farm.location and farm.location.strip()):
        return farm

    setting = db.query(UserSetting).filter(UserSetting.user_id == user_id).first()
    if setting and setting.default_city and setting.default_city.strip():
        farm.location = setting.default_city.strip()
        db.flush()
    return farm


def update_default_farm_location(
    db: Session,
    *,
    user_id: str,
    location: str,
    lat: float | None = None,
    lon: float | None = None,
    farm_id: int | None = None,
) -> Farm:
    """更新当前用户默认农场经营地区，并失效相关缓存。"""
    farm = get_farm_by_user_id(db, user_id)
    if farm is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "FARM_NOT_FOUND", "detail": "未找到关联农场"},
        )
    if farm_id is not None and farm.id != farm_id:
        raise HTTPException(
            status_code=403,
            detail={"code": FARM_LOCATION_FORBIDDEN, "detail": "无权修改该农场地区"},
        )

    farm.location = location.strip()
    sync_user_default_city(
        db, user_id=user_id, location=farm.location, lat=lat, lon=lon
    )
    deleted_daily_records = clear_daily_advice_cache(db, farm.id)
    db.commit()
    db.refresh(farm)
    invalidate_farm_location_caches(farm.id, deleted_daily_records)
    return farm


def sync_user_default_city(
    db: Session,
    *,
    user_id: str,
    location: str,
    lat: float | None = None,
    lon: float | None = None,
) -> UserSetting:
    """同步旧用户设置默认城市，避免上下文仍读取旧经营地区。"""
    setting = db.query(UserSetting).filter(UserSetting.user_id == user_id).first()
    if setting is None:
        setting = UserSetting(user_id=user_id)
        db.add(setting)
    setting.default_city = location.strip()
    if (lat is None or lon is None) and setting.default_city:
        coords = resolve_city_coords(setting.default_city)
        if coords is not None:
            lat, lon = coords
    setting.default_lat = lat
    setting.default_lon = lon
    return setting


def invalidate_farm_location_caches(
    farm_id: int, deleted_daily_records: int = 0
) -> dict[str, int | bool | None]:
    """清理经营地区变更影响到的上下文和天气缓存。"""
    context_result = invalidate_farm_context(farm_id)
    clear_context_cache()
    weather_cache.clear()
    weather_skill_invalidated = clear_skill_cache("weather")
    return {
        **context_result,
        "weather_cache_cleared": True,
        "farm_summary_cache_cleared": True,
        "weather_skill_invalidated": weather_skill_invalidated,
        "daily_advice_deleted": deleted_daily_records,
    }


def clear_daily_advice_cache(db: Session, farm_id: int) -> int:
    """删除该农场已有每日建议缓存。"""
    deleted = run_maybe_awaitable(
        get_agent_record_repository(db).delete_daily_cache(farm_id=farm_id)
    )
    return int(deleted or 0)


__all__ = [
    "FARM_LOCATION_FORBIDDEN",
    "backfill_default_farm_location_from_settings",
    "create_default_farm",
    "get_farm_by_user_id",
    "clear_daily_advice_cache",
    "invalidate_farm_location_caches",
    "update_default_farm_location",
]
