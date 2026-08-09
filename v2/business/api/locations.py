"""城市搜索与坐标查询路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from business.api.deps import get_current_user
from business.services import location_service

router = APIRouter(prefix="/locations", tags=["locations"])


@router.get("/search")
def search_cities(
    keyword: str = Query(min_length=1, max_length=50),
    limit: int = Query(default=10, ge=1, le=50),
    _user: dict = Depends(get_current_user),
) -> dict:
    return {"items": location_service.search_cities(keyword, limit=limit)}


@router.get("/coords")
def get_coords(
    city: str = Query(min_length=1, max_length=50),
    _user: dict = Depends(get_current_user),
) -> dict:
    coords = location_service.find_coords(city)
    if coords is None:
        return {
            "city": city,
            "latitude": None,
            "longitude": None,
            "found": False,
        }
    return {
        "city": city,
        "latitude": coords[0],
        "longitude": coords[1],
        "found": True,
    }
