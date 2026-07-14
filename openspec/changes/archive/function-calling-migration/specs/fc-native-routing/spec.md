## ADDED Requirements

### Requirement: 所有对话请求统一走 LangGraph FC 路由
`agent_service.py` 的 `chat_with_agent()` 和 `stream_chat_with_agent()` SHALL 移除 skillify 预路由快通道分支。所有非 pending-action-确认 的请求 SHALL 直接走 `invoke_advisor()` / `stream_advisor()`，由 LangGraph `_llm_node` 通过 Function Calling 决定是否调用 tool。

#### Scenario: 只读 skill 请求走 FC 路由
- **WHEN** 用户发送 "今天天气咋样"
- **THEN** 请求不经过 `_try_skillify_route()`，直接进入 LangGraph；`_llm_node` 返回 `tool_calls=[weather]`；`_parallel_tool_node` 执行 skill；LLM 第二轮将天气数据组织为自然语言返回

#### Scenario: 闲聊请求不触发 tool
- **WHEN** 用户发送 "你好"
- **THEN** 请求直接进入 LangGraph；`_llm_node` 直接返回文本回复，不触发任何 skill

#### Scenario: 多 skill 并行调用
- **WHEN** 用户发送 "看看天气和最近的成本"
- **THEN** `_llm_node` 返回 `tool_calls=[weather, get_cost_summary]`；`_parallel_tool_node` 并行执行两个 skill；LLM 第二轮将两个结果综合为自然语言返回

### Requirement: 移除 skillify 预路由函数
`agent_service.py` SHALL 删除 `_try_skillify_route()` 函数。`chat_with_agent()` 和 `stream_chat_with_agent()` 中所有调用 `_try_skillify_route()` 的分支代码 SHALL 被移除。

#### Scenario: skillify 预路由代码不存在
- **WHEN** 检查 `agent_service.py` 源码
- **THEN** 不存在 `_try_skillify_route` 函数定义，不存在对 `get_skill_manager` 或 `build_skill_context` 的导入/调用（pending action 流程除外）

### Requirement: 写操作拦截机制保持不变
写操作 skill 的 pending action 流程 SHALL 继续工作：`_parallel_tool_node` 拦截写操作 skill，存储为 pending action；用户确认后通过 `_execute_pending_action()` / `_execute_skill()` 执行。

#### Scenario: 写操作走 FC 路由并被拦截
- **WHEN** 用户发送 "记一笔化肥 200 元"
- **THEN** `_llm_node` 返回 `tool_calls=[create_cost_record]`；`_parallel_tool_node` 检测到 `is_write_skill("create_cost_record")` 为 True；存储 pending action 并返回确认提示

#### Scenario: 用户确认后执行写操作
- **WHEN** 用户对 pending action 回复 "确认"
- **THEN** `_execute_pending_action()` 调用 `_execute_skill()` 执行 skill，返回执行结果

### Requirement: skillify-sdk 不再被业务层调用
`agent_service.py` SHALL 不再导入或调用 `skillify-sdk` 的 `SkillManager.handle()`、`PatternMatcher`、LLM 意图分类等路由能力。`skillify-sdk` 包本身保留在代码库中，可被测试或未来功能引用。

#### Scenario: agent_service 无 skillify-sdk 路由依赖
- **WHEN** 检查 `agent_service.py` 的导入列表
- **THEN** 不存在 `from app.agent.skills import get_skill_manager, build_skill_context` 等仅用于预路由的导入（`get_langchain_tools` 保留，供 `_execute_skill` 和 graph.py 使用）
