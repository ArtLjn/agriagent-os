"""天气预报路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from business.api.deps import get_current_user
from business.config import settings
from business.db import get_db
from business.services import (
    farm_crud_service,
    location_service,
    user_service,
    weather_service,
)

router = APIRouter(prefix="/weather", tags=["weather"])


def _resolve_location(
    db: Session,
    farm_id: int,
    location: str | None,
    lat: float | None,
    lon: float | None,
    user_id: str | None = None,
) -> tuple[str, float | None, float | None]:
    user_settings = user_service.get_user_settings(user_id) if user_id else None
    farm = farm_crud_service.get_farm_by_id(db, farm_id)
    if lat is not None and lon is not None:
        return location or (farm.location if farm else None) or "北京", lat, lon

    explicit_location = bool(location and location.strip())
    default_city = (user_settings or {}).get("default_city")
    resolved_location = (
        location
        if explicit_location
        else default_city or (farm.location if farm else None) or "北京"
    )

    if not explicit_location and user_settings:
        default_lat = user_settings.get("default_lat")
        default_lon = user_settings.get("default_lon")
        if default_lat is not None and default_lon is not None:
            return resolved_location, default_lat, default_lon

    coords = location_service.find_coords(resolved_location)
    if coords is not None:
        return resolved_location, coords[0], coords[1]
    # 显式地点不能静默套用默认坐标，否则 Agent 无法收到 unknown_location
    # 并按 Skill 约定调用 search_cities 重试；农场自身地点仍保留系统默认兜底。
    if location and location.strip():
        return resolved_location, None, None
    return resolved_location, settings.weather.latitude, settings.weather.longitude


@router.get("")
async def get_weather(
    location: str | None = Query(default=None, max_length=100),
    days: int = Query(default=3, ge=1, le=7),
    lat: float | None = Query(default=None, ge=-90, le=90),
    lon: float | None = Query(default=None, ge=-180, le=180),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    resolved_location, resolved_lat, resolved_lon = _resolve_location(
        db, user["farm_id"], location, lat, lon, user["user_id"]
    )
    return await weather_service._fetch_weather_async(
        location=resolved_location,
        days=days,
        lat=resolved_lat,
        lon=resolved_lon,
    )


@router.get("/now")
async def get_weather_now(
    location: str | None = Query(default=None, max_length=100),
    lat: float | None = Query(default=None, ge=-90, le=90),
    lon: float | None = Query(default=None, ge=-180, le=180),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    resolved_location, resolved_lat, resolved_lon = _resolve_location(
        db, user["farm_id"], location, lat, lon, user["user_id"]
    )
    return await weather_service._fetch_weather_async(
        location=resolved_location,
        days=1,
        lat=resolved_lat,
        lon=resolved_lon,
    )
