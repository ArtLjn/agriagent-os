---
name: get_crop_templates
type: read
description: 查询农场作物模板及其生长阶段。
triggers:
  - 作物模板
  - 模板列表
  - 生长阶段模板
parameters:
  type: object
  properties:
    limit:
      type: integer
      description: 返回数量，默认 100。
  required: []
---

# get_crop_templates

查询农场作物模板及其生长阶段。

## 何时使用

用户询问有哪些作物模板、模板阶段、可创建哪些作物茬口时使用。

## 不要使用

用户要创建模板时使用 `create_crop_template`；要修改或删除模板时使用 `manage_crop_templates`。

## 参数推断

无特殊参数；可按用户要求设置 `limit`。

## 缺参策略

缺少参数时返回默认列表。

## Runtime 策略

- permission: read
- direct_call: false
- direct_return: false
- cache: 读取作物模板上下文。

## 失败处理

查询失败时返回中文说明。

## 示例

- 用户：“有哪些作物模板” -> 返回模板列表和阶段。
