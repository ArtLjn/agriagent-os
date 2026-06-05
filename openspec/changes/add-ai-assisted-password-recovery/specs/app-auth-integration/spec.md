## ADDED Requirements

### Requirement: 登录页密码找回入口
FarmManagerMobile SHALL 在登录页提供密码找回入口，优先引导用户通过 AI 客服提交找回申请，并提供使用重置码修改密码的入口。

#### Scenario: 打开 AI 客服找回
- **WHEN** 用户在登录页点击“忘记密码？问问小助手”
- **THEN** App SHALL 打开 AI 客服找回流程，提示用户提供账号手机号、昵称或备注信息

#### Scenario: 打开重置码改密
- **WHEN** 用户已从管理员处获得重置码
- **THEN** 用户 SHALL 能进入“使用重置码修改密码”页面

### Requirement: 重置码改密页面
FarmManagerMobile SHALL 提供重置码改密页面，允许用户输入账号/手机号、重置码、新密码和确认新密码。

#### Scenario: 重置成功
- **WHEN** 用户提交有效账号/手机号、重置码和新密码
- **THEN** App SHALL 展示重置成功提示，并引导用户使用新密码登录

#### Scenario: 重置失败
- **WHEN** 后端返回重置码错误、过期、已使用或新密码无效
- **THEN** App SHALL 展示不泄露具体敏感原因的错误提示，并允许用户重新输入

### Requirement: AI 客服找回申请体验
FarmManagerMobile SHALL 在 AI 客服找回流程中清楚告知用户：AI 只负责提交申请，管理员确认后才会提供重置码。

#### Scenario: 申请提交成功
- **WHEN** AI 客服成功创建找回申请
- **THEN** App SHALL 展示“申请已提交，管理员处理后会给你重置码”的提示

#### Scenario: 用户要求 AI 直接改密
- **WHEN** 用户要求 AI 客服直接修改密码
- **THEN** App SHALL 展示 AI 客服拒绝直接改密并说明管理员处理流程的回复
