---
name: manage_planting_units
type: write
description: 创建、更新或删除棚、地块等种植单元。
triggers:
  - 新增地块
  - 修改大棚
  - 删除种植单元
parameters:
  type: object
  properties:
    action:
      type: string
      description: 操作：create/update/delete。
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
  required:
    - action
---

# manage_planting_units

创建、更新或删除棚、地块等种植单元。

## 何时使用

用户明确要新增、修改、停用或删除种植单元、棚、地块、区域时使用。

## 不要使用

用户只是查询单元列表时使用 `get_planting_units`。

## 参数推断

- “给茬口 2 新增东棚 3 亩” -> `action=create`, `cycle_id=2`, `name=东棚`, `area_mu=3`。
- “删除种植单元 7” -> `action=delete`, `unit_id=7`。

## 缺参策略

创建缺 `cycle_id` 或名称时追问；更新和删除缺 `unit_id` 时追问。

## Runtime 策略

- permission: write_confirm
- direct_call: false
- direct_return: false
- cache: 写入成功后刷新农场状态缓存。

## 失败处理

找不到茬口或单元时返回中文说明。

## 示例

- 用户：“把 3 号棚面积改成 4.5 亩” -> 待确认后更新。
