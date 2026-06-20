## Purpose

定义 user-settings-api 能力的行为要求。

## Requirements

### Requirement: User settings 数据模型
系统 SHALL 提供 `user_settings` 表，每个用户最多一条记录，包含 `user_id`（unique）、`default_city`、`default_lat`、`default_lon`、`created_at`、`updated_at`。兼容期内 `default_city`、`default_lat`、`default_lon` SHALL 作为旧版默认天气位置兜底字段；新业务天气主位置 SHALL 来自当前用户默认农场的经营地区。

#### Scenario: 新用户首次获取设置
- **WHEN** 用户调用 `GET /settings` 且 `user_settings` 表中无该用户记录
- **THEN** 系统返回 `default_city=null, default_lat=null, default_lon=null`，不创建记录

#### Scenario: 设置不存在时 Agent 降级
- **WHEN** Agent 构建天气上下文时当前农场无经营地区且用户无 `user_settings` 记录
- **THEN** 系统使用 config.yaml 中的默认坐标，不报错

### Requirement: 读取用户设置
系统 SHALL 通过 `GET /settings` 返回当前用户的完整设置，包含 `display_name`、`default_city`、`default_lat`、`default_lon`。客户端 SHALL 将位置主展示来源优先绑定到当前用户默认农场的经营地区；`GET /settings` 返回的位置字段仅用于旧客户端兼容或农场经营地区缺失时兜底。

#### Scenario: 已有设置的用户获取设置
- **WHEN** 用户已登录且 `user_settings` 表中有该用户记录
- **THEN** 系统返回 `{ display_name: "农友", default_city: "苏州", default_lat: 31.3, default_lon: 120.62 }`

#### Scenario: 未认证用户访问
- **WHEN** 请求不带有效 JWT token
- **THEN** 系统返回 401 Unauthorized

### Requirement: 更新用户设置
系统 SHALL 通过 `PUT /settings` 接受部分更新，包含可选字段 `display_name`、`default_city`、`default_lat`、`default_lon`。新客户端 MUST 不再把 `default_city` 作为独立“默认天气”配置入口；经营地区更新 SHALL 写入当前用户默认农场位置，`user_settings` 位置字段仅在兼容旧客户端时更新。

#### Scenario: 首次设置城市
- **WHEN** 旧客户端发送 `PUT /settings { default_city: "北京", default_lat: 39.9, default_lon: 116.41 }` 且表中无该用户记录
- **THEN** 系统创建 `user_settings` 记录并返回完整设置

#### Scenario: 更新已有设置
- **WHEN** 旧客户端发送 `PUT /settings { default_city: "杭州" }` 且已有记录
- **THEN** 系统只更新 `default_city` 字段，其他字段不变，`updated_at` 自动刷新

#### Scenario: 城市名和坐标必须同时传入
- **WHEN** 旧客户端发送 `PUT /settings { default_city: "苏州" }` 但缺少 `default_lat` 或 `default_lon`
- **THEN** 系统接受请求（允许只更新城市名，坐标保持原值或为 null）

### Requirement: 设置记录的自动创建
系统 SHALL 在首次 `PUT /settings` 包含城市信息时自动创建 `user_settings` 记录，通过 `user_id` 关联到 `users` 表。新客户端 SHALL 优先通过经营地区更新流程初始化当前用户默认农场位置，不依赖 `user_settings` 自动创建来定义首次地区设置。

#### Scenario: 注册后首次同步设置
- **WHEN** 旧客户端的新注册用户首次调用 `PUT /settings` 带城市信息
- **THEN** 系统创建新记录并关联到该用户的 `user_id`
