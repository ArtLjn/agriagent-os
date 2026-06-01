## Context

当前 LangGraph 图的 `_llm_node` 对 pending ToolMessage 的处理是二元的：检测到任何一个 PENDING_MARKER 就跳过 LLM，直接返回确认文案。这在单意图 write 操作时没问题，但多意图场景（query + write 混合 tool call）会丢失 query 结果。

当前图流程：
```
_llm_node → (tool_calls?) → _parallel_tool_node → _llm_node
```

`_parallel_tool_node` 并行处理所有 tool_calls，query skill 直接执行返回结果，write skill 拦截为 pending action 返回 PENDING_MARKER。

## Goals / Non-Goals

**Goals:**
- 多意图消息（query + write 混合）时，query 结果和 write 确认提示都展示给用户
- 不调用 LLM 生成合并回复（避免弱模型幻觉和额外 token 消耗）
- 确认/取消按钮（pending_action SSE 事件）在混合场景下仍然正常工作

**Non-Goals:**
- 不改变 `_parallel_tool_node` 的拦截逻辑（write skill 仍然走 pending）
- 不改变 SSE 事件格式（前端无需改动）
- 不处理三个以上意图的复杂场景（最多 query + write 混合）

## Decisions

### Decision 1: `_llm_node` 三路分支

在 `_llm_node` 开头将 ToolMessage 分为 pending 和 non-pending 两组：

```
全部 pending → 只返回确认文案（当前逻辑，不变）
全部 non-pending → 正常调 LLM 处理 tool results（当前逻辑，不变）
混合 → 拼接 non-pending 摘要 + pending 确认文案，不调 LLM
```

**理由**: 不依赖 LLM 做合并，避免弱模型在长上下文下出错。

**替代方案**: 混合时仍然调 LLM，在 system prompt 里指示"必须包含确认提示"。被否决因为 qwen3.6-flash 不可靠。

### Decision 2: query 结果摘要截取

non-pending ToolMessage 的 content 可能很长（如完整天气 JSON），取前 200 字符作为摘要。

**理由**: 保持回复简洁，手机端友好。

### Decision 3: 确认文案参数可读性优化

`build_confirm_message` 将参数名映射为中文显示名：
- `crop_name=玉米` → `玉米`
- `amount=50, category=化肥` → `化肥 50元`

**理由**: 当前 `crop_name=玉米、season=春季、start_date=2026-05-31` 太技术化。

## Risks / Trade-offs

- [query 结果被截断] → 摘要取 200 字符，可能丢失细节。可接受因为 query skill 的 result.reply 本身就是摘要文本，不是原始数据
- [混合场景下确认后只执行 write 不重新展示 query 结果] → 这是预期行为，用户已经看到了
