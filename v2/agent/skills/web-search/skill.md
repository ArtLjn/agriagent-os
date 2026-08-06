---
name: web_search
kind: local
risk_level: read
description: 搜索互联网获取最新信息。用于查找农资价格、新品种介绍、病虫害防治等外部信息。
triggers:
  - 搜索
  - 查一下
  - 最新价格
  - 怎么防治
parameters:
  type: object
  properties:
    query:
      type: string
      description: 搜索关键词。
    num_results:
      type: integer
      description: 返回结果数量，默认 5。
  required: [query]
---

# web_search

本地 skill，直接调第三方搜索 API（DuckDuckGo HTML，无需 API key）。

## 何时使用

- "查一下今年番茄价格行情"
- "最新黄瓜新品种有哪些"
- "蚜虫怎么防治"
- "搜一下江苏 8 月天气趋势"

## 不要使用

- 农场内部数据 → 用对应业务 MCP tool
- 天气预报 → 用 `get_weather`
- 纯数学计算 → 用 `calculate_arithmetic`

## 实现说明

MVP 阶段用 DuckDuckGo HTML 接口（无 key）。返回前 N 条结果摘要。
如需更强搜索能力（Serper/Bing/Google），后续可换 backend，interface 不变。
