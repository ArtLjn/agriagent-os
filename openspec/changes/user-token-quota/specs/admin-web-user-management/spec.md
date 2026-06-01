## MODIFIED Requirements

### 用户列表页表格列定义
用户管理页面 SHALL 在表格中新增配额相关列。

#### Scenario: 月配额列
- **WHEN** 用户列表加载完成
- **THEN** 表格新增"月用量/月限额"列，显示进度条（已用/限额），颜色随百分比变化

#### Scenario: 周配额列
- **WHEN** 用户列表加载完成
- **THEN** 表格新增"周用量/周限额"列，显示进度条

## ADDED Requirements

### Requirement: 用户详情弹窗配额编辑
用户详情弹窗 SHALL 展示配额信息并支持管理员修改。

#### Scenario: 展示配额详情
- **WHEN** 管理员打开用户详情弹窗
- **THEN** 弹窗中新增"Token 配额"区块，展示月限额、月已用、月剩余、周限额、周已用、周剩余

#### Scenario: 修改月限额
- **WHEN** 管理员在配额区块修改月限额数值并保存
- **THEN** 调用 PUT /admin/users/{user_id}/quota 更新配额，刷新展示

#### Scenario: 恢复默认配额
- **WHEN** 管理员清空限额输入框并保存
- **THEN** 提交 null 值，用户回退到全局默认配额
