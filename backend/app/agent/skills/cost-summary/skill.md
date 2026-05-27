---
name: get_cost_summary
description: 查询农场成本与收入汇总，支持多维度筛选与分组。触发词: 成本、收入、利润、收支
triggers:
  - 成本
  - 收入
  - 利润
  - 收支
cache_ttl: 300
parameters:
  type: object
  properties:
    cycle_id:
      type: integer
      description: "种植周期ID（可选，不传则查全部记录）"
    date_from:
      type: string
      description: "开始日期 YYYY-MM-DD"
    date_to:
      type: string
      description: "结束日期 YYYY-MM-DD"
    record_type:
      type: string
      description: "记录类型: cost(支出)/income(收入)/all(全部)"
      default: "all"
    category:
      type: string
      description: "分类筛选，如'人工'、'化肥'"
    group_by:
      type: string
      description: "分组方式: none/category(按分类)/month(按月)"
      default: "none"
---

# 成本汇总查询

## 功能
查询农场的成本与收入汇总，支持按周期、日期范围、分类、记录类型筛选，并可按分类或月份分组。

## 参数说明
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| cycle_id | integer | 否 | 种植周期 ID（不传则查全部） |
| date_from | string | 否 | 开始日期 YYYY-MM-DD |
| date_to | string | 否 | 结束日期 YYYY-MM-DD |
| record_type | string | 否 | cost/income/all，默认 all |
| category | string | 否 | 分类筛选，如'人工'、'化肥' |
| group_by | string | 否 | none/category/month，默认 none |

## 示例
用户：「看看这个月的开支」
→ get_cost_summary(date_from="2026-05-01", date_to="2026-05-31", record_type="cost", group_by="category")
