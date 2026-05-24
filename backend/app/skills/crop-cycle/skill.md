---
name: get_crop_cycle_info
description: 查询指定种植周期的详细信息
triggers:
  - 周期
  - 阶段
  - 茬口
cache_ttl: 600
---

# 种植周期查询 Skill

## 功能
查询种植周期的详细信息，包括名称、起止日期、地块、状态和各阶段安排。

## 参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| cycle_id | integer | 是 | 种植周期 ID |

## 缓存策略
- TTL: 600s (10分钟)
- Key: cycle:{cycle_id}

## 数据源
- SQLite 数据库 (CropCycle 表)
