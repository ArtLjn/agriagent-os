---
name: get_cost_analytics
type: read-only
description: 分析农场收支趋势、同比和环比，适合回答比上月、比去年、趋势、变化幅度等问题。
triggers:
  - 分析
  - 趋势
  - 对比
  - 比去年
  - 比上月
  - 同比
  - 环比
  - 收支分析
cache_ttl: 300
parameters:
  type: object
  properties:
    date_from:
      type: string
      description: "分析开始日期 YYYY-MM-DD。"
    date_to:
      type: string
      description: "分析结束日期 YYYY-MM-DD。"
    compare_period:
      type: string
      description: "对比周期: none(不对比)/last_month(上月或上一等长周期)/last_year(去年同期)。"
      default: "none"
  required:
    - date_from
    - date_to
---

# 收支分析

## 何时使用
用户询问趋势、变化、对比、同比、环比、比上个月、比去年同期等分析型问题时使用本 Skill。它用于解释一段时间内收支变化，而不是只列出账单。

## 不要使用
- 用户只是查询“本周账单”“这个月花了多少”“收入明细”时，应使用 `get_cost_summary`。
- 用户要新增记账时，应使用 `create_cost_record`。
- 没有明确分析或对比意图时，不要优先使用本 Skill。

## 参数推断
- “这个月比上个月多花多少” -> 本月日期范围，`compare_period=last_month`。
- “今年和去年比收入怎么样” -> 今年日期范围，`compare_period=last_year`。
- “最近 30 天收支趋势” -> 最近 30 天日期范围，`compare_period=none`。
- “上周比再上一周” -> 上周日期范围，`compare_period=last_month`，当前实现会按等长上一周期比较。

## 缺参策略
- 未说明周期但有“趋势/分析”时，默认分析本月。
- 未说明对比对象时，`compare_period=none`。
- 用户要求精确同比时使用 `last_year`；要求环比时使用 `last_month`。

## 多工具协作
如果用户先问趋势再追问“具体哪几笔导致的”，使用 `get_cost_summary` 查询明细。如果趋势解释需要农场状态背景，可结合 `get_farm_status`。

## Runtime 策略
- permission: read
- direct_call: false
- direct_return: false
- cache: none

## 失败处理
- 缺少可分析周期时，用中文追问或说明默认分析范围。
- 查询失败时返回中文说明，不暴露内部异常。

## 示例
- 用户：“分析一下这个月收支，跟上个月比” -> `get_cost_analytics(date_from="本月1日", date_to="本月最后一天", compare_period="last_month")`
- 用户：“今年比去年赚得多吗” -> `get_cost_analytics(date_from="今年1月1日", date_to="今年12月31日", compare_period="last_year")`
