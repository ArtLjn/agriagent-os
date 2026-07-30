## ADDED Requirements

### Requirement: 重置码重设密码
认证模块 SHALL 提供公开接口，允许用户使用账号/手机号、一次性重置码和新密码重设密码。该接口 SHALL 不要求已登录，但必须校验重置码有效性。

#### Scenario: 使用有效重置码重设密码
- **WHEN** 用户提交账号/手机号、有效重置码、新密码和确认密码
- **THEN** 系统 SHALL 更新该用户的 password_hash，标记重置码已使用，并允许用户使用新密码登录

#### Scenario: 新密码不符合规则
- **WHEN** 用户提交的新密码不满足密码强度或长度要求
- **THEN** 系统 SHALL 拒绝重设密码，并保持原密码可用

#### Scenario: 重置码无效
- **WHEN** 用户提交错误、过期、已使用或不属于该账号的重置码
- **THEN** 系统 SHALL 拒绝重设密码，并返回不泄露具体原因的结构化错误

### Requirement: 不恢复原密码
系统 SHALL 永远不返回、展示或恢复用户原密码。忘记密码流程 SHALL 只能设置新密码。

#### Scenario: 管理员查看用户
- **WHEN** 管理员查看用户详情或找回申请
- **THEN** 系统 SHALL 不返回 password_hash 或任何明文密码

#### Scenario: 用户找回密码
- **WHEN** 用户声明忘记密码
- **THEN** 系统 SHALL 引导用户重设新密码，而不是找回旧密码
