## ADDED Requirements

### Requirement: Python Skill description 使用意图场景描述格式
每个 Python Skill 的 `description` 属性 SHALL 使用"当用户说/问 X 时使用此工具获取/执行 Y"的意图场景描述格式，覆盖该 skill 处理的典型用户口语表达。description SHALL 包含足够的关键词和场景描述，使小模型（如 qwen3.6-flash）能将用户输入准确映射到对应 tool。

#### Scenario: "我的余额" 触发 get_cost_summary
- **WHEN** 用户发送"我的余额"
- **THEN** LLM 返回 `tool_calls` 包含 `get_cost_summary`

#### Scenario: "帮我创建春茬种植西瓜" 触发 create_crop_cycle
- **WHEN** 用户发送"帮我创建春茬种植西瓜"
- **THEN** LLM 返回 `tool_calls` 包含 `create_crop_cycle`

#### Scenario: "花了多少钱" 触发 get_cost_summary
- **WHEN** 用户发送"这个月花了多少钱"
- **THEN** LLM 返回 `tool_calls` 包含 `get_cost_summary`

#### Scenario: "帮我记一笔化肥200块" 触发 create_cost_record
- **WHEN** 用户发送"帮我记一笔化肥200块"
- **THEN** LLM 返回 `tool_calls` 包含 `create_cost_record`

#### Scenario: "进苗期了" 触发 update_crop_stage
- **WHEN** 用户发送"西瓜进苗期了"
- **THEN** LLM 返回 `tool_calls` 包含 `update_crop_stage`

### Requirement: System prompt 包含可用工具映射表
`base.j2` 的工具调用规则段落 SHALL 包含一个【可用工具】映射表，列出所有 tool 名称和对应的用户意图关键词。映射表 SHALL 与 `get_langchain_tools()` 返回的工具列表保持一致。

#### Scenario: prompt 包含所有 tool 映射
- **WHEN** 检查 `base.j2` 内容
- **THEN** 包含所有 10 个 tool 的名称和意图描述：get_weather_forecast、get_cost_summary、get_cost_analytics、create_cost_record、create_crop_cycle、get_crop_cycle_info、get_recent_farm_logs、log_farm_activity、update_crop_stage、settle_debt

#### Scenario: 新增 skill 后映射表可维护
- **WHEN** 开发者新增一个 Python Skill
- **THEN** 只需更新该 Skill 的 description 和 `base.j2` 中的映射条目
