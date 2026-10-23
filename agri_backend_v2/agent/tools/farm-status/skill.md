---
schema_version: 1
name: get_farm_status
kind: mcp
mcp_tool: business.get_farm_status
risk_level: read
description: 查询农场当前整体状态：活跃茬口、最近农事、今日天气。
triggers:
  - 农场状态
  - 整体情况
  - 当前茬口
operations: {}
parameters:
  type: object
  properties: {}
---

# get_farm_status

查询农场当前的整体快照，包括：
- 所有活跃茬口（作物、面积、当前生长阶段）
- 最近 7 天的农事记录数量和预览
- 今日天气预报

## 何时使用

用户问"农场怎么样"、"整体情况"、"当前状态"等概览类问题时使用。
如果用户只要当前概览，查询成功后直接组织回答。若用户还要求其他日期的安排、天气或专项明细，应继续查询对应工具，不把今日快照当作明天的安排。
备忘录使用 `query_memos` 查询；天气使用 `get_weather` 的 `days` 覆盖用户要求的日期，并按返回日期筛选。仅补齐当前请求所需的信息，不自行执行额外写操作。

## 不要使用

- 用户只问天气 → 用 `get_weather`
- 用户只问最近农事 → 用 `query_farm_logs`
- 用户要创建农事 → 用 `create_farm_log`
