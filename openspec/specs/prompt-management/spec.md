## Purpose

定义 prompt-management 能力的行为要求。

## Requirements

### Requirement: Prompt 版本化回归
系统 SHALL 为关键 Prompt 组合记录版本，并支持对指定版本执行回放评测。Prompt 变更进入生产前 MUST 至少通过渲染快照测试。

#### Scenario: Prompt 变更前验证
- **WHEN** 开发者修改 system prompt 片段
- **THEN** 系统能够生成新快照并运行相关回放用例

### Requirement: Prompt 片段优先级
Prompt Composer SHALL 支持按优先级组合片段，至少包括安全约束、角色设定、能力边界、工具约束、上下文、输出格式和风格要求。

#### Scenario: 组合 system prompt
- **WHEN** Agent 请求 system prompt
- **THEN** Composer 按配置顺序组合片段，并保证安全约束优先于普通风格要求

### Requirement: Prompt 输入与 Context 解耦
Prompt 渲染 SHALL 接收结构化 PromptInput 或 ContextBundle，而不是在模板渲染过程中直接查询数据库。

#### Scenario: 渲染 Prompt
- **WHEN** Composer 渲染 Agent system prompt
- **THEN** 所需上下文已经由 Context Builder 提供，模板渲染不直接访问数据库
