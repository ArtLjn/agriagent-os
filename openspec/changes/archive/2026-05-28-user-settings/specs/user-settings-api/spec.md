## ADDED Requirements

### Requirement: User settings 数据模型
系统 SHALL 提供 `user_settings` 表，每个用户最多一条记录，包含 `user_id`（unique）、`default_city`、`default_lat`、`default_lon`、`created_at`、`updated_at`。

#### Scenario: 新用户首次获取设置
- **WHEN** 用户调用 `GET /settings` 且 `user_settings` 表中无该用户记录
- **THEN** 系统返回 `default_city=null, default_lat=null, default_lon=null`，不创建记录

#### Scenario: 设置不存在时 Agent 降级
- **WHEN** Agent 构建天气上下文时用户无 `user_settings` 记录
- **THEN** 系统使用 config.yaml 中的默认坐标，不报错

### Requirement: 读取用户设置
系统 SHALL 通过 `GET /settings` 返回当前用户的完整设置，包含 `display_name`、`default_city`、`default_lat`、`default_lon`。

#### Scenario: 已有设置的用户获取设置
- **WHEN** 用户已登录且 `user_settings` 表中有该用户记录
- **THEN** 系统返回 `{ display_name: "农友", default_city: "苏州", default_lat: 31.3, default_lon: 120.62 }`

#### Scenario: 未认证用户访问
- **WHEN** 请求不带有效 JWT token
- **THEN** 系统返回 401 Unauthorized

### Requirement: 更新用户设置
系统 SHALL 通过 `PUT /settings` 接受部分更新，包含可选字段 `display_name`、`default_city`、`default_lat`、`default_lon`。

#### Scenario: 首次设置城市
- **WHEN** 用户发送 `PUT /settings { default_city: "北京", default_lat: 39.9, default_lon: 116.41 }` 且表中无该用户记录
- **THEN** 系统创建 `user_settings` 记录并返回完整设置

#### Scenario: 更新已有设置
- **WHEN** 用户发送 `PUT /settings { default_city: "杭州" }` 且已有记录
- **THEN** 系统只更新 `default_city` 字段，其他字段不变，`updated_at` 自动刷新

#### Scenario: 城市名和坐标必须同时传入
- **WHEN** 用户发送 `PUT /settings { default_city: "苏州" }` 但缺少 `default_lat` 或 `default_lon`
- **THEN** 系统接受请求（允许只更新城市名，坐标保持原值或为 null）

### Requirement: 设置记录的自动创建
系统 SHALL 在首次 `PUT /settings` 包含城市信息时自动创建 `user_settings` 记录，通过 `user_id` 关联到 `users` 表。

#### Scenario: 注册后首次同步设置
- **WHEN** 新注册用户首次调用 `PUT /settings` 带城市信息
- **THEN** 系统创建新记录并关联到该用户的 `user_id`
