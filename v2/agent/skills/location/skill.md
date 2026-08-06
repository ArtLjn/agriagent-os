---
name: search_cities
kind: mcp
mcp_tool: business.search_cities
risk_level: read
description: 查询系统支持的城市/区县列表（含坐标）。
triggers:
  - 城市
  - 坐标
  - 查城市
  - 哪些城市
parameters:
  type: object
  properties:
    keyword:
      type: string
      description: 搜索关键词，如"苏州"、"东城"、"北京市东城区"。
    limit:
      type: integer
      description: 最多返回条数（1-50，默认 10）。
  required:
    - keyword
---

# search_cities

查询系统支持的城市/区县列表（含坐标）。底层用 `shared/location/regions.json`（3366 个区县）做模糊匹配。

## 何时使用

- **调 get_weather 前**：如果用户说的城市名不常见，先 search_cities 确认系统支持的精确名称
- **get_weather 返回 error=unknown_location 后**：用 search_cities 查找相似城市，再用返回的 `full_name` 重新调 get_weather
- **用户问"你们支持哪些城市"**：search_cities("北京") 能列出所有北京下属区县

## 返回结构

```json
{
  "keyword": "苏州",
  "count": 2,
  "cities": [
    {"name": "苏州市", "full_name": "江苏省苏州市", "province": "江苏省",
     "city": "苏州市", "adcode": "320500", "lat": 31.299, "lon": 120.585},
    {"name": "苏州区", "full_name": "黑龙江省大兴安岭地区苏州区", ...}
  ]
}
```

## 匹配优先级

1. 精确匹配 name / full_name / aliases
2. 前缀匹配（"东城" → "东城区"）
3. 包含匹配（"城区" → "东城区"）

## 不要使用

- 查询天气本身 → 用 `get_weather`
- 查询农场位置 → 用 `get_farm_status`
