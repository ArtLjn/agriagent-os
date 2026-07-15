---
name: manage_planting_units
type: write
description: 查询、创建、更新或删除棚、地块等种植单元。
triggers:
  - 查询种植单元
  - 有哪些地块
  - 有哪些大棚
  - 新增地块
  - 修改大棚
  - 删除种植单元
parameters:
  type: object
  properties:
    operation:
      type: string
      description: 业务操作：query_units/manage_units。查询用 query_units，创建/更新/删除用 manage_units。
    action:
      type: string
      description: 管理动作：create/update/delete；兼容旧调用。
    unit_id:
      type: integer
      description: 种植单元 ID。
    cycle_id:
      type: integer
      description: 所属茬口 ID。
    name:
      type: string
      description: 种植单元名称。
    area_mu:
      type: number
      description: 面积，单位亩。
    planted_date:
      type: string
      description: 定植日期，YYYY-MM-DD。
    status:
      type: string
      description: 状态。
    note:
      type: string
      description: 备注。
  required: []
---

# manage_planting_units

查询、创建、更新或删除棚、地块等种植单元。

## 何时使用

用户询问有哪些棚、地块、种植区域或某个茬口下有哪些单元时，使用 `operation=query_units`。

用户明确要新增、修改、停用或删除种植单元、棚、地块、区域时，使用 `operation=manage_units`，并通过 `action=create/update/delete` 指定管理动作。

## 不要使用

用户要查询或管理茬口、作物模板、农事日志、作业单、工人或账务时，不要使用本 Skill。

## 参数推断

- “茬口 3 下有哪些棚” -> `operation=query_units`, `cycle_id=3`。
- “给茬口 2 新增东棚 3 亩” -> `action=create`, `cycle_id=2`, `name=东棚`, `area_mu=3`。
- “删除种植单元 7” -> `action=delete`, `unit_id=7`。

## 缺参策略

查询缺少 `cycle_id` 时查询全农场种植单元，不追问。创建缺 `cycle_id` 或名称时追问；更新和删除缺 `unit_id` 时追问。

## Runtime 策略

- operation=query_units: read
- operation=manage_units: write_confirm
- direct_call: false
- direct_return: false
- cache: 写入成功后刷新农场状态缓存。

## 失败处理

找不到茬口或单元时返回中文说明。

## 示例

- 用户：“有哪些种植单元” -> 返回单元列表。
- 用户：“把 3 号棚面积改成 4.5 亩” -> 待确认后更新。
