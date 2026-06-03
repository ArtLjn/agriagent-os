## Why

当前 Agent 主链路主要注入少量 farm runtime 字段，并依赖最近消息滑窗和工具主动查询来控制上下文大小；`ContextBundle`、selector、Memory 边界已经有雏形，但尚未形成统一的“意图驱动上下文 + 短时记忆”策略。随着账务、天气、作物、日志、长期记忆和多轮追问能力增加，需要明确哪些信息每次注入、哪些按需检索、哪些进入短时记忆，避免 token 膨胀、用户信息错注入和模型上下文崩溃。

## What Changes

- 建立三层上下文策略：热上下文、工作记忆、按需检索上下文。
- 将 `ContextBuilder.build()` 正式接入 Agent Runtime 主链路，由 intent 和 selected tools 决定启用哪些 selector。
- 将短时记忆定义为 session 级工作记忆，包含最近消息窗口、会话摘要、pending action 和临时任务状态。
- 增加 token-aware 预算策略，要求对最终 prompt 进行统一预算、压缩和丢弃记录。
- 增加用户上下文准确性规则，用户资料、位置、坐标、当前 farm 和 session 必须从认证/数据库边界获取，不得由 LLM 推断。
- 增加缓存失效策略，用户设置、农场信息、活跃茬口、账务和日志变更后必须清理相关 context/prompt 缓存。
- 增加上下文 trace 要求，记录候选 block、保留 block、压缩 block、丢弃 block、token 估算和 selector 错误。

## Capabilities

### New Capabilities
- `agent-context-policy`: 定义 Agent 上下文分层、意图驱动选择、token 预算和准确性规则。
- `short-term-memory-policy`: 定义 session 级短时记忆窗口、摘要、pending action 和临时状态策略。

### Modified Capabilities
- `conversation-management`: 会话历史注入从固定最近 10 轮升级为“最近窗口 + 摘要 + token 预算”的短时记忆策略。
- `user-context-injection`: 用户上下文注入从固定 XML 字段升级为认证绑定、数据库来源、缓存失效和缺失追问规则。
- `farm-context-injection`: 农场上下文摘要从固定摘要入口升级为 selector/block 化，并由上下文策略决定是否注入或按需工具获取。

## Impact

- 影响 `backend/app/agent/runtime/nodes.py`、`backend/app/agent/runtime/llm_support.py`、`backend/app/agent/runtime/messages.py`。
- 影响 `backend/app/context/*` 的 builder、models、budget、selectors、cache、preload。
- 影响 `backend/app/memory/*` 与 `backend/app/services/conversation_service.py` 的短时记忆接口。
- 影响用户设置、农场、周期、账务、日志等写接口的 context/prompt 缓存失效逻辑。
- 需要新增或更新 Context Builder、TokenBudget、Conversation/Memory、Agent Runtime 集成测试。
