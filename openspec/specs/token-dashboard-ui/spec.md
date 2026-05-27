## ADDED Requirements

### Requirement: Token 用量概览
系统 SHALL 提供 `/dev/tokens` 页面，展示 Token 用量概览：总用量、总请求数、配额使用百分比、近 N 天趋势折线图。

#### Scenario: 默认展示近 7 天
- **WHEN** 用户进入 `/dev/tokens` 页面
- **THEN** 顶部展示 4 个统计卡片（总 tokens、总请求数、今日用量、配额剩余百分比），下方展示近 7 天 daily token 用量折线图

#### Scenario: 切换时间范围
- **WHEN** 用户选择"近 30 天"
- **THEN** 统计卡片和折线图更新为近 30 天数据

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
