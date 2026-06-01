# structured-output-parsing Specification

## Purpose
TBD - created by archiving change structured-output-parse. Update Purpose after archive.
## Requirements
### Requirement: 解析端点使用 structured output
`/crops/templates/parse`、`/cycles/parse`、`/costs/parse` 三个端点 SHALL 使用 `get_llm().with_structured_output(Schema)` 替代 `get_llm() → ainvoke → safe_parse_json → model_validate` 的手动解析链路。LLM SHALL 通过 Function Calling 直接返回符合 Pydantic schema 的结构化对象。

#### Scenario: 正常解析作物模板
- **WHEN** 用户发送 `POST /crops/templates/parse` 请求 `{"description": "我要种西瓜"}`
- **THEN** 系统通过 `with_structured_output(CropTemplateParseResponse)` 获得类型安全的 Pydantic 对象
- **AND** 返回 200 + 结构化 JSON，无需经过 `safe_parse_json`

#### Scenario: 正常解析茬口
- **WHEN** 用户发送 `POST /cycles/parse` 请求 `{"description": "种一季西瓜"}`
- **THEN** 系统通过 `with_structured_output(CycleParseResponse)` 获得类型安全的 Pydantic 对象

#### Scenario: 正常解析记账
- **WHEN** 用户发送 `POST /costs/parse` 请求 `{"description": "昨天买了200块化肥"}`
- **THEN** 系统通过 `with_structured_output(CostParseResult)` 获得类型安全的 Pydantic 对象

### Requirement: structured output 失败时 fallback 到 safe_parse_json
如果 `with_structured_output` 抛出异常（如 provider 不支持 tool_choice），系统 SHALL 回退到当前的 `safe_parse_json` + `model_validate` 逻辑，确保功能不中断。

#### Scenario: provider 不支持 tool_choice
- **WHEN** 当前 LLM provider 不支持 Function Calling，`with_structured_output` 抛异常
- **THEN** 系统回退到 `safe_parse_json` 解析 LLM 文本输出
- **AND** 记录 warning 日志标记使用了 fallback 路径

#### Scenario: structured output 返回类型错误
- **WHEN** `with_structured_output` 返回的对象无法转为目标 Pydantic 类型
- **THEN** 系统回退到 `safe_parse_json` 解析
- **AND** 返回正常 HTTP 响应（不返回 500）

### Requirement: 不影响 API 接口契约
三个解析端点的请求和响应 schema SHALL 保持不变。前端无需修改。

#### Scenario: 请求格式不变
- **WHEN** 前端发送 `POST /crops/templates/parse` 请求
- **THEN** 请求 body 格式和 response 格式与改造前完全一致

### Requirement: 每日建议不走此方案
`agent_service.py` 中的每日建议解析走 LangGraph Agent 图，不适用 `with_structured_output`，SHALL 保持现有 `safe_parse_json` 逻辑。

#### Scenario: 每日建议仍用 safe_parse_json
- **WHEN** `_parse_advice_items()` 解析 Agent 返回的建议文本
- **THEN** 继续使用 `safe_parse_json` 解析，不使用 `with_structured_output`

