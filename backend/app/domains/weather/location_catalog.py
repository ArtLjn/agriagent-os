"""统一位置数据目录。"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


@lru_cache(maxsize=1)
def load_catalog() -> dict[str, Any]:
    """读取共享行政区划坐标完整目录。"""
    path = _repo_root() / "shared" / "location" / "regions.json"
    with path.open(encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, dict):
        return {"regions": []}
    return payload


def load_regions() -> list[dict[str, Any]]:
    """读取共享行政区划坐标数据。"""
    payload = load_catalog()
    regions = payload.get("regions", [])
    if not isinstance(regions, list):
        return []
    return [region for region in regions if isinstance(region, dict)]


def catalog_meta() -> dict[str, Any]:
    """返回位置目录元信息。"""
    payload = load_catalog()
    regions = load_regions()
    return {
        "version": payload.get("version"),
        "source": payload.get("source"),
        "source_urls": payload.get("source_urls") or [],
        "coordinate_note": payload.get("coordinate_note"),
        "regions_count": len(regions),
    }


def search_regions(query: str, *, limit: int = 20) -> list[dict[str, Any]]:
    """按名称搜索行政区划。"""
    cleaned = query.strip()
    if not cleaned:
        return []
    matches: list[tuple[int, dict[str, Any]]] = []
    for region in load_regions():
        keys = _search_keys(region)
        if cleaned not in keys:
            continue
        score = _match_score(cleaned, keys)
        matches.append((score, region))
    matches.sort(key=lambda item: (item[0], str(item[1].get("display_name") or "")))
    return [region for _, region in matches[:limit]]


def find_region(query: str) -> dict[str, Any] | None:
    """返回唯一匹配的行政区划；重名或无匹配时返回 None。"""
    cleaned = query.strip()
    if not cleaned:
        return None

    exact_matches: list[dict[str, Any]] = []
    for region in load_regions():
        keys = _search_key_set(region)
        if cleaned in keys:
            exact_matches.append(region)

    if len(exact_matches) == 1:
        return exact_matches[0]
    return None


def list_regions(*, province: str | None = None, city: str | None = None) -> dict[str, Any]:
    """按省市返回城市或区县列表。"""
    regions = load_regions()
    if province and city:
        areas = [
            _public_region(region)
            for region in regions
            if region.get("province") == province
            and region.get("city") == city
            and region.get("district")
        ]
        areas.sort(key=lambda item: item["display_name"])
        return {"province": province, "city": city, "areas": areas}

    if province:
        cities = [
            _public_region(region)
            for region in regions
            if region.get("province") == province
            and region.get("level") == "city"
            and not region.get("district")
        ]
        cities.sort(key=lambda item: item["display_name"])
        return {"province": province, "cities": cities}

    provinces = sorted({str(region.get("province")) for region in regions})
    return {"provinces": [item for item in provinces if item]}


def to_public_region(region: dict[str, Any]) -> dict[str, Any]:
    """转换为客户端可用字段。"""
    return _public_region(region)


def _search_keys(region: dict[str, Any]) -> str:
    return " ".join(_search_key_set(region))


def _search_key_set(region: dict[str, Any]) -> set[str]:
    aliases = region.get("aliases") or []
    parts = [
        str(region.get("name") or ""),
        str(region.get("full_name") or ""),
        str(region.get("display_name") or ""),
        str(region.get("adcode") or ""),
        *(str(alias) for alias in aliases),
    ]
    return {part for part in parts if part}


def _match_score(query: str, keys: str) -> int:
    if keys == query:
        return 0
    if f" {query} " in f" {keys} ":
        return 1
    return 2


def _public_region(region: dict[str, Any]) -> dict[str, Any]:
    return {
        "province": region.get("province"),
        "city": region.get("city"),
        "district": region.get("district"),
        "name": region.get("name"),
        "full_name": region.get("full_name"),
        "display_name": region.get("display_name"),
        "adcode": region.get("adcode"),
        "lat": region.get("lat"),
        "lon": region.get("lon"),
        "level": region.get("level"),
        "coordinate_system": region.get("coordinate_system"),
        "coordinate_source": region.get("coordinate_source"),
    }


__all__ = [
    "catalog_meta",
    "find_region",
    "list_regions",
    "load_catalog",
    "load_regions",
    "search_regions",
    "to_public_region",
]
