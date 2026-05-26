## Why

Agent 日志可观测性严重不足。当前日志只能看到请求进入和回复返回，中间的 skill 发现、LLM 工具选择决策、prompt 模板渲染、待确认操作生命周期等关键环节完全不可见。排查 Agent 问题只能靠猜测和读源码，效率极低。

## What Changes

- 在 `_llm_node` 中记录 LLM 的原始响应（选择哪些工具、参数是什么、或直接回复），使工具路由决策可见
- 在 Skill 执行流程中增加结构化日志：执行开始（参数摘要）、耗时、返回结果摘要
- 在 `pending_actions.py` 中记录完整生命周期：存储、检索、超时清理、用户意图检测
- 在 `prompt_renderer` 中记录模板选择和渲染变量（debug 级别）
- 在 `llm.py` 中记录客户端初始化和熔断器状态
- 激活 `AgentTrace` 模型，在关键节点写入追踪记录（LLM 调用耗时、token 数、工具调用链路）
- 在 `report.py` 中增加日志覆盖

## Capabilities

### New Capabilities
- `agent-trace`: Agent 调用链路追踪，在 LLM 调用和 Skill 执行节点写入 AgentTrace 表，记录耗时、token、输入输出摘要、错误信息
- `agent-structured-logging`: Agent 系统结构化日志规范，定义关键节点的日志级别、格式和必填字段，覆盖 graph/skills/prompt/pending-actions/llm 五个模块

### Modified Capabilities
- `llm-tool-calling`: 工具选择决策日志从 advisor 流式回调下沉到 `_llm_node`，非流式模式也记录工具选择

## Impact

- **代码变更**：`app/agents/graph.py`、`app/agents/advisor.py`、`app/agents/report.py`、`app/core/llm.py`、`app/core/prompt_renderer.py`、`app/core/pending_actions.py`、`app/skills/__init__.py`、各 Skill 实现
- **数据库**：`agent_trace` 表已有模型定义，需新增写入逻辑
- **日志输出**：`app.log` 和 `error.log` 信息量增加，但通过合理使用 DEBUG/INFO/WARNING 分级控制噪音
- **性能**：`AgentTrace` 写入在异步任务中完成，不影响响应延迟
