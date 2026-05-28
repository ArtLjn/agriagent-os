## MODIFIED Requirements

### Requirement: Function Calling 链路端到端可用
当使用支持 FC 的模型（如 `qwen3.6-flash`）且 `enable_thinking` 为 `false` 时，LangGraph 的 `_llm_node` SHALL 在调用 `bind_tools()` 前先调用 `select_tools()` 预筛选 Tool，仅将筛选后的候选 Tool 子集注入 LLM。当 `select_tools()` 返回全量列表（fallback）时，行为与修改前一致。`_llm_node` SHALL 在 LLM 返回后以 INFO 级别记录工具选择决策。

#### Scenario: 用户询问天气触发 tool call（预筛后）
- **WHEN** 用户发送"明天天气怎么样"且 `select_tools` 返回 `[get_weather_forecast]`
- **THEN** `bind_tools()` 仅注入 1 个 Tool，LLM 返回 `tool_calls` 包含 `get_weather_forecast`

#### Scenario: 用户记账触发 tool call（regex 预筛）
- **WHEN** 用户发送"卖了西瓜5000块"且 `select_tools` 通过 regex 命中 `create_cost_record`
- **THEN** `bind_tools()` 注入该 Tool，LLM 返回 `tool_calls` 包含 `create_cost_record`

#### Scenario: 用户闲聊不触发 tool call（fallback）
- **WHEN** 用户发送"你好"且 `select_tools` 返回全量 Tool（fallback）
- **THEN** `bind_tools()` 注入全量 Tool，LLM 直接回复文本，不触发任何 skill

#### Scenario: 多 skill 并行调用（预筛后）
- **WHEN** 用户发送"看看天气和成本"且 `select_tools` 返回 `[get_weather_forecast, get_cost_summary]`
- **THEN** LLM 返回多个 `tool_calls`，`_parallel_tool_node` 并行执行两个 skill
