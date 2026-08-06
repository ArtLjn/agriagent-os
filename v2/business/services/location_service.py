"""Location service.

提供城市坐标查询能力，基于 shared/location/regions.json (3366 个区县)。

数据结构（regions.json 单条示例）：
    {
      "province": "北京市", "city": "北京市", "district": "东城区",
      "name": "东城区", "full_name": "北京市东城区",
      "adcode": "110101", "lat": 39.927, "lon": 116.409,
      "aliases": ["北京东城区", "北京市东城区"]
    }

匹配优先级：
  1. 精确匹配 name / full_name / aliases
  2. startswith 前缀匹配（"东城" → "东城区"）
  3. contains 包含匹配（"北京市东" → "北京市东城区"）

返回字段裁剪为 agent 真正需要的子集（name/full_name/lat/lon/adcode/province/city）。
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# regions.json 路径：v2/shared/location/regions.json
# 从本文件 (business/services/location_service.py) 回溯 3 层 parent 到 v2/
_REGIONS_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "shared" / "location" / "regions.json"
)


@lru_cache(maxsize=1)
def _load_regions() -> list[dict[str, Any]]:
    """加载 regions.json，缓存解析结果。

    1.7MB 文件首次解析约 30ms，后续命中 lru_cache 零开销。
    """
    if not _REGIONS_PATH.exists():
        logger.warning("regions.json not found: %s", _REGIONS_PATH)
        return []
    raw = json.loads(_REGIONS_PATH.read_text(encoding="utf-8"))
    regions = raw.get("regions", []) if isinstance(raw, dict) else []
    logger.info("regions loaded: %d entries from %s", len(regions), _REGIONS_PATH.name)
    return regions


def _strip_suffix(name: str) -> str:
    """去掉行政区划后缀（区/县/市/旗/自治县等），便于模糊匹配。

    "余杭区" → "余杭"
    "苏州市" → "苏州"
    "鄂伦春自治旗" → "鄂伦春"
    """
    for suffix in (
        "自治区", "自治州", "自治县", "地区",
        "区", "县", "市", "旗", "林区",
    ):
        if name.endswith(suffix) and len(name) > len(suffix):
            return name[: -len(suffix)]
    return name


def _match_score(region: dict[str, Any], keyword: str) -> int:
    """计算 keyword 与 region 的匹配分数。0 表示不匹配。

    分数越高越优先：
      100  精确匹配 name（"东城区"）
       90  精确匹配 full_name（"北京市东城区"）
       80  精确匹配 alias
       70  精确匹配 city（"北京市"）
       60  精确匹配 province（"北京市"）
       50  name 以 keyword 开头（"东城" → "东城区"）
       40  full_name 以 keyword 开头
       30  alias 以 keyword 开头
       25  去后缀的 name 精确匹配 keyword（"余杭" == "余杭"）
       20  keyword 包含 name 或去后缀 name（"明天余杭天气" → "余杭区"）
       15  keyword 包含 alias
       10  name 包含 keyword（"城区" → "东城区"，正向包含，容易误匹配故低分）
    """
    name = region.get("name", "")
    full_name = region.get("full_name", "")
    city = region.get("city", "")
    province = region.get("province", "")
    aliases = region.get("aliases") or []

    if keyword == name:
        return 100
    if keyword == full_name:
        return 90
    if keyword in aliases:
        return 80
    if keyword == city:
        return 70
    if keyword == province:
        return 60
    if name.startswith(keyword):
        return 50
    if full_name.startswith(keyword):
        return 40
    if any(a.startswith(keyword) for a in aliases):
        return 30

    # 去后缀匹配：处理"余杭区"→"余杭"、"苏州市"→"苏州"
    stripped = _strip_suffix(name)
    if keyword == stripped and len(stripped) >= 2:
        return 25

    # 反向包含：keyword 是更长的字符串（可能是自然语言），name/stripped/city_stripped 是子串
    # 例如 keyword="明天余杭天气怎么样"，stripped="余杭"
    #      keyword="北京天气"，city="北京市" stripped="北京"
    # 限制长度 ≥ 2 避免单字误匹配
    if len(stripped) >= 2 and stripped in keyword:
        return 20
    if len(name) >= 2 and name in keyword:
        return 20
    city_stripped = _strip_suffix(city)
    if len(city_stripped) >= 2 and city_stripped in keyword:
        return 18
    if any(len(a) >= 2 and a in keyword for a in aliases):
        return 15

    # 正向包含：name 包含 keyword（"城区" → "东城区"）
    # 低分因为容易误匹配（"区"会匹配所有区县）
    if keyword in name:
        return 10
    return 0


def _trim(region: dict[str, Any]) -> dict[str, Any]:
    """裁剪为 agent 真正需要的字段。"""
    return {
        "name": region.get("name", ""),
        "full_name": region.get("full_name", ""),
        "province": region.get("province", ""),
        "city": region.get("city", ""),
        "adcode": region.get("adcode", ""),
        "lat": region.get("lat"),
        "lon": region.get("lon"),
    }


def search_cities(keyword: str, limit: int = 10) -> list[dict[str, Any]]:
    """按关键词模糊搜索城市/区县，返回坐标。

    Args:
        keyword: 搜索关键词，支持城市名、区县名、别名。
                 "苏州" / "苏州市" / "东城区" / "北京市东城区" 均可。
        limit: 最多返回条数（默认 10）。

    Returns:
        按匹配分数降序排列的 region 列表，每条含
        name/full_name/province/city/adcode/lat/lon 字段。
        空列表表示无匹配。
    """
    keyword = (keyword or "").strip()
    if not keyword:
        return []

    regions = _load_regions()
    if not regions:
        return []

    # 限制 limit 避免恶意大值
    limit = max(1, min(limit, 50))

    scored: list[tuple[int, dict[str, Any]]] = []
    for region in regions:
        score = _match_score(region, keyword)
        if score > 0:
            scored.append((score, region))

    if not scored:
        return []

    # 按分数降序，同分按 name 长度升序（短的更可能是用户想要的）
    scored.sort(key=lambda x: (-x[0], len(x[1].get("name", ""))))
    return [_trim(r) for _, r in scored[:limit]]


def find_coords(keyword: str) -> tuple[float, float] | None:
    """精确查询某个城市/区县的坐标（取最佳匹配）。

    用于 weather_service 内部解析 location → (lat, lon)。
    跟 search_cities 的区别：只返回坐标，不返回元数据；找不到返回 None。
    """
    results = search_cities(keyword, limit=1)
    if not results:
        return None
    r = results[0]
    lat, lon = r.get("lat"), r.get("lon")
    if lat is None or lon is None:
        return None
    return float(lat), float(lon)
