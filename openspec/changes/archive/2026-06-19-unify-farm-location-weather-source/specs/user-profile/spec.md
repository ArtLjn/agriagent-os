## MODIFIED Requirements

### Requirement: 获取当前用户信息
系统 SHALL 提供 `GET /auth/me` 接口返回当前登录用户的基本信息（nickname、avatar_url、phone 脱敏、关联的 farm 信息）。返回的 farm location SHALL 表示当前账号默认农场的经营地区，并作为新客户端展示“经营地区/农场地区”的权威来源。

#### Scenario: 获取用户信息
- **WHEN** 用户携带有效 token 请求 `GET /auth/me`
- **THEN** 返回 `{"nickname": "老李", "phone": "138****8001", "farm": {"id": "...", "name": "我的农场", "location": "苏州"}}`

#### Scenario: 经营地区为空
- **WHEN** 用户携带有效 token 请求 `GET /auth/me` 且默认农场 location 为空
- **THEN** 返回的 farm location 为空，客户端 SHALL 将该账号视为需要首次地区设置

## ADDED Requirements

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
