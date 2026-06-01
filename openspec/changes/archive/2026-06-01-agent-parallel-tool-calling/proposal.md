## Why

当前 Agent 的 Skill 执行层已通过 `asyncio.gather` 支持并行，但 LLM 层面（Qwen 模型）通过 DashScope OpenAI 兼容接口时，通常只返回单个 tool_call，无法触发并行执行。用户同时询问天气和成本等场景时，LLM 串行调用多个 Skill，响应时间翻倍。需要从模型选择、prompt 引导、bind_tools 配置三个层面确保并行 tool calling 稳定生效。

## What Changes

- `bind_tools()` 显式传入 `parallel_tool_calls=True`，确保 OpenAI 兼容接口启用并行
- Agent system prompt 增加并行调用引导指令，告诉 LLM 可以一次返回多个 tool_calls
- `_parallel_tool_node` 增加并行执行的 trace 日志，记录并行数和各 Skill 耗时
- 增加 `parallel_tool_calls` 配置项，支持按模型开关（某些模型不支持并行时回退串行）

## Capabilities

### New Capabilities
- `parallel-tool-execution`: LLM 并行 tool calling 配置、prompt 引导、trace 日志增强

### Modified Capabilities
- `llm-tool-calling`: 增加 `parallel_tool_calls` 参数传递和配置开关

## Impact

- **后端代码**: `app/agent/graph.py`（bind_tools 调用、system prompt）、`app/agent/llm.py`（LLM 配置）、`app/core/config.py`（新增配置项）
- **依赖**: 无新增依赖，使用 LangChain 已有的 `parallel_tool_calls` 参数
- **兼容性**: Qwen 旧模型可能不支持并行，需要配置开关回退串行
