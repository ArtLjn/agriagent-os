---
name: get_recent_farm_logs
description: 查询指定周期最近N天的农事记录
triggers:
  - 记录
  - 日志
  - 农事
cache_ttl: 60
---

# 农事记录查询 Skill

## 功能
查询指定种植周期最近N天的农事操作记录，按日期倒序排列。

## 参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| cycle_id | integer | 是 | 种植周期 ID |
| days | integer | 否 | 查询天数（默认7天） |

## 缓存策略
- TTL: 60s (1分钟)
- Key: logs:{cycle_id}:{days}

## 数据源
- SQLite 数据库 (FarmLog 表)
