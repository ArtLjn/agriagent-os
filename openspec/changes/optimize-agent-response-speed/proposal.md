## Why

farm-manager App 已使用 `/chat/stream` 流式响应，但用户真实体感仍然慢。核心问题：Agent 处理一次写操作（记账、创建模板）需要 **2 次 LLM 调用**——第一次 LLM 决定调用 tool，tool_node 拦截为 pending 后，LLM 还要再生成一轮确认语。仅 LLM 等待时间就达 3-7 秒。加上每次请求都重新渲染 system prompt（查询 farm 信息、季节、坐标等），以及所有任务都用同一模型，简单问候和复杂分析没有区分，进一步拉高了平均延迟。

## What Changes

- **确认语模板化**：write skill 拦截后，确认消息由系统模板 `build_confirm_message` 直接生成，不再走第二轮 LLM。写操作从 2 次 LLM 降为 1 次，延迟减半
- **System Prompt 缓存**：按 `farm_id + date` 缓存渲染后的 system prompt，命中时直接复用，减少 100-200ms
- **模型路由**：问候/闲聊走轻量模型（Qwen-Turbo/GPT-4o Mini），常规查询走标准模型，复杂分析走大模型
- **并行预加载**：LLM 调用的同时，后台并行加载可能需要的上下文数据（最近成本、天气、茬口），减少 tool 执行等待
- **高频查询本地缓存**："今天天气"、"当前茬口状态"等结果缓存 5-10 分钟，避免重复调用外部 API

## Capabilities

### New Capabilities
- `agent-response-optimization`: Agent 响应速度优化（确认语模板化、prompt 缓存、模型路由）
- `agent-context-preload`: 上下文并行预加载机制
- `agent-query-cache`: 高频查询结果本地缓存

### Modified Capabilities
- （无 spec-level 需求变更，纯实现层优化）

## Impact

- **后端**: `backend/app/agent/graph.py`、`backend/app/agent/advisor.py`、`backend/app/agent/llm.py`、`backend/app/core/config.py`
- **API**: `/agent/chat/stream` 响应格式不变，但内部延迟降低
- **前端**: 无需改动，流式响应已可用
- **数据库**: 不影响业务表，只增加缓存层
