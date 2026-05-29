---
name: get_farm_status
description: 获取当前农场综合状态，包括茬口、农事、花费、天气。触发词: 农场、茬口、农事、花费、建议
cache_ttl: 300
parameters:
  type: object
  properties: {}
---

# 农场状态查询

## 功能
获取当前农场综合状态摘要（≤300字），包括活跃茬口、近期农事、欠账、月度花费、天气。

## 示例
用户：「我的辣椒长得怎么样了」
→ get_farm_status()
