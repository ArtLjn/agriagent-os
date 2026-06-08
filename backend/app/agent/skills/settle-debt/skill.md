---
name: settle_debt
type: write
description: 还赊账、还款或结清欠款，支持部分还款和全额还清。
triggers:
  - 还钱
  - 还账
  - 还款
  - 清账
  - 结清
  - 还了
parameters:
  type: object
  properties:
    counterparty:
      type: string
      description: "债权人或交易对象名称/简称，如老王、农资店。"
    amount:
      type: number
      description: "还款金额。不传则全额还清匹配到的欠款。"
    note:
      type: string
      description: "备注。"
  required:
    - counterparty
---

# 还赊账

## 何时使用
用户表达已经还钱、准备结清、清账、把欠款还上等写入动作时使用本 Skill。

## 不要使用
- 用户只是查询“还欠多少”“欠谁的钱”“赊账账单”时，不要用本 Skill；应使用 `get_debt_summary`。
- 用户是在新增一笔赊账时，应使用 `create_cost_record`。
- 用户没有确认实际还款动作时，不要执行。

## 参数推断
- “还了老王 1000 块” -> `counterparty=老王`, `amount=1000`。
- “把农资店的账结清” -> `counterparty=农资店`，不传 `amount` 表示全额。
- “老王的钱全还了” -> `counterparty=老王`，不传 `amount`。

## 缺参策略
- 缺少交易对象时，应追问“还给谁/结清谁的账”。
- 缺少金额但用户说“结清/全还”，可不传金额。
- 缺少金额且没有“全额”语义时，应追问还款金额。

## 多工具协作
还款成功后，如果用户继续问欠款余额，应调用账务查询或债务查询能力读取最新数据。

## Runtime 策略
- permission: write_confirm
- direct_call: false
- direct_return: false
- cache: none；写入成功后使账务、欠款和收支分析相关查询缓存失效。

## 失败处理
- 债权人、金额或还款范围不明确时，用中文追问必要信息。
- 结算失败时返回中文说明和可重试建议，不暴露内部异常。

## 示例
- 用户：“还了老王 1000 块” -> `settle_debt(counterparty="老王", amount=1000)`
- 用户：“农资店的账全清了” -> `settle_debt(counterparty="农资店")`
