import json
import urllib.request
import urllib.parse
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

# Province capital coordinates (fallback for cities not found in API)
PROVINCE_CAPITALS = {
    "北京市": (39.9042, 116.4074),
    "天津市": (39.1252, 117.1904),
    "河北省": (38.0428, 114.5149),
    "山西省": (37.8706, 112.5489),
    "内蒙古自治区": (40.8414, 111.7519),
    "辽宁省": (41.8057, 123.4315),
    "吉林省": (43.8171, 125.3235),
    "黑龙江省": (45.8038, 126.5350),
    "上海市": (31.2304, 121.4737),
    "江苏省": (32.0603, 118.7969),
    "浙江省": (30.2741, 120.1551),
    "安徽省": (31.8206, 117.2272),
    "福建省": (26.0745, 119.2965),
    "江西省": (28.6820, 115.8579),
    "山东省": (36.6512, 117.1201),
    "河南省": (34.7466, 113.6253),
    "湖北省": (30.5928, 114.3055),
    "湖南省": (28.2280, 112.9388),
    "广东省": (23.1291, 113.2644),
    "广西壮族自治区": (22.8170, 108.3665),
    "海南省": (20.0440, 110.1999),
    "重庆市": (29.5630, 106.5516),
    "四川省": (30.5728, 104.0668),
    "贵州省": (26.6470, 106.6302),
    "云南省": (25.0389, 102.7183),
    "西藏自治区": (29.6500, 91.1000),
    "陕西省": (34.3416, 108.9398),
    "甘肃省": (36.0611, 103.8343),
    "青海省": (36.6171, 101.7782),
    "宁夏回族自治区": (38.4872, 106.2309),
    "新疆维吾尔自治区": (43.8256, 87.6168),
    "台湾省": (25.0330, 121.5654),
    "香港特别行政区": (22.3193, 114.1694),
    "澳门特别行政区": (22.1987, 113.5439),
}


def fetch_geo(name: str) -> dict | None:
    encoded = urllib.parse.quote(name)
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={encoded}&count=1&language=zh&country=CN"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            results = data.get("results", [])
            if results:
                r = results[0]
                return {"lat": r["latitude"], "lon": r["longitude"]}
    except Exception:
        pass
    return None


def get_variants(name: str) -> list[str]:
    """Generate query name variants for a city name."""
    variants = [name]
    # Remove 市 suffix
    if name.endswith("市"):
        variants.append(name[:-1])
    # Remove 地区
    if name.endswith("地区"):
        variants.append(name[:-2])
    # Remove 盟
    if name.endswith("盟"):
        variants.append(name[:-1])
    # For 自治州, try the prefix before 自治
    if "自治州" in name:
        idx = name.find("自治")
        if idx > 0:
            variants.append(name[:idx])
    return list(dict.fromkeys(variants))  # dedup while preserving order


def main():
    print("Downloading level.json...")
    level_url = "https://unpkg.com/province-city-china@8.5.8/dist/level.json"
    with urllib.request.urlopen(level_url) as resp:
        raw_data = json.loads(resp.read().decode("utf-8"))

    municipalities = {"北京市", "上海市", "天津市", "重庆市"}

    # Phase 1: Fetch coordinates for all cities (no delay, single thread)
    print("Phase 1: Fetching coordinates...")
    city_coords = {}  # city_name -> {lat, lon}
    all_cities = []

    for p in raw_data:
        pname = p["name"]
        for c in p.get("children", []):
            cname = c["name"]
            all_cities.append((cname, pname))

    total = len(all_cities)
    for i, (cname, pname) in enumerate(all_cities, 1):
        if cname in city_coords:
            continue
        variants = get_variants(cname)
        found = False
        for v in variants:
            result = fetch_geo(v)
            if result:
                city_coords[cname] = result
                found = True
                break
        if not found:
            # Use province capital as fallback
            cap = PROVINCE_CAPITALS.get(pname, (30.0, 110.0))
            city_coords[cname] = {"lat": cap[0], "lon": cap[1]}
        if i % 50 == 0:
            print(f"  {i}/{total} done")

    failed_count = sum(1 for cname, pname in all_cities if city_coords[cname]["lat"] == PROVINCE_CAPITALS.get(pname, (30.0, 110.0))[0])
    print(f"  {total}/{total} done")
    print(f"  Cities using fallback: {failed_count}")

    # Phase 2: Build output structure
    print("\nPhase 2: Building data structure...")
    provinces = []
    for p in raw_data:
        pname = p["name"]
        cities = []
        for c in p.get("children", []):
            cname = c["name"]
            crd = city_coords[cname]
            areas = []
            for a in c.get("children", []):
                areas.append({"name": a["name"], "lat": crd["lat"], "lon": crd["lon"]})
            cities.append({
                "name": cname,
                "lat": crd["lat"],
                "lon": crd["lon"],
                "areas": areas,
            })
        provinces.append({"name": pname, "cities": cities})

    total_cities = sum(len(p["cities"]) for p in provinces)
    total_areas = sum(len(c["areas"]) for p in provinces for c in p["cities"])
    print(f"Stats: {len(provinces)} provinces, {total_cities} cities, {total_areas} areas")

    # Phase 3: Generate TypeScript file
    print("\nPhase 3: Writing TypeScript file...")
    out = os.path.join(PROJECT_ROOT, "src", "data", "cities.ts")
    os.makedirs(os.path.dirname(out), exist_ok=True)

    lines = [
        "export interface Area {",
        "  name: string;",
        "  lat: number;",
        "  lon: number;",
        "}",
        "",
        "export interface City {",
        "  name: string;",
        "  lat: number;",
        "  lon: number;",
        "  areas: Area[];",
        "}",
        "",
        "export interface Province {",
        "  name: string;",
        "  cities: City[];",
        "}",
        "",
        "export const PROVINCES: Province[] = [",
    ]

    for p in provinces:
        lines.append(f'  {{ name: "{p["name"]}", cities: [')
        for c in p["cities"]:
            lines.append(f'    {{ name: "{c["name"]}", lat: {c["lat"]}, lon: {c["lon"]}, areas: [')
            for a in c["areas"]:
                lines.append(f'      {{ name: "{a["name"]}", lat: {a["lat"]}, lon: {a["lon"]} }},')
            lines.append("    ] },")
        lines.append("  ] },")
    lines.append("];")
    lines.append("")

    # Flat cities (backward compatibility)
    lines.extend([
        "export interface FlatCity {",
        "  name: string;",
        "  lat: number;",
        "  lon: number;",
        "}",
        "",
    ])

    flat = []
    for p in provinces:
        is_muni = p["name"] in municipalities
        for c in p["cities"]:
            if is_muni:
                for a in c["areas"]:
                    flat.append(a)
                if not c["areas"]:
                    flat.append({"name": c["name"], "lat": c["lat"], "lon": c["lon"]})
            else:
                flat.append({"name": c["name"], "lat": c["lat"], "lon": c["lon"]})

    lines.append("export const CITIES: FlatCity[] = [")
    for fc in flat:
        lines.append(f'  {{ name: "{fc["name"]}", lat: {fc["lat"]}, lon: {fc["lon"]} }},')
    lines.append("];")

    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"\nWritten: {out}")
    print(f"  {len(flat)} selectable cities/districts")
    print(f"  {total_areas} county-level areas")


if __name__ == "__main__":
    main()
