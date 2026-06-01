import json
import urllib.request
import urllib.parse
import concurrent.futures
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

def fetch_geo(name: str) -> dict | None:
    """调用 Open-Meteo Geocoding API，返回 {lat, lon} 或 None。"""
    encoded = urllib.parse.quote(name)
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={encoded}&count=1&language=zh&country=CN"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            results = data.get("results", [])
            if results:
                r = results[0]
                return {"lat": r["latitude"], "lon": r["longitude"]}
    except Exception:
        pass
    return None


def fetch_with_fallback(name: str, fallback_names: list[str]) -> dict:
    """尝试多个名称变体获取坐标。"""
    for n in [name] + fallback_names:
        result = fetch_geo(n)
        if result:
            return result
    return {"lat": 0.0, "lon": 0.0}


def main():
    # 下载 level.json
    print("Downloading level.json...")
    level_url = "https://unpkg.com/province-city-china@8.5.8/dist/level.json"
    with urllib.request.urlopen(level_url) as resp:
        raw_data = json.loads(resp.read().decode("utf-8"))

    municipalities = {"北京市", "上海市", "天津市", "重庆市"}

    # 收集所有需要查询坐标的城市/区
    # 对于省：查询地级市（去掉"市"后缀）
    # 对于直辖市：查询直辖市本身（去掉"市"后缀）
    queries = []  # (display_name, query_variants, province_name)

    for p in raw_data:
        pname = p["name"]
        if pname in municipalities:
            # 直辖市本身
            queries.append((pname, [pname.replace("市", "")], pname))
        else:
            for c in p.get("children", []):
                cname = c["name"]
                # 去掉"市"后缀查询，失败时尝试保留原样或加省份前缀
                short = cname.replace("市", "").replace("地区", "").replace("盟", "")
                if short.endswith("自治州"):
                    short = short.replace("自治州", "")
                queries.append((cname, [short, cname, f"{pname}{short}"], pname))

    print(f"Total queries: {len(queries)}")

    # 并发获取坐标（限制并发数避免被封）
    print("Fetching coordinates...")
    coords = {}

    def fetch_one(args):
        display_name, variants, province = args
        result = fetch_with_fallback(display_name, variants)
        return display_name, result

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(fetch_one, q) for q in queries]
        done = 0
        for future in concurrent.futures.as_completed(futures):
            name, result = future.result()
            coords[name] = result
            done += 1
            if done % 50 == 0:
                print(f"  {done}/{len(queries)} done")

    print(f"  {done}/{len(queries)} done")

    # 统计失败数
    failed = [n for n, c in coords.items() if c["lat"] == 0.0]
    if failed:
        print(f"Warning: {len(failed)} cities failed to fetch coordinates:")
        for f in failed[:10]:
            print(f"  - {f}")
        if len(failed) > 10:
            print(f"  ... and {len(failed) - 10} more")

    # 构建输出结构
    provinces = []
    for p in raw_data:
        pname = p["name"]
        cities = []
        for c in p.get("children", []):
            cname = c["name"]
            if pname in municipalities:
                # 直辖市：用直辖市本身的坐标
                muni_name = pname
                crd = coords.get(muni_name, {"lat": 0.0, "lon": 0.0})
            else:
                crd = coords.get(cname, {"lat": 0.0, "lon": 0.0})

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
    print(f"\nStats: {len(provinces)} provinces, {total_cities} cities, {total_areas} areas")

    # 生成 TypeScript 文件
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

    # 扁平化城市列表（兼容旧代码）
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


if __name__ == "__main__":
    main()
