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
    description: |
      更新当前登录用户的默认城市及其坐标。调用前必须先调用 location Skill 的 search_cities(keyword=城市或区县名称)，从同一条 cities 结果读取 full_name、lat、lon，并分别传入 default_city、default_lat、default_lon。
      这三个字段都是必填项；禁止猜测坐标、只传城市、只传坐标或把 search_cities 的 keyword 直接传入。调用前必须向用户展示完整城市和坐标并取得确认。
    risk_level: write_confirm
    parameters: [default_city, default_lat, default_lon, assistant_role]
    required: [default_city, default_lat, default_lon]
  update_coordinates:
    tool_name: update_user_settings_coordinates
    description: |
      更新当前登录用户的默认坐标。只有用户明确提供纬度和经度，或已经通过 location Skill 的 search_cities 得到同一条城市结果时使用；default_lat 和 default_lon 必须同时传入。
      这是局部更新，只传坐标，不修改默认城市。调用前必须向用户展示坐标并取得确认；实际 MCP operation 字段固定传 update。
    risk_level: write_confirm
    parameters: [operation, default_lat, default_lon]
    required: [operation, default_lat, default_lon]
    inject_operation: false
  update_style:
    tool_name: update_user_settings_style
    description: |
      更新当前登录用户的助手回复风格。assistant_role 必须是 warm、professional 或 concise；实际 MCP operation 字段固定传 update。
      调用前必须向用户展示将使用的风格并取得确认。
    risk_level: write_confirm
    parameters: [operation, assistant_role]
    required: [operation, assistant_role]
    inject_operation: false
parameters:
  type: object
  properties:
    operation:
      type: string
      enum: [query, update, update_coordinates, update_style]
      description: query=查看当前设置，update=更新城市及其坐标，update_coordinates=更新坐标，update_style=更新回复风格。
    default_city:
      type: string
      maxLength: 50
      description: 天气查询使用的默认城市或区县名称。更新城市时使用 search_cities 返回的同一条结果中的 full_name，不要自行猜测名称。
    default_lat:
      type: number
      minimum: -90
      maximum: 90
      description: 默认位置纬度。更新坐标时必须与 default_lon 成对提供，城市更新时使用 search_cities 同一条结果中的 lat。
    default_lon:
      type: number
      minimum: -180
      maximum: 180
      description: 默认位置经度。更新坐标时必须与 default_lat 成对提供，城市更新时使用 search_cities 同一条结果中的 lon。
    assistant_role:
      type: string
      enum: [warm, professional, concise]
      description: 助手回复风格：warm=亲切，professional=专业，concise=简洁。
  required: [operation]
---

# manage_user_settings

管理当前登录用户的个人偏好设置，支持查询和更新：

- `query` — 查询当前用户设置（read）
- `update` — 更新默认城市及其坐标（write_confirm）
- `update_coordinates` — 仅更新默认坐标（write_confirm）
- `update_style` — 更新助手回复风格（write_confirm）

## 何时使用

- “我的用户设置是什么” → operation=query
- “把默认城市改成苏州” → 先调用 `search_cities`，再使用 `update_user_settings`，同时传 `default_city`、`default_lat`、`default_lon`
- “把默认坐标改成 31.299487, 120.581823” → 使用 `update_user_settings_coordinates`，传 `operation="update"`、`default_lat`、`default_lon`
- “以后回答简洁一点” → 使用 `update_user_settings_style`，传 `operation="update"`、`assistant_role="concise"`

## 缺参策略

- 不要调用一个同时承载所有更新形态的通用空参数工具；按用户意图选择城市、坐标或风格对应的更新工具。没有明确字段和值时先追问。
- 可更新的内容只有：默认城市（`default_city`）、默认纬度（`default_lat`）、默认经度（`default_lon`）、助手回复风格（`assistant_role`）。不要传入 `user_id`、`keyword` 或其他字段。
- 用户说“把默认城市改成苏州”时，先调用 `search_cities(keyword="苏州")`；从返回的 `cities` 选择与用户意图匹配的结果，读取该项的 `full_name`、`lat`、`lon`，再调用 `update_user_settings` 并同时传 `default_city`、`default_lat`、`default_lon`。有多个同名结果时先让用户选择，不要擅自选择。
- 城市更新不得只传城市名称；必须同步传入同一条 `search_cities` 结果的坐标，避免城市与坐标不一致；不要凭记忆填写坐标。
- 用户明确给出一对坐标时，可只更新 `default_lat`、`default_lon`；坐标必须成对传入，不能只更新其中一个。
- 只有用户明确要求修改回复风格时才更新 `assistant_role`，可选值为 `warm`、`professional`、`concise`。
- 未被修改的字段不要传 `null` 或旧值，保持局部更新。
- assistant_role 只能使用 `warm`、`professional`、`concise`，无法映射时追问用户选择。

## 城市和坐标参数流程

1. 从用户请求提取城市或区县名称，例如“苏州”“北京市东城区”。
2. 调用只读的 `search_cities`：`{"keyword": "苏州", "limit": 10}`。该 Skill 的参数名是 `keyword`，不是 `location`、`city` 或 `query`。
3. 检查返回的 `cities` 数组；从匹配项读取：
   - `full_name` → `default_city`
   - `lat` → `default_lat`
   - `lon` → `default_lon`
4. 结果为空或有多个无法确认的匹配时，向用户澄清，不调用更新。
5. 先向用户展示将要更新的城市和坐标并取得确认，再调用：
   `update_user_settings(default_city=..., default_lat=..., default_lon=...)`

例如用户说“把默认城市改成苏州”，应先查 `search_cities(keyword="苏州")`，不能直接猜坐标；确认后再提交城市、纬度和经度三个字段。

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
