"""统一位置数据 API 测试。"""


def test_search_locations_returns_shared_region_matches(client):
    """位置搜索从 shared/location/regions.json 返回坐标。"""
    response = client.get("/locations/search?q=虎丘")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    first = data["items"][0]
    assert first["display_name"] == "苏州市虎丘区"
    assert first["lat"] == 31.3296
    assert first["lon"] == 120.4342
    assert first["coordinate_source"] == "manual_verified"


def test_search_locations_exposes_ambiguous_names(client):
    """重名区县搜索返回多个带上级城市的候选项。"""
    response = client.get("/locations/search?q=鼓楼区")

    assert response.status_code == 200
    names = {item["display_name"] for item in response.json()["items"]}
    assert "南京市鼓楼区" in names
    assert "徐州市鼓楼区" in names
    assert "福州市鼓楼区" in names


def test_list_location_regions_groups_by_province_city(client):
    """城市选择器可直接按省市区层级获取同一份数据源。"""
    response = client.get("/locations/regions?province=江苏省&city=苏州市")

    assert response.status_code == 200
    data = response.json()
    assert data["province"] == "江苏省"
    assert data["city"] == "苏州市"
    area = next(item for item in data["areas"] if item["name"] == "虎丘区")
    assert area["lat"] == 31.3296
    assert area["lon"] == 120.4342


def test_location_meta_exposes_version_for_client_cache(client):
    """App/Admin 可读取位置数据版本，避免缓存长期失效。"""
    response = client.get("/locations/meta")

    assert response.status_code == 200
    data = response.json()
    assert data["version"] == "2026-06-22"
    assert data["regions_count"] >= 3000
    assert "https://github.com/pfinal/city" in data["source_urls"]
