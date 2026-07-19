"""天气 API 路由，提供天气预报数据接口。"""

from fastapi import APIRouter, HTTPException
from fastapi import Depends
from fastapi import Request
from sqlalchemy.orm import Session

from app.shared.database import get_db
from app.shared.config import settings
from app.domains.users.models import User
from app.domains.users.errors import (
    expired_token_error,
    invalid_token_error,
    user_disabled_error,
    user_not_found_error,
)
from app.domains.users.tokens import (
    TokenExpiredError,
    TokenInvalidError,
    decode_access_token,
)
from app.domains.weather.location_resolver import (
    AmbiguousWeatherLocationError,
    resolve_weather_location,
)
from app.domains.weather.service import fetch_weather, check_weather_warnings

router = APIRouter(prefix="/weather", tags=["weather"])

_PLACEHOLDER_LOCATIONS = {"", "当前地块", "地块"}


@router.get("/forecast")
async def get_forecast(
    request: Request,
    days: int = 7,
    location: str = "当前地块",
    lat: float | None = None,
    lon: float | None = None,
    db: Session = Depends(get_db),
):
    """获取未来 N 天天气预报。

    Args:
        days: 预报天数（默认 7 天）。
        location: 城市名（默认"当前地块"）。
        lat: 纬度（与 lon 配合使用，优先级高于 location）。
        lon: 经度（与 lat 配合使用，优先级高于 location）。
    """
    current_user = _get_optional_current_user(request, db)
    if current_user is not None:
        try:
            resolved = resolve_weather_location(
                db,
                user_id=current_user.id,
                explicit_location=location,
                explicit_lat=lat,
                explicit_lon=lon,
            )
        except AmbiguousWeatherLocationError as exc:
            raise _ambiguous_location_error(exc.location) from exc
        location, lat, lon = resolved.location, resolved.lat, resolved.lon
    elif (lat is None or lon is None) and location.strip() in _PLACEHOLDER_LOCATIONS:
        lat = settings.weather_latitude
        lon = settings.weather_longitude
    data = await fetch_weather(location, days, lat, lon)
    warnings = check_weather_warnings(data)
    data["warnings"] = warnings
    return data


def _ambiguous_location_error(location: str) -> HTTPException:
    """地点重名时返回结构化错误，避免静默查询错城市。"""
    return HTTPException(
        status_code=400,
        detail={
            "code": "WEATHER_LOCATION_AMBIGUOUS",
            "detail": f"天气地点“{location}”不明确，请补充上级城市或经纬度。",
        },
    )


def _get_optional_current_user(request: Request, db: Session) -> User | None:
    """无 Authorization 时保持公共天气接口兼容；带 token 时按认证用户解析。"""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header:
        return None
    if not auth_header.startswith("Bearer "):
        raise invalid_token_error()

    token = auth_header[7:]
    try:
        payload = decode_access_token(token)
    except TokenExpiredError:
        raise expired_token_error()
    except TokenInvalidError:
        raise invalid_token_error()

    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise user_not_found_error()
    if user.status != "active":
        raise user_disabled_error()
    return user


__all__ = ["router"]
