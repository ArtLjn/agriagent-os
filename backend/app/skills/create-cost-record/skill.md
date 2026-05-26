---
name: create_cost_record
description: 记录一笔农场支出或收入，支持赊账备注。触发词: 记了一笔、花多少、买多少、卖多少、赚多少、花了、买了、卖了、记账、赊账、收入了、支出了、万、块
triggers:
  - 记了一笔
  - 花多少
  - 买多少
  - 卖多少
  - 赚多少
  - 花了
  - 买了
  - 卖了
  - 记账
  - 赊账
  - 收入了
  - 支出了
  - 万
  - 块
  - 元
parameters:
  type: object
  properties:
    amount:
      type: number
      description: "金额，必须大于0"
    category:
      type: string
      description: "分类，如'化肥'、'人工'、'大棚膜'"
    record_date:
      type: string
      description: "记录日期 YYYY-MM-DD，默认今天"
    record_type:
      type: string
      description: "cost(支出)或income(收入)，默认cost"
      default: "cost"
    note:
      type: string
      description: "备注，如'赊账-农资店老王'"
  required:
    - amount
    - category
---

# 记账

## 功能
记录一笔农场支出或收入，支持添加赊账备注。金额必填且大于 0，分类必填。

## 参数说明
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| amount | number | 是 | 金额，必须大于0 |
| category | string | 是 | 分类，如'化肥'、'人工'、'大棚膜' |
| record_date | string | 否 | 记录日期 YYYY-MM-DD，默认今天 |
| record_type | string | 否 | cost(支出)/income(收入)，默认 cost |
| note | string | 否 | 备注，如'赊账-农资店老王' |

## 示例
用户：「昨天买了200块化肥」
→ create_cost_record(amount=200, category="化肥", record_date="2026-05-25")
返回：「已记账：化肥 200元（现金），日期 2026-05-25」
