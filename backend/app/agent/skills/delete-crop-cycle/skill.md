---
name: delete_crop_cycle
type: write
description: 删除指定茬口，并级联删除其阶段、农事日志、成本记录和种植单元。
triggers:
  - 删除茬口
  - 移除茬口
  - 删掉种植周期
parameters:
  type: object
  properties:
    cycle_id:
      type: integer
      description: 茬口 ID。
  required:
    - cycle_id
---

# delete_crop_cycle

删除指定茬口。

## 何时使用

用户明确要求删除、移除某个茬口或种植周期时使用。

## 不要使用

用户要修改茬口开始日期或阶段时使用 `update_crop_cycle` 或 `update_crop_stage`。

## 参数推断

- “删除茬口 12” -> `cycle_id=12`。

## 缺参策略

缺少 `cycle_id` 时追问，不要猜测当前茬口。

## Runtime 策略

- permission: write_confirm
- direct_call: false
- direct_return: false
- cache: 删除成功后刷新茬口、农事、账务和农场状态缓存。

## 失败处理

找不到茬口时返回中文说明。

## 示例

- 用户：“删除 12 号茬口” -> 待确认后执行高风险删除。
