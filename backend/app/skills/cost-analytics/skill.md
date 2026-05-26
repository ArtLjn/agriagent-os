---
name: get_cost_analytics
description: 分析农场收支趋势与对比，支持按月/去年同期对比。触发词: 分析、趋势、对比、比去年、比上月、收支分析
triggers:
  - 分析
  - 趋势
  - 对比
  - 比去年
  - 比上月
  - 收支分析
cache_ttl: 300
parameters:
  type: object
  properties:
    date_from:
      type: string
      description: "分析开始日期 YYYY-MM-DD"
    date_to:
      type: string
      description: "分析结束日期 YYYY-MM-DD"
    compare_period:
      type: string
      description: "对比周期: none(不对比)/last_month(上月)/last_year(去年同期)"
      default: "none"
  required:
    - date_from
    - date_to
---

# 收支分析

## 功能
分析农场指定日期范围内的收支数据，支持与上月或去年同期对比，返回支出/收入变化百分比及 TOP 分类。

## 参数说明
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| date_from | string | 是 | 分析开始日期 YYYY-MM-DD |
| date_to | string | 是 | 分析结束日期 YYYY-MM-DD |
| compare_period | string | 否 | 对比周期: none/last_month/last_year，默认 none |

## 示例
用户：「分析一下这个月的收支，跟上个月比」
→ get_cost_analytics(date_from="2026-05-01", date_to="2026-05-31", compare_period="last_month")
返回：收支对比数据，含支出/收入变化百分比
