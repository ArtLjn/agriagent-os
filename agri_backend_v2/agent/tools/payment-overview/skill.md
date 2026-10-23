---
schema_version: 1
name: get_payment_overview
kind: mcp
mcp_tool: business.get_payment_overview
risk_level: read
description: 同时盘点应收赊账、应付赊账和未结工资，适用于“还有哪些钱没结”“收付款盘点”。
triggers: [待结款, 收付款盘点, 未结工资]
operations: {}
parameters:
  type: object
  properties: {}
---

分别展示应收、应付和工资；不能混合收付方向或把工资重复当作新增成本。此能力只读，不代替结算；用户明确要求结算时切换现有结算工具并遵守审批。金额以工具结果为准。
如果盘点已满足用户请求，直接回答；若还要求明细或后续操作，继续处理未完成的要求，写入仍须遵守对应工具的审批规则。

## 工具使用方法

本目录由 SkillLoader 加载，McpSkill 提供执行封装，调用 Business 的 `get_payment_overview`。

- “还有哪些钱没结” → `get_payment_overview({})`，无需业务参数。
- 工具从鉴权上下文取得当前农场身份，不接收模型传入的农场 ID。
- 返回 `debts` 的每项包含 `record_type`、`counterparty`、`remaining`。`income` 是应收，`cost` 是应付，按方向分别列出交易对手和未结金额。
- `unpaid_labor` 是独立工资汇总，`total_unpaid` 表示未付工资总额。不要与赊账直接相加后称为总成本。
- 空列表表示该类没有未结记录；调用失败不等于全部结清。成功盘点也不能声称已经付款或收款。
