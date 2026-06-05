## MODIFIED Requirements

### Requirement: Skill 调用质量指标
Evaluation SHALL 统计 skill 调用准确率、漏调率、误调率、参数正确率、写操作确认命中率、修正成功率、取消成功率和执行一致性。

#### Scenario: 工具调用参数错误
- **WHEN** 用例期望调用 `create_cost_record` 且金额为 300，但实际参数金额为 30
- **THEN** 评测报告将该用例标记为参数错误

#### Scenario: 明确修改意图被错误追问
- **WHEN** 用例输入为「修改玉米茬口9月1开始」且上下文中只有一个玉米茬口
- **THEN** 如果 Agent 追问“修改还是新建”而不是生成 `update_crop_cycle` pending action，评测报告将该用例标记为 `unnecessary_clarification`

### Requirement: 评测结果可追踪
每次评测运行 SHALL 生成结构化报告，包含运行时间、代码版本、Prompt 版本、配置摘要、用例结果、失败原因、关键指标、trace 证据和数据库一致性结果。

#### Scenario: 生成评测报告
- **WHEN** 评测运行结束
- **THEN** 系统保存包含指标和失败详情的报告，供后续回归对比

#### Scenario: 写操作一致性证据
- **WHEN** 评测用例包含确认后的写操作
- **THEN** 报告包含执行前后数据库快照摘要和对应 trace request_id
