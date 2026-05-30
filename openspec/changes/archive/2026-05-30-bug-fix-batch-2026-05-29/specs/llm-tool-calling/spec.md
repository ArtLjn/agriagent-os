## MODIFIED Requirements

### Requirement: Function Calling 链路端到端可用
当使用支持 FC 的模型时，LangGraph 的 `_llm_node` 中 `bind_tools()` SHALL 正常工作。`_llm_node` SHALL 将用户当前城市（来自 `UserSetting.default_city`）注入 system prompt，使 LLM 在调用天气 skill 时能传递正确的城市参数。

#### Scenario: 天气 skill 获取用户城市
- **WHEN** 用户问"今天天气怎么样"且未指定城市
- **THEN** system prompt 中 SHALL 包含 `UserSetting.default_city` 的值，LLM 据此在 tool call 中传递 `city` 参数

#### Scenario: 用户设置城市为空
- **WHEN** 用户未配置 default_city
- **THEN** 天气 skill SHALL 通过降级机制从 `_get_user_location(farm_id)` 获取位置
