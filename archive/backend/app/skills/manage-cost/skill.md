---
name: manage_cost
type: write
description: 管理农场账务，支持记账、删除账务、查询汇总、趋势分析、欠款查询和赊账结清。
domain: finance
capability: manage_cost
triggers:
  - 记账
  - 账单
  - 成本
  - 收支
  - 趋势
  - 欠款
  - 还款
  - 删除账务
parameters:
  type: object
  properties:
    operation:
      type: string
      description: "操作类型：create_record、delete_record、query_summary、analyze_cost、query_debt、settle_debt。"
      enum:
        - create_record
        - delete_record
        - query_summary
        - analyze_cost
        - query_debt
        - settle_debt
    amount:
      type: number
      description: 金额，新增账务或还款时使用。
    category:
      type: string
      description: 账务分类，如化肥、种子、销售。
    record_date:
      type: string
      description: 记录日期 YYYY-MM-DD。
    record_type:
      type: string
      description: cost(支出)或 income(收入)，默认 cost。
      default: cost
    note:
      type: string
      description: 备注。
    record_subtype:
      type: string
      description: 赊账、欠款、未付款或未收款时传 赊账。
    counterparty:
      type: string
      description: 赊账、欠款、还款或往来对象。
    due_date:
      type: string
      description: 约定还款或收款日期 YYYY-MM-DD。
    record_id:
      type: integer
      description: 删除账务记录时使用的记录 ID。
    cycle_id:
      type: integer
      description: 查询账务时可按种植周期筛选。
    date_from:
      type: string
      description: 查询或分析开始日期 YYYY-MM-DD。
    date_to:
      type: string
      description: 查询或分析结束日期 YYYY-MM-DD。
    group_by:
      type: string
      description: 查询分组方式：none、category、month。
      default: none
    compare_period:
      type: string
      description: 分析对比周期：none、last_month、last_year。
      default: none
    direction:
      type: string
      description: 欠款方向：payable、receivable、all。
      default: payable
    scope:
      type: string
      description: debt_only 或 total_payable。
      default: debt_only
    limit:
      type: integer
      description: 欠款查询最多返回对象数。
  required:
    - operation
---

# manage_cost

## 何时使用

用户要处理农场账务能力时使用本 Skill，包括新增支出或收入、删除账务记录、查询账单汇总、分析收支趋势、查询欠款和结清赊账。

## 不要使用

- 查询或管理账务分类时使用 `manage_cost_categories`。
- 查询人工欠款、结算人工或管理工资时使用人工结算能力。
- 查询天气、农事、茬口、工人档案或种植单元时使用对应业务能力。

## 参数推断

- “今天买了 100 元化肥” -> `operation=create_record`, `amount=100`, `category=化肥`, `record_type=cost`。
- “这个月花了多少钱” -> `operation=query_summary`, 设置明确的 `date_from` 和 `date_to`。
- “最近三个月成本趋势” -> `operation=analyze_cost`。
- “我还欠老王多少钱” -> `operation=query_debt`, `counterparty=老王`, `direction=payable`。
- “把农资店的账结清” -> `operation=settle_debt`, `counterparty=农资店`。
- “删除账务记录 12” -> `operation=delete_record`, `record_id=12`。

## 缺参策略

- 缺少 `operation` 时必须追问要记账、查账、分析、查欠款、还款还是删除。
- 新增账务缺少金额或分类时必须追问。
- 删除账务缺少 `record_id` 时必须追问，不要猜测最近一条。
- 还款缺少对象时必须追问；缺少金额但用户表达结清或全还时可不传金额。

## Runtime 策略

- permission: operation-aware
- direct_call: 读操作可直接执行，写操作必须进入确认。
- direct_return: false
- cache: 写入、删除和还款成功后清理账务汇总、收支分析和农场状态缓存。

## 失败处理

- 参数不完整时用中文追问必要信息。
- 数据库或业务服务失败时返回中文说明和可重试建议，不暴露内部异常。

## 示例

- 用户：“昨天买了 200 块化肥” -> `manage_cost(operation="create_record", amount=200, category="化肥", record_date="昨天")`
- 用户：“查一下本周账单” -> `manage_cost(operation="query_summary", date_from="本周一", date_to="本周日")`
- 用户：“今年比去年赚得多吗” -> `manage_cost(operation="analyze_cost", date_from="今年1月1日", date_to="今年12月31日", compare_period="last_year")`
- 用户：“老王的钱全还了” -> `manage_cost(operation="settle_debt", counterparty="老王")`
