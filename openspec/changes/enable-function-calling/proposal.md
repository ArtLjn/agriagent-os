## Why

当前使用的 `qwen-flash-character` 模型是角色扮演专用模型，**不支持 Function Calling**。经 spike 验证，`bind_tools()` + `tool_choice="required"` 完全无效，LLM 从未通过 tool calling 调用过任何 skill。这意味着 LangGraph 中的 skill 执行机制一直静默失效，用户获取的天气、成本等数据可能来自 LLM 编造而非真实 skill 调用。

## What Changes

- **将默认 LLM 从 `qwen-flash-character` 切换为 `qwen3.6-flash`**
- 新增 `enable_thinking` 配置项，默认 `false`（qwen3 系列在思考模式下不支持 `tool_choice`，且延迟从 ~500ms 飙升至 ~5s）
- 在 `ChatOpenAI` 初始化时通过 `model_kwargs` 或 `extra_body` 传递 `enable_thinking` 参数
- 验证现有 5 个 skill 的 tool calling 链路端到端可用
- **BREAKING**: `qwen3.6-flash` 的语气/风格与 character 模型不同，system prompt 可能需要微调以保持"农事顾问"角色感

## Capabilities

### New Capabilities
- `llm-tool-calling`: LLM 通过 OpenAI 兼容的 function calling 协议调用 skill，包含 tool_choice 约束、thinking 模式配置、以及端到端验证

### Modified Capabilities
- `prompt-template-management`: system prompt 需要强化 tool calling 指令（当前措辞"请主动调用"太软），确保 LLM 优先调 tool 而非编造数据

## Impact

- **配置文件** `config.yaml`: 新增 `ai.enable_thinking` 字段，`ai.model` 默认值变更
- **核心代码** `app/core/config.py`: `AIConfig` 新增字段
- **核心代码** `app/core/llm.py`: `get_llm()` 需传递 `extra_body` 参数
- **Prompt** `prompts/base.j2`: 强化 tool calling 指令
- **依赖**: 无新依赖，`langchain-openai` 的 `ChatOpenAI` 已支持 `extra_body`
- **下游影响**: 所有依赖 `get_llm()` 的模块（agent graph、report、streaming）自动生效
