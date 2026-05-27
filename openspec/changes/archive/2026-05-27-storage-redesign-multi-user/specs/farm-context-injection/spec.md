## MODIFIED Requirements

### Requirement: 农场上下文摘要构建
farm_context_service.build_summary SHALL 通过 user_id → farms 查找农场信息，display_name 改为从 users.nickname 获取。

#### Scenario: 构建带用户昵称的上下文
- **WHEN** 调用 `build_summary(db, farm_id=...)`，关联用户的 nickname="老李"
- **THEN** 摘要中使用 "老李" 作为用户称呼
