## Purpose

定义 token-dashboard-ui 能力的行为要求。
## Requirements
### Requirement: Token 用量概览
系统 SHALL 提供 `/dev/tokens` 页面，展示 Token 用量概览：总用量、总请求数、月/周配额进度、按模型趋势图，支持按用户筛选。

#### Scenario: 默认展示近 7 天全量统计
- **WHEN** 用户进入 `/dev/tokens` 页面
- **THEN** 顶部展示统计卡片（总 tokens、总请求数、全局默认月配额进度条、全局默认周配额进度条），下方展示近 7 天趋势图

#### Scenario: 切换时间范围
- **WHEN** 用户选择"近 30 天"
- **THEN** 统计卡片和趋势图更新为近 30 天数据

#### Scenario: 按用户筛选
- **WHEN** 用户在用户选择器中选择某个用户
- **THEN** 所有统计数据（卡片、图表、明细表）仅展示该用户的数据

#### Scenario: 未选择用户时展示全量
- **WHEN** 用户选择器为"全部用户"
- **THEN** 展示所有用户的汇总统计
- **AND** API 请求 SHALL 不传 user_id 或 farm_id

### Requirement: 按模型分组统计
系统 SHALL 在 Token Dashboard 中展示按模型分组的用量统计。

#### Scenario: 模型分组柱状图
- **WHEN** Token Dashboard 加载完成
- **THEN** 展示柱状图，每个模型一组，区分 prompt_tokens 和 completion_tokens（堆叠或分组）

#### Scenario: 模型明细表
- **WHEN** 页面展示完成
- **THEN** 下方表格按模型列出：模型名、总 tokens、请求数、预估费用

### Requirement: 配额状态指示
系统 SHALL 展示当日 Token 配额使用状态。

#### Scenario: 配额正常
- **WHEN** 今日用量 < 配额的 80%
- **THEN** 配额卡片显示绿色进度条，文字"正常"

#### Scenario: 配额接近上限
- **WHEN** 今日用量 >= 配额的 80% 且 < 100%
- **THEN** 配额卡片显示橙色进度条，文字"接近上限"

#### Scenario: 配额已超
- **WHEN** 今日用量 >= 配额的 100%
- **THEN** 配额卡片显示红色进度条，文字"已超限"

### Requirement: 指定日期明细
系统 SHALL 支持查看指定日期的 Token 用量明细（按模型和调用类型分组）。

#### Scenario: 点击某天查看明细
- **WHEN** 用户在折线图上点击某一天
- **THEN** 下方展示该天的明细表格：模型、调用类型（chat/daily_advice/report）、prompt_tokens、completion_tokens、请求数

### Requirement: 月/周配额进度展示
系统 SHALL 在 Token Dashboard 顶部展示当前月和周配额使用进度。

#### Scenario: 配额进度条
- **WHEN** Dashboard 加载完成
- **THEN** 展示月配额进度条（已用/限额）和周配额进度条，颜色：绿色 <60%，黄色 60-80%，红色 >80%

#### Scenario: 配额数据来源
- **WHEN** 选中某用户
- **THEN** 进度条使用该用户的个人配额限额；未选中时使用全局默认限额

### Requirement: Token 配置展示同步
配置页面 SHALL 展示后端返回的月/周默认 token 配额，并使用统一的 warn/reject 超额动作枚举。

#### Scenario: 展示月/周默认限额
- **WHEN** 管理员进入配置页面
- **THEN** Token 配额区块 SHALL 展示 monthly_limit 和 weekly_limit
- **AND** 不再展示旧的 daily_limit 作为主要配额

#### Scenario: 展示 reject 动作
- **WHEN** 后端返回 token_quota.over_quota_action 为 "reject"
- **THEN** 前端 SHALL 显示拒绝调用状态

