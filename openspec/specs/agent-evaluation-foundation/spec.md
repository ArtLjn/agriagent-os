## Purpose

定义 agent-evaluation-foundation 能力的行为要求。
## Requirements
### Requirement: Agent 回放评测
系统 SHALL 支持保存和回放 Agent 测试用例。测试用例 SHALL 包含输入消息、用户上下文、农场上下文、预期 skill 调用、预期写操作和最低回复质量断言。

#### Scenario: 回放单个用例
- **WHEN** 开发者运行指定 Agent 测试用例
- **THEN** 系统使用固定上下文执行请求，并输出实际回复、skill 调用和断言结果

### Requirement: Prompt 回归验证
系统 SHALL 支持对不同 Prompt 版本执行同一组评测用例，并报告回复格式、工具调用、成本和延迟差异。

#### Scenario: 比较两个 Prompt 版本
- **WHEN** 开发者比较 `system_base` 的 v1 和 v2
- **THEN** 系统输出两个版本在相同用例集上的通过率、skill 调用差异和 token 成本差异

### Requirement: Context 质量指标
Evaluation SHALL 能评估上下文命中率、上下文丢弃原因、token 预算使用和检索结果是否被使用。

#### Scenario: 上下文命中率报告
- **WHEN** 评测用例声明需要某个农场事实
- **THEN** 报告标明该事实是否被 Context Builder 注入，以及是否出现在最终回复依据中

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

