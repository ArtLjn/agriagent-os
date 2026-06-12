---
name: manage_user_settings
type: write
description: 更新当前用户显示名、默认天气城市、默认经纬度和助手回复角色。
triggers:
  - 修改用户设置
  - 修改默认城市
  - 改显示名
  - 修改助手角色
  - 调整回复语气
parameters:
  type: object
  properties:
    display_name:
      type: string
      description: 显示名。
    default_city:
      type: string
      description: 默认天气城市。
    default_lat:
      type: number
      description: 默认纬度。
    default_lon:
      type: number
      description: 默认经度。
    assistant_role:
      type: string
      enum: [professional, warm, creative]
      description: 助手回复角色，professional=冷静专业型，warm=温暖陪伴型，creative=灵感创意型。
  required: []
---

# manage_user_settings

更新当前用户设置。

## 何时使用

用户明确要修改自己的显示名、默认城市、天气位置、经纬度或助手回复角色时使用。

## 不要使用

不要用它修改其他用户、角色、状态、配额、密码或认证信息。

## 参数推断

- “默认城市改成上海” -> `default_city=上海`。
- “显示名改成老李” -> `display_name=老李`。
- “以后专业一点” -> `assistant_role=professional`。
- “以后温柔一点” -> `assistant_role=warm`。
- “以后有创意一点” -> `assistant_role=creative`。

## 缺参策略

没有任何设置项时追问用户要改什么。

## Runtime 策略

- permission: write_confirm
- direct_call: false
- direct_return: false
- cache: 写入成功后刷新当前用户农场上下文。

## 失败处理

缺少登录用户上下文或用户不存在时返回中文说明。

## 示例

- 用户：“把默认天气城市改成杭州” -> 待确认后更新当前用户设置。
