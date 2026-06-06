---
name: get_cost_categories
type: read
description: 查询农场账务分类，包括支出分类和收入分类。
triggers:
  - 账务分类
  - 成本分类
  - 收入分类
parameters:
  type: object
  properties: {}
  required: []
---

# get_cost_categories

查询农场账务分类。

## 何时使用

用户询问有哪些账务、成本、收入分类时使用。

## 不要使用

用户要创建或删除分类时使用 `manage_cost_categories`。

## 参数推断

无参数。

## 缺参策略

无参数。

## Runtime 策略

- permission: read
- direct_call: false
- direct_return: false
- cache: 使用分类上下文。

## 失败处理

查询失败时返回中文说明。

## 示例

- 用户：“有哪些成本分类” -> 返回分类列表。
