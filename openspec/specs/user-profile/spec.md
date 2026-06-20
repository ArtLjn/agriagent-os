## Purpose

定义 user-profile 能力的行为要求。

## Requirements

### Requirement: 用户画像存储
`users` 表 SHALL 存储用户基本信息：nickname（昵称，AI 使用此字段称呼用户）、avatar_url（头像）、role（角色，默认"user"）。

#### Scenario: 注册时设置昵称
- **WHEN** 用户注册时提供 nickname="老李"
- **THEN** users 表记录 nickname="老李"

#### Scenario: 注册时未提供昵称
- **WHEN** 用户注册时未提供 nickname
- **THEN** users 表记录 nickname 为手机号后四位（如"8001"）

### Requirement: AI 称呼来源从 users 获取
`<user_context>` 段的 `<name>` 标签 SHALL 从 `users.nickname` 读取，不再从 `farms.display_name` 读取。

#### Scenario: 用户昵称注入 prompt
- **WHEN** 用户 nickname="老李"，发送消息
- **THEN** system prompt 包含 `<user_context><name>老李</name>...</user_context>`

### Requirement: 获取当前用户信息
系统 SHALL 提供 `GET /auth/me` 接口返回当前登录用户的基本信息（nickname、avatar_url、phone 脱敏、关联的 farm 信息）。返回的 farm location SHALL 表示当前账号默认农场的经营地区，并作为新客户端展示“经营地区/农场地区”的权威来源。

#### Scenario: 获取用户信息
- **WHEN** 用户携带有效 token 请求 `GET /auth/me`
- **THEN** 返回 `{"nickname": "老李", "phone": "138****8001", "farm": {"id": "...", "name": "我的农场", "location": "苏州"}}`

#### Scenario: 经营地区为空
- **WHEN** 用户携带有效 token 请求 `GET /auth/me` 且默认农场 location 为空
- **THEN** 返回的 farm location 为空，客户端 SHALL 将该账号视为需要首次地区设置

### Requirement: 更新默认农场经营地区
系统 SHALL 提供受认证保护的流程允许当前用户更新自己默认农场的经营地区。更新成功后，后续用户资料、天气查询、AI 今日建议和农事提醒 SHALL 使用新的经营地区。

#### Scenario: 手动修改经营地区
- **WHEN** 当前用户将默认农场经营地区从"睢宁县"修改为"邳州市"
- **THEN** 系统保存默认农场 location="邳州市"，并在后续 `GET /auth/me` 中返回该地区

#### Scenario: 禁止修改他人农场地区
- **WHEN** 用户尝试修改不属于自己账号的 farm location
- **THEN** 系统返回 403 Forbidden，并包含错误 code

#### Scenario: 修改经营地区后清理上下文
- **WHEN** 当前用户默认农场经营地区更新成功
- **THEN** 系统 SHALL 清理该 farm 相关天气、农场上下文和 Agent 摘要缓存

### Requirement: 更新用户信息
系统 SHALL 提供 `PUT /auth/me` 接口允许用户更新 nickname 和 avatar_url。

#### Scenario: 更新昵称
- **WHEN** 用户提交 `PUT /auth/me`，body 为 `{"nickname": "李大哥"}`
- **THEN** users 表更新 nickname，后续 AI 对话使用新称呼
