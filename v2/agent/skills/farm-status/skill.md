---
name: get_farm_status
kind: mcp
mcp_tool: business.get_farm_status
risk_level: read
description: 查询农场当前整体状态：活跃茬口、最近农事、今日天气。
triggers:
  - 农场状态
  - 整体情况
  - 当前茬口
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
通常作为多步推理的第一步，收集上下文后再深入具体细节。

## 不要使用

- 用户只问天气 → 用 `get_weather`
- 用户只问最近农事 → 用 `query_farm_logs`
- 用户要创建农事 → 用 `create_farm_log`
