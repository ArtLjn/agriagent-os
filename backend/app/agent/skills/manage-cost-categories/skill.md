---
name: manage_cost_categories
type: write
description: 创建或删除农场账务分类，删除系统默认分类会被拒绝。
triggers:
  - 新增分类
  - 创建分类
  - 删除分类
parameters:
  type: object
  properties:
    action:
      type: string
      description: 操作：create/delete。
    category_id:
      type: integer
      description: 分类 ID。
    name:
      type: string
      description: 分类名称。
    type:
      type: string
      description: cost 或 income。
    icon:
      type: string
      description: 图标名称。
    sort_order:
      type: integer
      description: 排序值。
  required:
    - action
---

# manage_cost_categories

创建或删除账务分类。

## 何时使用

用户明确要新增、创建或删除成本/收入/账务分类时使用。

## 不要使用

用户只是查询分类时使用 `get_cost_categories`。

## 参数推断

- “新增分类农机” -> `action=create`, `name=农机`, `type=cost`。
- “删除分类 12” -> `action=delete`, `category_id=12`。

## 缺参策略

创建缺名称时追问；删除缺 `category_id` 时追问。

## Runtime 策略

- permission: write_confirm
- direct_call: false
- direct_return: false
- cache: 写入成功后刷新分类、账务和农场状态缓存。

## 失败处理

默认分类删除失败时返回中文说明。

## 示例

- 用户：“新增成本分类农机” -> 待确认后创建分类。
