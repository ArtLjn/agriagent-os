---
name: get_cost_summary
type: read-only
description: 查询农场账单、收支、成本、收入、利润和流水明细，支持周账单、月账单、年账单、分类汇总和按月汇总。
triggers:
  - 账单
  - 周账单
  - 月账单
  - 年账单
  - 本周
  - 本月
  - 今年
  - 收支
  - 成本
  - 收入
  - 利润
  - 流水
  - 明细
cache_ttl: 300
parameters:
  type: object
  properties:
    cycle_id:
      type: integer
      description: "种植周期 ID，可选。不传则查当前农场全部记录。"
    date_from:
      type: string
      description: "开始日期 YYYY-MM-DD。用户说本周、本月、今年等相对周期时，先换算成明确日期。"
    date_to:
      type: string
      description: "结束日期 YYYY-MM-DD。"
    record_type:
      type: string
      description: "记录类型: cost(支出)/income(收入)/all(全部)。"
      default: "all"
    category:
      type: string
      description: "分类筛选，如人工、化肥、种子。"
    group_by:
      type: string
      description: "分组方式: none(汇总+明细)/category(按分类)/month(按月)。"
      default: "none"
---

# 账单查询

## 何时使用
用户查询真实账务数据时使用本 Skill，包括周账单、月账单、年账单、收支汇总、成本、收入、利润、分类统计和流水明细。只要用户问“花了多少”“赚了多少”“账怎么样”“这个月支出”“今年收入”等，都应先调用本 Skill 获取数据库数据。

## 不要使用
- 用户是在新增一笔支出、收入或赊账时，不要使用本 Skill，应使用 `create_cost_record`。
- 用户是在做同比、环比、趋势分析时，优先使用 `get_cost_analytics`。
- 用户只是在闲聊、询问种植建议或天气时，不要使用本 Skill。

## 参数推断
- “本周账单”“这周花了多少” -> 换算本周一到本周日，`record_type=all` 或 `cost`，`group_by=none`。
- “本月账单”“这个月收支” -> 本月 1 日到本月最后一天，`record_type=all`。
- “今年收入”“年度账单” -> 今年 1 月 1 日到 12 月 31 日。
- “上个月支出” -> 上月 1 日到上月最后一天，`record_type=cost`。
- “按分类看”“分类汇总” -> `group_by=category`。
- “按月看今年账单” -> `group_by=month`。
- “流水”“明细”“每笔” -> `group_by=none`。
- “化肥花了多少” -> `category=化肥`, `record_type=cost`。

## 缺参策略
- 未说明周期时，默认查询本月。
- 未说明收入或支出时，默认 `record_type=all`。
- 未说明分组方式时，默认 `group_by=none`，返回汇总和最近明细。
- 不知道具体 `cycle_id` 时不要编造，可不传。

## 多工具协作
如果用户同时问账务和农场整体情况，可与 `get_farm_status` 一起使用。如果用户问“比上个月多花多少”，应使用 `get_cost_analytics`，必要时再用本 Skill 补充明细。

## Runtime 策略
- permission: read
- direct_call: true
- direct_return: false
- cache: none

## 失败处理
- 日期或筛选条件不明确时，用中文说明默认查询范围。
- 查询失败时返回中文说明，不暴露内部异常。

## 示例
- 用户：“查一下本周账单” -> `get_cost_summary(date_from="本周一", date_to="本周日", record_type="all", group_by="none")`
- 用户：“这个月化肥花了多少” -> `get_cost_summary(date_from="本月1日", date_to="本月最后一天", record_type="cost", category="化肥")`
- 用户：“今年账单按月汇总” -> `get_cost_summary(date_from="今年1月1日", date_to="今年12月31日", record_type="all", group_by="month")`
