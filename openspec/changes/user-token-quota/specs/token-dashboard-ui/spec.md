## MODIFIED Requirements

### Requirement: Token 用量概览
系统 SHALL 提供 `/dev/tokens` 页面，展示 Token 用量概览：总用量、总请求数、月/周配额进度、按模型趋势图，支持按用户筛选。

#### Scenario: 默认展示近 7 天全量统计
- **WHEN** 用户进入 `/dev/tokens` 页面
- **THEN** 顶部展示统计卡片（总 tokens、总请求数、月配额进度条、周配额进度条），下方展示近 7 天趋势图

#### Scenario: 切换时间范围
- **WHEN** 用户选择"近 30 天"
- **THEN** 统计卡片和趋势图更新为近 30 天数据

#### Scenario: 按用户筛选
- **WHEN** 用户在用户选择器中选择某个用户
- **THEN** 所有统计数据（卡片、图表、明细表）仅展示该用户的数据

#### Scenario: 未选择用户时展示全量
- **WHEN** 用户选择器为"全部用户"
- **THEN** 展示所有用户的汇总统计

## ADDED Requirements

### Requirement: 月/周配额进度展示
系统 SHALL 在 Token Dashboard 顶部展示当前月和周配额使用进度。

#### Scenario: 配额进度条
- **WHEN** Dashboard 加载完成
- **THEN** 展示月配额进度条（已用/限额）和周配额进度条，颜色：绿色 <60%，黄色 60-80%，红色 >80%

#### Scenario: 配额数据来源
- **WHEN** 选中某用户
- **THEN** 进度条使用该用户的个人配额限额；未选中时使用全局默认限额
