---
schema_version: 1
name: get_farm_status
kind: mcp
mcp_tool: business.get_farm_status
risk_level: read
finalize_after_success: true
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
查询结果已包含概览回答需要的汇总信息，成功后应直接组织回答，不再自动扩展其他专项查询。

## 不要使用

- 用户只问天气 → 用 `get_weather`
- 用户只问最近农事 → 用 `query_farm_logs`
- 用户要创建农事 → 用 `create_farm_log`
