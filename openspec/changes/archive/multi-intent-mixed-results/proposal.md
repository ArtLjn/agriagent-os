## Why

多意图消息（如"今天天气怎么样，我想种玉米"）触发 query + write 混合 tool call 时，`_llm_node` 检测到 pending ToolMessage 后跳过 LLM 直接返回确认文案，导致 query 结果（天气数据）完全丢失。用户只看到"确认吗？"，看不到天气信息。

## What Changes

- `_llm_node` 增加混合结果合并逻辑：当 ToolMessage 中同时存在 pending 和非 pending 结果时，将 query tool 结果摘要 + write confirm 文案拼接为一条 AIMessage，不调用 LLM
- `_parallel_tool_node` 中 pending ToolMessage 的 content 格式调整，携带 skill display name 便于前端展示
- `pending_actions.py` 的 `build_confirm_message` 参数显示优化（`crop_name=玉米` → `玉米`）

## Capabilities

### New Capabilities
- `mixed-result-merge`: 处理同一轮中 query + write tool call 混合结果，合并为一条完整回复（query 结果摘要 + write 确认提示）

### Modified Capabilities

## Impact

- `backend/app/agent/graph.py`: `_llm_node` 的 pending 检测逻辑从二元判断改为三路分支
- `backend/app/infra/pending_actions.py`: `build_confirm_message` 参数可读性优化
- 前端无需改动 — 最终输出仍然是一条 AIMessage，pending_action SSE 事件不变
