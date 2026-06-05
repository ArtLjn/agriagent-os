## Purpose

定义 admin-web-user-management 能力的行为要求。

# Admin-web 用户管理页面

## 概述
在 admin-web 中新增用户管理模块，供管理员查看和操作注册用户。

## 页面结构

### 用户列表页 (/users)

**布局：**
- 顶部：页面标题"用户管理" + 统计卡片（总用户数、今日新增、活跃用户数、已禁用数）
- 中部：筛选栏（状态筛选下拉框、手机号搜索框）
- 主体：用户数据表格

**表格列定义：**
| 列名 | 数据源 | 展示方式 |
|------|--------|---------|
| 手机号 | phone | 纯文本 |
| 昵称 | nickname | 纯文本 |
| 角色 | role | Tag 组件（user-蓝色/admin-橙色）|
| 状态 | status | Tag 组件（active-绿色/disabled-红色）|
| 注册时间 | created_at | 格式化日期 |
| 农场名 | farm_name | 纯文本 |
| 操作 | - | 查看详情按钮 + 禁用/启用按钮 |

**交互：**
- 点击"查看详情" → 打开用户详情 Modal
- 点击"禁用" → Modal.confirm 二次确认 → 调用 API → 刷新列表
- 点击"启用" → 同上
- 状态筛选变更 → 重新请求列表
- 手机号搜索 → 输入后按回车或防抖 500ms 请求

### 用户详情弹窗

**展示内容：**
- 基础信息：ID、手机号、昵称、头像（如有）、角色、状态、注册时间
- 农场信息：农场名、位置
- 操作按钮：禁用/启用（根据当前状态显示对应按钮）

## 导航集成

更新 `AdminLayout.tsx` 菜单：
- 新增分组"系统管理"
- 新增菜单项：用户管理（icon: TeamOutlined）→ /users

更新 `App.tsx` 路由：
- 新增 `<Route path="/users" element={<Users />} />`

## 技术约束
- 使用现有 Ant Design 组件（Table、Modal、Tag、Button、Input、Select）
- 使用现有 API client（`api/client.ts`）
- 深色主题风格与现有页面一致
## Requirements
### Requirement: 用户详情弹窗配额编辑
用户详情弹窗 SHALL 展示配额信息并支持管理员修改。

#### Scenario: 展示配额详情
- **WHEN** 管理员打开用户详情弹窗
- **THEN** 弹窗中新增"Token 配额"区块，展示月限额、月已用、月剩余、月周期起止、周限额、周已用、周剩余、周周期起止

#### Scenario: 修改月限额
- **WHEN** 管理员在配额区块修改月限额数值并保存
- **THEN** 调用 PUT /admin/users/{user_id}/quota 更新配额，刷新展示

#### Scenario: 恢复默认配额
- **WHEN** 管理员清空限额输入框并保存
- **THEN** 提交 null 值，用户回退到全局默认配额

