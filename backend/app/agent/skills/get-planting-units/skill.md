---
name: get_planting_units
type: read
description: 查询农场种植单元、棚、地块或区域，可按茬口 ID 过滤。
triggers:
  - 种植单元
  - 地块
  - 大棚
  - 棚区
parameters:
  type: object
  properties:
    cycle_id:
      type: integer
      description: 茬口 ID，可选。
  required: []
---

# get_planting_units

查询农场种植单元、棚、地块或区域。

## 何时使用

用户询问有哪些棚、地块、种植区域或某个茬口下有哪些单元时使用。

## 不要使用

用户要新增、修改或删除单元时使用 `manage_planting_units`。

## 参数推断

- “茬口 3 下有哪些棚” -> `cycle_id=3`。

## 缺参策略

缺少 `cycle_id` 时查询全农场种植单元，不追问。

## Runtime 策略

- permission: read
- direct_call: false
- direct_return: false
- cache: 读取种植上下文。

## 失败处理

查询失败时返回中文说明。

## 示例

- 用户：“有哪些种植单元” -> 返回单元列表。
