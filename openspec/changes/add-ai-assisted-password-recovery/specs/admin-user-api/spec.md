## ADDED Requirements

### Requirement: 管理员处理密码找回申请
系统 SHALL 提供管理员 API 查看和处理密码找回申请。

#### Scenario: 查询找回申请列表
- **WHEN** 管理员请求找回申请列表
- **THEN** 系统 SHALL 返回分页申请列表，包含申请状态、用户输入线索、关联用户、创建时间和处理时间

#### Scenario: 非管理员禁止查询找回申请
- **WHEN** 非管理员请求找回申请列表
- **THEN** 系统 SHALL 返回 403

#### Scenario: 关联申请到用户
- **WHEN** 管理员选择某个用户作为找回申请的匹配账号
- **THEN** 系统 SHALL 保存关联用户 ID、处理管理员 ID 和备注

#### Scenario: 拒绝找回申请
- **WHEN** 管理员拒绝找回申请并填写原因
- **THEN** 系统 SHALL 将申请状态更新为 `rejected`

### Requirement: 管理员生成密码重置码
系统 SHALL 提供管理员 API 为指定用户生成一次性密码重置码。

#### Scenario: 为申请生成重置码
- **WHEN** 管理员对已关联用户的找回申请生成重置码
- **THEN** 系统 SHALL 创建绑定该用户的一次性重置码，返回明文重置码和过期时间，并将申请状态更新为 `resolved`

#### Scenario: 为用户直接生成重置码
- **WHEN** 管理员在用户详情页直接生成重置码
- **THEN** 系统 SHALL 创建绑定该用户的一次性重置码，并返回明文重置码和过期时间

#### Scenario: 重置码只显示一次
- **WHEN** 管理员生成重置码后刷新页面或再次查询记录
- **THEN** 系统 SHALL 不再返回该重置码明文

#### Scenario: 禁用用户不允许生成重置码
- **WHEN** 管理员尝试为 disabled 用户生成重置码
- **THEN** 系统 SHALL 拒绝生成，并返回结构化错误
