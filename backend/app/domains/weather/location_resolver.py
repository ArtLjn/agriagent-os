"""天气位置解析服务。"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.shared.config import settings
from app.domains.farm.models import Farm
from app.domains.users.settings_models import UserSetting
from app.domains.farm.city_coords import is_ambiguous_city_name
from app.domains.farm.city_coords import resolve_city_coords

_PLACEHOLDER_LOCATIONS = {"", "当前地块", "地块"}


@dataclass(frozen=True)
class WeatherLocation:
    """天气查询位置。"""

    location: str
    lat: float | None
    lon: float | None
    source: str


class AmbiguousWeatherLocationError(ValueError):
    """天气地点缺少上级城市或坐标，无法安全解析。"""

    def __init__(self, location: str) -> None:
        self.location = location
        super().__init__(f"天气地点不明确: {location}")


def has_explicit_weather_location(
    location: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
) -> bool:
    """判断请求是否显式指定天气位置。"""
    if lat is not None and lon is not None:
        return True
    return bool(location and location.strip() not in _PLACEHOLDER_LOCATIONS)


def resolve_weather_location(
    db: Session,
    *,
    farm_id: int | None = None,
    user_id: str | None = None,
    explicit_location: str | None = None,
    explicit_lat: float | None = None,
    explicit_lon: float | None = None,
) -> WeatherLocation:
    """按显式请求、当前农场、用户设置、系统默认解析天气位置。"""
    if explicit_lat is not None and explicit_lon is not None:
        return WeatherLocation(
            location=(explicit_location or "").strip(),
            lat=explicit_lat,
            lon=explicit_lon,
            source="explicit",
        )

    farm = _get_farm(db, farm_id=farm_id, user_id=user_id)
    setting_user_id = user_id or (farm.user_id if farm else None)
    setting = None
    if setting_user_id:
        setting = (
            db.query(UserSetting).filter(UserSetting.user_id == setting_user_id).first()
        )

    if explicit_location and explicit_location.strip() not in _PLACEHOLDER_LOCATIONS:
        location = explicit_location.strip()
        lat = None
        lon = None
        if (
            setting
            and setting.default_city
            and setting.default_city.strip() == location
            and setting.default_lat is not None
            and setting.default_lon is not None
        ):
            lat = setting.default_lat
            lon = setting.default_lon
        if lat is None or lon is None:
            coords = resolve_city_coords(location)
            if coords is not None:
                lat, lon = coords
            elif is_ambiguous_city_name(location):
                raise AmbiguousWeatherLocationError(location)
        return WeatherLocation(
            location=location,
            lat=lat,
            lon=lon,
            source="explicit",
        )

    if farm and farm.location and farm.location.strip():
        location = farm.location.strip()
        lat = None
        lon = None
        if (
            setting
            and setting.default_city
            and setting.default_city.strip() == location
            and setting.default_lat is not None
            and setting.default_lon is not None
        ):
            lat = setting.default_lat
            lon = setting.default_lon
        if lat is None or lon is None:
            coords = resolve_city_coords(location)
            if coords is not None:
                lat, lon = coords
            elif is_ambiguous_city_name(location):
                raise AmbiguousWeatherLocationError(location)
        return WeatherLocation(
            location=location,
            lat=lat,
            lon=lon,
            source="farm",
        )

    if setting:
        city = (setting.default_city or "").strip()
        if setting.default_lat is not None and setting.default_lon is not None:
            return WeatherLocation(
                location=city,
                lat=setting.default_lat,
                lon=setting.default_lon,
                source="user_settings",
            )
        if city:
            lat = None
            lon = None
            coords = resolve_city_coords(city)
            if coords is not None:
                lat, lon = coords
            elif is_ambiguous_city_name(city):
                raise AmbiguousWeatherLocationError(city)
            return WeatherLocation(
                location=city,
                lat=lat,
                lon=lon,
                source="user_settings",
            )

    return WeatherLocation(
        location=explicit_location or "",
        lat=settings.weather_latitude,
        lon=settings.weather_longitude,
        source="system_default",
    )


def _get_farm(
    db: Session,
    *,
    farm_id: int | None,
    user_id: str | None,
) -> Farm | None:
    """读取当前 Farm。"""
    if farm_id is not None:
        return db.query(Farm).filter(Farm.id == farm_id).first()
    if user_id is not None:
        return db.query(Farm).filter(Farm.user_id == user_id).first()
    return None


__all__ = [
    "AmbiguousWeatherLocationError",
    "WeatherLocation",
    "has_explicit_weather_location",
    "resolve_weather_location",
]
