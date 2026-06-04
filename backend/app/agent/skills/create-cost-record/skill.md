---
name: create_cost_record
type: write
description: 记录一笔农场支出或收入，支持自然语言记账和赊账备注。
triggers:
  - 记账
  - 记一笔
  - 花了
  - 买了
  - 卖了
  - 收入
  - 支出
  - 赊账
  - 元
  - 块
parameters:
  type: object
  properties:
    amount:
      type: number
      description: "金额，必须大于 0。"
    category:
      type: string
      description: "分类，如化肥、人工、种子、大棚膜、番茄销售。"
    record_date:
      type: string
      description: "记录日期 YYYY-MM-DD，默认今天。"
    record_type:
      type: string
      description: "cost(支出)或 income(收入)，默认 cost。"
      default: "cost"
    note:
      type: string
      description: "备注。赊账可写成 赊账-交易对象。"
  required:
    - amount
    - category
---

# 记账

## 何时使用
用户要新增一笔真实账务记录时使用本 Skill，包括买农资、支付人工、销售收入、收到货款、赊账记账等。

## 不要使用
- 用户只是查询账单、收支、利润或明细时，应使用 `get_cost_summary`。
- 用户只是分析趋势或同比环比时，应使用 `get_cost_analytics`。
- 用户要还款或结清赊账时，应使用 `settle_debt`。

## 参数推断
- “买了 200 块化肥” -> `amount=200`, `category=化肥`, `record_type=cost`。
- “卖了番茄赚了 5000” -> `amount=5000`, `category=番茄销售`, `record_type=income`。
- “昨天买了 100 块种子” -> `record_date=昨天对应日期`。
- “在农资店老王那赊了 3000 块大棚膜” -> `amount=3000`, `category=大棚膜`, `record_type=cost`, `note=赊账-农资店老王`。

## 缺参策略
- 缺少金额时，不要编造金额，应提示用户补充。
- 缺少分类时，不要随意归类，应提示用户补充或选择最明显分类。
- 未说明日期时默认今天。
- 未说明收入或支出时，买入、花费、支付默认为支出；卖出、收入、赚了默认为收入。

## 多工具协作
写入成功后，相关账单缓存应失效。用户记账后又问“这个月一共多少”，再调用 `get_cost_summary` 查询最新数据。

## 示例
- 用户：“昨天买了 200 块化肥” -> `create_cost_record(amount=200, category="化肥", record_date="昨天", record_type="cost")`
- 用户：“卖西瓜收入 5w” -> `create_cost_record(amount=50000, category="西瓜销售", record_type="income")`
