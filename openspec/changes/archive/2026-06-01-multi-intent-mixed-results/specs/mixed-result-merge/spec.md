## ADDED Requirements

### Requirement: Mixed query+write results merged into single response
When `_llm_node` receives ToolMessages containing both pending (PENDING_MARKER) and non-pending results, the system SHALL compose a combined AIMessage without calling the LLM. The message SHALL contain: non-pending tool result summaries followed by the pending action confirmation prompt.

#### Scenario: Weather query + crop creation in one message
- **WHEN** user sends "今天天气怎么样，我想种玉米"
- **AND** LLM calls both `weather` and `create_crop_cycle`
- **AND** `_parallel_tool_node` returns one normal ToolMessage (weather) and one PENDING_MARKER ToolMessage (crop cycle)
- **THEN** `_llm_node` SHALL compose a response containing both the weather summary and "要帮你创建茬口：玉米，确认吗？"
- **AND** the response SHALL NOT call the LLM

#### Scenario: Pure write intent still works as before
- **WHEN** user sends "帮我记一笔50块化肥"
- **AND** LLM calls only `create_cost_record`
- **AND** `_parallel_tool_node` returns only PENDING_MARKER ToolMessage
- **THEN** `_llm_node` SHALL return only the confirmation text (no query results)
- **AND** the response SHALL NOT call the LLM

#### Scenario: Pure query intent still works as before
- **WHEN** user sends "今天天气怎么样"
- **AND** LLM calls only `weather`
- **AND** `_parallel_tool_node` returns only normal ToolMessage
- **THEN** `_llm_node` SHALL call the LLM to generate a natural language response from the tool result

### Requirement: Non-pending result summary truncation
When composing mixed results, non-pending ToolMessage content SHALL be truncated to a maximum of 300 characters to keep the response concise for mobile display.

#### Scenario: Long query result gets truncated
- **WHEN** a non-pending ToolMessage contains 500 characters of weather data
- **THEN** the merged response SHALL include only the first 300 characters of that result

### Requirement: Confirmation parameters displayed in human-readable format
`build_confirm_message` SHALL map parameter names to human-readable labels for common skill parameters.

#### Scenario: Crop cycle creation with readable params
- **WHEN** pending action is `create_crop_cycle` with params `{crop_name: "玉米", season: "春季"}`
- **THEN** confirmation text SHALL read "要帮你创建茬口：玉米、春季，确认吗？" instead of "crop_name=玉米、season=春季"

#### Scenario: Cost record with readable params
- **WHEN** pending action is `create_cost_record` with params `{amount: 50, category: "化肥"}`
- **THEN** confirmation text SHALL read "要帮你记账：化肥 50元，确认吗？"
