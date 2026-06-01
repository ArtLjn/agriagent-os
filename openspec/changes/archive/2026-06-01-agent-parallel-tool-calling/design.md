## Context

当前 Agent 的并行执行能力分为两层：

1. **LLM 层**：Qwen 模型通过 DashScope OpenAI 兼容接口调用。`ChatOpenAI` 未显式传入 `parallel_tool_calls` 参数，导致即使模型支持也未被启用。实测 Qwen 通常只返回单个 `tool_call`，多 Skill 场景下串行调用，响应时间翻倍。
2. **执行层**：`_parallel_tool_node` 已通过 `asyncio.gather` 支持并行（graph.py:425-429），但前提是 LLM 必须一次返回多个 `tool_calls`。

核心问题在 LLM 层——模型不返回多个 `tool_calls`，执行层的并行能力就无法触发。

关键代码位置：
- `bind_tools()` 调用：`graph.py:246`，未传 `parallel_tool_calls`
- `get_llm()` 构建：`llm.py:25-70`，未设 `parallel_tool_calls`
- `_parallel_tool_node`：`graph.py:338-431`，已有 `asyncio.gather`
- 配置：`config.py:48-53` AIConfig，无 `parallel_tool_calls` 字段

## Goals / Non-Goals

**Goals:**
- 确保 LLM 在用户同时询问多个独立问题（如"今天天气怎么样？顺便看看我这个月花了多少钱"）时，一次返回多个 `tool_calls`
- 通过 `bind_tools(parallel_tool_calls=True)` + prompt 引导双管齐下，最大化并行触发率
- 并行执行的 trace 日志记录并行数和各 Skill 耗时，便于观测优化效果
- 支持按模型配置开关，旧模型不支持并行时可回退串行

**Non-Goals:**
- 不修改 `_parallel_tool_node` 的执行逻辑（已支持并行）
- 不引入新的 LLM provider（仍使用 DashScope）
- 不实现 LLM 层面的 fallback（模型不支持并行时只是串行，不需要降级到其他模型）

## Decisions

### D1: 在 `bind_tools()` 层传入 `parallel_tool_calls=True`

**选择**：在 `graph.py:246` 的 `llm.bind_tools(selected_tools)` 调用中添加 `parallel_tool_calls=True`。

**理由**：LangChain 的 `ChatOpenAI.bind_tools()` 支持 `parallel_tool_calls` 参数，会透传到 OpenAI API 的 `tool_choice` 配置。这是最直接的启用方式。

**替代方案**：
- 在 `ChatOpenAI` 构造函数设置：影响全局，不灵活。弃用。
- 不设参数，仅靠 prompt 引导：不稳定，模型可能仍只返回单 tool_call。弃用。

### D2: System prompt 增加并行调用引导指令

**选择**：在 system prompt 模板（通过 PromptComposer snippet）中增加一段引导文本。

**内容**：
```
当用户的问题需要调用多个工具时，你应该在一次回复中同时返回所有需要的工具调用，
而不是逐个调用。例如用户同时问天气和成本，你应该同时调用天气和成本查询工具。
```

**理由**：`parallel_tool_calls=True` 是 API 层面的"允许"，但模型仍可能选择串行。prompt 引导能显著提高模型一次返回多个 tool_calls 的概率。

**替代方案**：
- 不加引导：依赖模型自行判断，触发率低。弃用。
- 用 few-shot 示例：system prompt 已较长，加示例会使 token 消耗增加过多。弃用。

### D3: `parallel_tool_calls` 作为 AIConfig 字段，而非硬编码

**选择**：在 `config.py` 的 `AIConfig` 中添加 `parallel_tool_calls: bool = True`，`graph.py` 读取该配置决定是否传入。

**理由**：
- Qwen 旧模型（如 qwen-plus）可能不支持并行，需要运行时关闭
- 配置化比硬编码更灵活，无需改代码即可切换
- 默认 `True`，新模型默认启用

### D4: 并行执行 trace 增强在 `_parallel_tool_node` 中实现

**选择**：在 `_parallel_tool_node` 并行执行后，记录一条聚合 trace 日志，包含并行数、各 Skill 名称和耗时。

**实现**：
```python
# asyncio.gather 完成后
if len(results) > 1:
    parallel_info = {
        "parallel_count": len(results),
        "skills": [{"name": n, "duration_ms": d} for n, d in skill_timings],
    }
    collector.record(
        node_type="parallel_batch",
        node_name=f"parallel_{len(results)}_skills",
        output_data=parallel_info,
        duration_ms=sum(d for _, d in skill_timings),
    )
```

**理由**：不修改每个 Skill 的 trace 记录（已有），额外加一条聚合记录，便于在 Trace Monitor 中观察并行效果。

## Risks / Trade-offs

- **[Qwen 模型可能忽略 parallel_tool_calls 参数]** → Mitigation: prompt 引导作为第二层保障；配置开关允许关闭；即使模型不返回多个 tool_calls，串行执行不受影响，只是没有加速效果。
- **[并行 Skill 结果拼接顺序不确定]** → Mitigation: `_parallel_tool_node` 已按 tool_call 顺序返回 `ToolMessage`，LLM 会根据各结果自行整合，无需特殊处理。
- **[并行 Skill 中有写操作]** → Mitigation: 写操作已被 `_parallel_tool_node` 拦截为 pending action（graph.py:356-375），不会真正并行执行写操作，仅并行执行读操作。
- **[prompt 引导增加 system prompt 长度]** → Mitigation: 引导文本约 80 字，相比现有 system prompt 可忽略。
