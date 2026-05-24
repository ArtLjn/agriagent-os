---
name: get_cycle_cost_summary
description: 查询指定周期的成本与收入汇总
triggers:
  - 成本
  - 收入
  - 利润
  - 收支
cache_ttl: 300
---

# 成本汇总查询 Skill

## 功能
查询种植周期的成本与收入汇总，包含总成本、总收入、净利润及明细。

## 参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| cycle_id | integer | 是 | 种植周期 ID |

## 缓存策略
- TTL: 300s (5分钟)
- Key: cost:{cycle_id}

## 数据源
- SQLite 数据库 (CostRecord 表)
