---
name: create_operation_work_order
type: write
description: 创建农事作业单，可同时记录工人用工和人工成本。
triggers:
  - 创建作业单
  - 记录作业
  - 登记用工
  - 人工成本
parameters:
  type: object
  properties:
    operation_type:
      type: string
      description: 作业类型，如人工授粉、压蔓、装车。
    operation_date:
      type: string
      description: 作业日期 YYYY-MM-DD，默认今天。
    cycle_id:
      type: integer
      description: 种植批次 ID，不传则自动选择第一个活跃批次。
    unit_names:
      type: string
      description: 作用棚或地块名称，多个用逗号分隔。
    note:
      type: string
      description: 备注。
    workers:
      type: string
      description: 工人姓名，多个用逗号分隔。
    unit_price:
      type: number
      description: 每名工人单价。
    paid_worker:
      type: string
      description: 已付款工人姓名。
    paid_amount:
      type: number
      description: 已付金额。
  required:
    - operation_type
---

# create_operation_work_order

创建农事作业单，可同时记录工人用工和人工成本。

## 何时使用

用户明确要记录一次农事作业、创建作业单、登记工人用工或同步记录人工成本时使用。

- 今天东大棚 4 个工人给西瓜授粉，每人 200，先付老王 200
- 记录东大棚 1-3 号压蔓
- 给春茬西瓜补一条装车作业和工人工资

## 不要使用

- 用户只是查询已有作业单时，不要创建新作业单。
- 用户只是记录普通成本且不涉及农事作业时，应使用 `create_cost_record`。
- 用户只是查询茬口阶段或农场状态时，应使用读操作 Skill。

## 参数推断

- “今天东大棚 4 个工人给西瓜授粉，每人 200” -> `operation_type=授粉`, `unit_names=东大棚`, `workers=待确认4人`, `unit_price=200`。
- “记录东大棚 1-3 号压蔓” -> `operation_type=压蔓`, `unit_names=东大棚1-3号`。
- “先付老王 200” -> 在 workers 中记录老王已付金额。

## 缺参策略

- 缺少作业类型时必须追问。
- 缺少日期时默认今天。
- 缺少茬口或种植单元时可结合当前活跃茬口推断；无法唯一确定时追问。
- 涉及多个工人、金额或付款状态不明确时，先生成待确认信息，不要直接写入。

## Runtime 策略
- permission: write_confirm
- direct_call: false
- direct_return: false
- cache: none；写入成功后使作业单、人工应付和账务相关查询缓存失效。

## 失败处理
- 参数缺失或范围无法确定时，用中文追问必要信息。
- 写入失败时返回中文说明和可重试建议，不暴露内部异常。

## 示例

- 用户：“今天东大棚 4 个工人给西瓜授粉，每人 200，先付老王 200” -> 创建授粉作业单并记录工人工资。
- 用户：“给春茬西瓜补一条装车作业和工人工资” -> 创建装车作业单。
