---
name: manage_cost_categories
type: write
description: 查询、创建或删除农场账务分类，删除系统默认分类会被拒绝。
triggers:
  - 查询分类
  - 成本分类
  - 收入分类
  - 新增分类
  - 创建分类
  - 删除分类
parameters:
  type: object
  properties:
    operation:
      type: string
      description: 操作：query_categories、create_category、delete_category 或 manage_category。
    action:
      type: string
      description: 兼容操作：create/delete/query。
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
  required: []
---

# manage_cost_categories

查询、创建或删除账务分类。

## 何时使用

用户要查询、新增、创建或删除成本/收入/账务分类时使用。

## 不要使用

- 用户要记录一笔支出或收入时使用 `manage_cost`。
- 用户查询或管理作物、地块、工人、农事时使用对应业务能力。

## 参数推断

- “有哪些成本分类” -> `operation=query_categories`。
- “新增分类农机” -> `action=create`, `name=农机`, `type=cost`。
- “删除分类 12” -> `action=delete`, `category_id=12`。

## 缺参策略

- 查询分类不需要额外参数。
- 创建缺名称时追问；删除缺 `category_id` 时追问。

## Runtime 策略

- permission: operation-aware
- direct_call: false
- direct_return: false
- cache: 查询读取分类；写入成功后刷新分类、账务和农场状态缓存。

## 失败处理

默认分类删除失败时返回中文说明。

## 示例

- 用户：“新增成本分类农机” -> 待确认后创建分类。
- 用户：“有哪些收入分类” -> 返回分类列表。
