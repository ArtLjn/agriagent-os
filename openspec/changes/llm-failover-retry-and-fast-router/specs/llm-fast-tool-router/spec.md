## ADDED Requirements

### Requirement: Role-based model selection
`get_llm()` SHALL accept a `role` parameter (`"tool-selection"` or `"generation"`) to select models optimized for that purpose. `LLMClientManager.get_chat_model(role=...)` SHALL filter candidates by role.

#### Scenario: Tool selection uses lightweight model
- **WHEN** `get_llm(role="tool-selection")` is called
- **THEN** Manager returns a model whose `roles` includes `"tool-selection"` or `"all"`, preferring smaller parameter models

#### Scenario: Generation uses high quality model
- **WHEN** `get_llm(role="generation")` is called
- **THEN** Manager returns a model whose `roles` includes `"generation"` or `"all"`, with no size preference

#### Scenario: Backward compatibility without roles field
- **WHEN** a model in `providers.json` has no `roles` field
- **THEN** the model is treated as having `roles: ["all"]` and is available for all purposes

### Requirement: Model roles in providers.json
Each model in `providers.json` SHALL support an optional `roles` array field with values `"tool-selection"`, `"generation"`, or `"all"`.

#### Scenario: Configured model with specific role
- **WHEN** `providers.json` has `{"id": "gemma3:12b", "roles": ["tool-selection"]}`
- **THEN** this model is only selected when `role="tool-selection"` is requested

#### Scenario: Configured model with all roles
- **WHEN** `providers.json` has `{"id": "gemma4:31b", "roles": ["all"]}`
- **THEN** this model is available for both `role="tool-selection"` and `role="generation"`

### Requirement: LLMIntentClassifier uses lightweight model
`LLMIntentClassifier` SHALL use `get_sync_client()` or `get_chat_model()` with `role="tool-selection"` to select a lightweight model for intent classification.

#### Scenario: Classifier gets small model
- **WHEN** `LLMIntentClassifier` is initialized
- **THEN** it uses a model with `"tool-selection"` role, reducing classification latency

### Requirement: _llm_node first call uses tool-selection model
The first LLM call in `_llm_node` (tool selection) SHALL use `get_llm(role="tool-selection")`, and the second call (reply generation after tool results) SHALL use `get_llm(role="generation")`.

#### Scenario: Different models for different phases
- **WHEN** user sends "今天天气怎么样"
- **THEN** first LLM call (selecting get_weather_forecast tool) uses tool-selection model
- **AND** second LLM call (generating reply from weather data) uses generation model
