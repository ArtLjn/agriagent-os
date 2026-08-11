"""天气预报路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from business.api.deps import get_current_user
from business.config import settings
from business.db import get_db
from business.services import farm_crud_service, location_service, weather_service

router = APIRouter(prefix="/weather", tags=["weather"])


def _resolve_location(
    db: Session,
    farm_id: int,
    location: str | None,
    lat: float | None,
    lon: float | None,
) -> tuple[str, float | None, float | None]:
    farm = farm_crud_service.get_farm_by_id(db, farm_id)
    resolved_location = location or (farm.location if farm else None) or "北京"
    if lat is not None and lon is not None:
        return resolved_location, lat, lon
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
        db, user["farm_id"], location, lat, lon
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
        db, user["farm_id"], location, lat, lon
    )
    return await weather_service._fetch_weather_async(
        location=resolved_location,
        days=1,
        lat=resolved_lat,
        lon=resolved_lon,
    )
