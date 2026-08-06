"""统一位置数据 API。"""

from fastapi import APIRouter, Query

from app.domains.weather.location_catalog import catalog_meta
from app.domains.weather.location_catalog import list_regions
from app.domains.weather.location_catalog import search_regions
from app.domains.weather.location_catalog import to_public_region

router = APIRouter(prefix="/locations", tags=["locations"])


@router.get("/search")
def search_locations(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=50),
):
    """搜索统一行政区划坐标。"""
    items = [to_public_region(region) for region in search_regions(q, limit=limit)]
    return {"items": items, "total": len(items)}


@router.get("/meta")
def get_location_meta():
    """获取位置数据版本和来源信息。"""
    return catalog_meta()


@router.get("/regions")
def get_location_regions(
    province: str | None = None,
    city: str | None = None,
):
    """获取省市区层级数据，供 App/Admin 城市选择器使用。"""
    return list_regions(province=province, city=city)


__all__ = ["router"]
