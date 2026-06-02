## ADDED Requirements

### Requirement: Playground 用户选择器
Chat Playground 的配置栏 SHALL 提供一个用户身份选择下拉框。

#### Scenario: 加载用户列表
- **WHEN** Playground 页面加载时
- **THEN** 系统 SHALL 调用用户列表接口获取可用用户
- **AND** 在下拉框中展示用户昵称/用户名
- **AND** 默认选中「匿名用户」或第一个可用用户

#### Scenario: 切换用户
- **WHEN** 用户从下拉框中选择不同用户
- **THEN** 系统 SHALL 更新当前选中用户状态
- **AND** 新发送的消息 SHALL 携带该用户的 `user_id`

### Requirement: 匿名模式兼容
当未选择特定用户时，系统 SHALL 保持现有匿名行为，不破坏向后兼容。

#### Scenario: 匿名发送
- **WHEN** 用户选择「匿名用户」或未做任何选择
- **THEN** 消息 SHALL 不携带 `user_id` 参数
- **AND** Agent SHALL 按现有逻辑处理（使用默认 farm_id=1）

### Requirement: 用户上下文生效
选中用户后发送的消息，Agent SHALL 使用该用户的农场上下文进行回复。

#### Scenario: 用户上下文注入
- **WHEN** 用户选择用户 A 并发送消息
- **THEN** Agent SHALL 加载用户 A 关联的农场数据
- **AND** 回复内容 SHALL 基于用户 A 的农场上下文生成
