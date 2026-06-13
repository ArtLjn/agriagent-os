---
name: get_debt_summary
type: read
description: 查询欠款统计，支持普通赊账以及普通赊账+未付人工的总欠款。
triggers:
  - 欠款统计
  - 赊账统计
  - 还欠多少
  - 我欠别人多少钱
parameters:
  type: object
  properties:
    counterparty:
      type: string
      description: 往来对象名称。
    direction:
      type: string
      description: payable=我欠别人，receivable=别人欠我，all=全部；默认 payable。
    limit:
      type: integer
      description: 最多返回对象数。
    scope:
      type: string
      description: debt_only=仅普通赊账，total_payable=普通赊账+未付人工；默认 debt_only。
  required: []
---

# get_debt_summary

查询结构化赊账的未结余额，也可汇总普通赊账和未付人工。用户问“我还欠多少钱/我欠别人多少钱”时设置 `scope=total_payable`；用户明确问“赊账还欠多少”时保持默认 `scope=debt_only`。用户明确问“别人欠我多少钱/应收赊账”时设置 `direction=receivable`。

## 何时使用

- 用户问“我还欠多少钱”“我欠别人多少钱”“欠款统计”。
- 用户明确问“赊账还欠多少”。
- 用户按往来对象查询“张三那边还欠多少”。
- 用户问普通采购/销售赊账余额。

## 不要使用

- 人工工资未付查询使用 `get_labor_payables`。
- 还款、结清、清账等写入动作使用 `settle_debt`。
- 新增一笔赊账使用 `create_cost_record`，并写入结构化 `record_subtype=赊账` 和 `counterparty`。

## 参数推断

- “我还欠多少钱/我欠别人多少钱” -> `scope=total_payable`, `direction=payable`。
- “赊账还欠多少” -> `scope=debt_only`, `direction=payable`。
- “张三那边还欠多少” -> `counterparty=张三`, `direction=payable`。
- “别人欠我多少钱” -> `direction=receivable`。

## 缺参策略

缺少参数时默认查询我方应付普通赊账；用户问总欠款时合并未付人工。

## Runtime 策略

- permission: read
- direct_call: true
- direct_return: true
- cache: 读取欠款上下文。

## 失败处理

查询失败时返回中文说明。没有未结赊账时返回空汇总，不要臆造欠款。

## 示例

- 用户：“我还欠多少钱” -> `get_debt_summary(scope="total_payable", direction="payable")`
- 用户：“赊账还欠多少” -> `get_debt_summary(scope="debt_only", direction="payable")`
