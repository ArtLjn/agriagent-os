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
Evaluation SHALL 统计 skill 调用准确率、漏调率、误调率、参数正确率和写操作确认命中率。

#### Scenario: 工具调用参数错误
- **WHEN** 用例期望调用 `create_cost_record` 且金额为 300，但实际参数金额为 30
- **THEN** 评测报告将该用例标记为参数错误

### Requirement: 评测结果可追踪
每次评测运行 SHALL 生成结构化报告，包含运行时间、代码版本、Prompt 版本、配置摘要、用例结果、失败原因和关键指标。

#### Scenario: 生成评测报告
- **WHEN** 评测运行结束
- **THEN** 系统保存包含指标和失败详情的报告，供后续回归对比
