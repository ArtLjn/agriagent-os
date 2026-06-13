---
name: get_crop_cycles
type: read
description: 查询农场茬口列表，支持查看全部茬口或按状态过滤。
triggers:
  - 我的茬口
  - 有哪些茬口
  - 茬口列表
  - 种植批次
parameters:
  type: object
  properties:
    status:
      type: string
      description: 按状态过滤：active、planned 或 finished；不传则返回全部。
    limit:
      type: integer
      description: 返回数量，默认 100。
  required: []
---

# get_crop_cycles

查询农场茬口列表。

## 何时使用

用户询问“我的茬口”“有哪些茬口”“茬口列表”“种了什么批次”时使用。

## 不要使用

用户询问某一个具体茬口的阶段详情时使用 `get_crop_cycle_info`；用户询问农场整体经营状态时使用 `get_farm_status`。

## 参数推断

- “有哪些活跃茬口” -> `status=active`。
- “历史茬口” -> `status=finished`。
- “我的茬口” -> 不传参数，返回全部茬口。

## 缺参策略

缺少参数时返回当前农场全部茬口，不追问。

## Runtime 策略

- permission: read
- direct_call: true
- direct_return: false
- cache: 读取茬口上下文。

## 失败处理

查询失败时返回中文说明；无数据时返回“暂无茬口”。

## 示例

- 用户：“我的茬口” -> `get_crop_cycles()`
- 用户：“有哪些活跃茬口” -> `get_crop_cycles(status="active")`
