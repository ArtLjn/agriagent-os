"""统一位置坐标数据源测试。"""

import json
from pathlib import Path

from app.modules.farm.city_coords import is_ambiguous_city_name
from app.modules.farm.city_coords import resolve_city_coords


def test_shared_regions_cover_existing_city_picker_dataset():
    """共享 JSON 不是示例数据，必须覆盖现有城市选择器主数据集。"""
    path = Path(__file__).resolve().parents[2] / "shared" / "location" / "regions.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    regions = payload["regions"]
    names = {region["display_name"] for region in regions}
    sources = {region["coordinate_source"] for region in regions}

    assert len(regions) >= 3000
    assert "https://github.com/pfinal/city" in payload["source_urls"]
    assert "pfinal_city_region_sql_bd09ll_converted" in sources
    assert "manual_verified" in sources
    assert "北京市朝阳区" in names
    assert "上海市浦东新区" in names
    assert "广州市天河区" in names
    assert "深圳市南山区" in names
    assert "苏州市虎丘区" in names


def test_shared_regions_override_district_coordinates():
    """区县坐标优先来自 shared/location/regions.json。"""
    assert resolve_city_coords("苏州市虎丘区") == (31.3296, 120.4342)
    assert resolve_city_coords("虎丘区") == (31.3296, 120.4342)


def test_shared_regions_disambiguate_duplicate_district_names():
    """重名区县必须带上级城市才能解析到不同坐标。"""
    assert is_ambiguous_city_name("鼓楼区") is True
    assert resolve_city_coords("鼓楼区") is None
    assert resolve_city_coords("徐州市鼓楼区") == (34.28889, 117.18559)
    assert resolve_city_coords("南京市鼓楼区") == (32.06634, 118.76974)


def test_shared_regions_keep_existing_county_fallback():
    """已有区县坐标被网络源校准，不再退回地级市中心。"""
    assert resolve_city_coords("睢宁县") == (33.914129, 117.935535)
