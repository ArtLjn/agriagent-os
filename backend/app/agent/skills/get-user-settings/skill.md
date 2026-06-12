---
name: get_user_settings
type: read
description: 查询当前用户的显示名、默认天气城市/经纬度和助手回复角色设置。
triggers:
  - 用户设置
  - 我的设置
  - 默认城市
  - 助手角色
  - 回复语气
parameters:
  type: object
  properties: {}
  required: []
---

# get_user_settings

查询当前用户设置。

## 何时使用

用户询问自己的显示名、默认城市、天气位置、助手回复角色或个人设置时使用。

## 不要使用

用户要修改设置时使用 `manage_user_settings`。不要查询或修改其他用户设置。

## 参数推断

无参数，始终使用当前登录用户上下文。

## 缺参策略

缺少用户上下文时返回失败说明。

## Runtime 策略

- permission: read
- direct_call: false
- direct_return: false
- cache: 读取用户上下文。

## 失败处理

用户不存在时返回中文说明。

## 示例

- 用户：“我的默认城市是什么” -> 返回当前用户设置。
