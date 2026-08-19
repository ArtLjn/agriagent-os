---
schema_version: 1
name: manage_user_settings
kind: mcp
mcp_tool: business.manage_user_settings
risk_level: mixed
description: |
  查询或更新当前登录用户的个人偏好设置，包括天气默认城市、默认坐标和助手回复风格。
  只能操作当前用户，不能代替用户管理其他账号的设置。
triggers:
  - 用户设置
  - 偏好设置
  - 默认城市
  - 默认位置
  - 回复风格
operations:
  query:
    tool_name: get_user_settings
    description: 查询当前登录用户的偏好设置；没有设置时返回未配置状态，不编造默认值。
    risk_level: read
    parameters: []
    required: []
  update:
    tool_name: update_user_settings
    description: 更新当前登录用户的天气默认位置或助手回复风格；调用前必须向用户确认将要修改的字段和值。
    risk_level: write_confirm
    parameters: [default_city, default_lat, default_lon, assistant_role]
    required: []
    required_any: [default_city, default_lat, default_lon, assistant_role]
parameters:
  type: object
  properties:
    operation:
      type: string
      enum: [query, update]
      description: query=查看当前设置，update=修改当前设置。
    default_city:
      type: string
      maxLength: 50
      description: 天气查询使用的默认城市或区县名称。
    default_lat:
      type: number
      minimum: -90
      maximum: 90
      description: 默认位置纬度，需与 default_lon 一起表示准确位置时再提供。
    default_lon:
      type: number
      minimum: -180
      maximum: 180
      description: 默认位置经度，需与 default_lat 一起表示准确位置时再提供。
    assistant_role:
      type: string
      enum: [warm, professional, concise]
      description: 助手回复风格：warm=亲切，professional=专业，concise=简洁。
  required: [operation]
---

# manage_user_settings

管理当前登录用户的个人偏好设置，支持查询和更新：

- `query` — 查询当前用户设置（read）
- `update` — 更新当前用户设置（write_confirm）

## 何时使用

- “我的用户设置是什么” → operation=query
- “把默认城市改成苏州” → operation=update, default_city="苏州"
- “以后回答简洁一点” → operation=update, assistant_role="concise"

## 缺参策略

- update 至少需要提供一个要修改的字段；没有字段时追问具体要修改的设置。
- 只修改默认城市时不要求坐标；只有在用户明确提供坐标时才传 default_lat/default_lon。
- assistant_role 只能使用 `warm`、`professional`、`concise`，无法映射时追问用户选择。

## HITL

- query 是 read，不需要确认。
- update 是 write_confirm，调用前必须明确告诉用户要修改的字段和值并取得确认。

## 结果与失败策略

- 查询结果来自当前用户的真实设置；未创建设置时返回未配置状态，不使用示例值代替。
- 查询和更新结果不缓存，确保下一轮能看到最新设置。
- 参数不合法或业务服务失败时返回结构化错误；不要声称设置已经修改成功。

## 不要使用

- 用户要修改昵称或头像时，使用用户资料接口，不把资料字段映射为设置。
- 用户要修改农场信息时，使用农场管理能力，不修改 default_city 代替农场设置。
- 用户询问其他用户的设置时，不尝试传入 user_id；本能力只允许当前登录用户。
