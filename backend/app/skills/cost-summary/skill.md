---
name: get_cost_summary
description: 查询农场成本与收入汇总，支持多维度筛选与分组
triggers:
  - 成本
  - 收入
  - 利润
  - 收支
cache_ttl: 300
---

# 成本汇总查询 Skill

## 功能
查询农场的成本与收入汇总，支持按周期、日期范围、分类、记录类型筛选，并可按分类或月份分组。

## 参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| cycle_id | integer | 否 | 种植周期 ID（可选，不传则查全部记录） |
| date_from | string | 否 | 开始日期 YYYY-MM-DD |
| date_to | string | 否 | 结束日期 YYYY-MM-DD |
| record_type | string | 否 | 记录类型: cost(支出)/income(收入)/all(全部，默认) |
| category | string | 否 | 分类筛选（可选，如'人工'、'化肥'） |
| group_by | string | 否 | 分组方式: none(不分组)/category(按分类)/month(按月)，默认none |

## 缓存策略
- TTL: 300s (5分钟)
- Key: cost_summary:{hash(str(sorted(params.items())))}

## 数据源
- SQLite 数据库 (CostRecord 表)
