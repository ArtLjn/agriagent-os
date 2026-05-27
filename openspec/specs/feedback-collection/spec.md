## ADDED Requirements

### Requirement: 用户对 AI 回复评价
系统 SHALL 允许用户对 conversation_messages 中的 assistant 消息提交评价（good/bad），并可选提供修正文本。

#### Scenario: 正面评价
- **WHEN** 用户提交 `POST /agent/feedback`，body 为 `{"message_id": 42, "rating": "good"}`
- **THEN** 系统在 feedback_records 表创建记录，关联 user_id 和 conversation_message_id

#### Scenario: 负面评价带修正
- **WHEN** 用户提交 `POST /agent/feedback`，body 为 `{"message_id": 42, "rating": "bad", "correction": "我种的是豆角不是西瓜"}`
- **THEN** feedback_records 记录 rating="bad" 和 correction 内容

#### Scenario: 重复评价覆盖
- **WHEN** 用户对同一 message_id 提交第二次评价
- **THEN** 系统更新已有记录（不创建新记录）

#### Scenario: 评价不存在的消息
- **WHEN** 用户提交的 message_id 不存在或不属于当前用户
- **THEN** 返回 404

### Requirement: 自学习数据导出
系统 SHALL 提供 `GET /admin/training-data` 接口导出带评价的对话数据为 JSONL 格式，包含完整对话链和用户评价。此接口需要管理员权限。

#### Scenario: 导出训练数据
- **WHEN** 管理员请求 `GET /admin/training-data?rating=good&limit=100`
- **THEN** 返回 JSONL，每行为 `{"messages": [...], "feedback": {"rating": "good"}, "meta": {...}}`

#### Scenario: 非管理员访问
- **WHEN** 普通用户请求 `GET /admin/training-data`
- **THEN** 返回 403
