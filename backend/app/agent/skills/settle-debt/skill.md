---
name: settle_debt
description: 还赊账，结清欠款，支持部分还款和全额还清。触发词: 还钱、还账、还款、清账、还了
triggers:
  - 还钱
  - 还账
  - 还款
  - 清账
  - 还了
parameters:
  type: object
  properties:
    counterparty:
      type: string
      description: "债权人名称/简称，如'老王'、'农资店'"
    amount:
      type: number
      description: "还款金额，不传则全额还清"
    note:
      type: string
      description: "备注"
  required:
    - counterparty
---

# 还赊账

## 功能
结清赊账记录，支持部分还款和全额还清两种模式。根据债权人名称查找未结清的赊账记录。

## 参数说明
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| counterparty | string | 是 | 债权人名称/简称，如'老王'、'农资店' |
| amount | number | 否 | 还款金额，不传则全额还清 |
| note | string | 否 | 备注 |

## 示例
- 部分还款：「还了老王1000块」→ settle_debt(counterparty="老王", amount=1000)
- 全额还清：「老王的钱全还了」→ settle_debt(counterparty="老王")
