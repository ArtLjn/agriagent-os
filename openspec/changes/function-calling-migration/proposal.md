## Why

当前 Skill 路由依赖两层匹配：关键词 fast_match（`str.find` 触发词）+ LLM 意图分类兜底。关键词匹配精度有限（口语、同义词难覆盖），LLM 兜底每次未命中都额外消耗一次 LLM 调用。同时快通道直返原始工具输出，未经 LLM 组织语言，导致回答风格割裂（有时是数据表，有时是自然语言）。迁移到 Function Calling 后，路由精度由模型原生 tool selection 能力保证，且所有回答都经过 LLM 润色，风格统一。

## What Changes

- **移除 skillify 预路由快通道**：删除 `_try_skillify_route()` 及 `agent_service.py` 中的快通道分支（只读 skill 直接执行、写操作预路由识别），所有请求统一走 LangGraph `llm → tools → llm` 循环
- **保留写操作拦截机制**：`_parallel_tool_node` 中的 `is_write_skill()` 检查和 pending action 流程不变，写操作仍然不直接执行
- **Progressive Disclosure 优化 tool schema 注入**：System prompt 中不再全量注入 10 个 skill 的完整描述（~30K tokens），改为只注入精简的 tool schema（name + description + parameters），由 LLM 原生 function calling 决策
- **移除 skillify-sdk 的 PatternMatcher 和 LLM 意图分类调用**：`SkillManager.handle()` 中的快通道匹配逻辑不再被 `agent_service` 调用，SDK 仅保留 Skill 注册和执行能力
- **trace 记录调整**：移除 `node_type="routing"` 的 `skillify_route` trace 记录，tool 调用链路由 LangGraph `_parallel_tool_node` 记录
- **BREAKING**: `agent_service.py` 的 `chat_with_agent()` 和 `stream_chat_with_agent()` 删除 skillify 预路由分支，API 接口不变但内部行为变更（所有请求都经过 LLM）

## Capabilities

### New Capabilities
- `fc-native-routing`: Skill 路由统一走 LLM Function Calling，移除 skillify 预路由快通道，所有回答经 LLM 组织语言

### Modified Capabilities
- `llm-tool-calling`: 现有 FC 基础设施已就绪（`_llm_node` bind_tools、`_parallel_tool_node` 并行执行），但需要补充 Progressive Disclosure 的 tool schema 精简注入策略
- `agent-trace`: 移除 `skillify_route` routing 节点记录，FC 路由的 trace 由现有的 `llm_call` + `skill_call` 节点自然覆盖

## Impact

- **agent_service.py**: 大幅简化，删除 `_try_skillify_route()`、快通道分支、`_execute_skill()` 直接调用，统一走 LangGraph
- **agent/advisor.py**: `invoke_advisor` 和 `stream_advisor` 已走 LangGraph，无需改动
- **agent/graph.py**: `_llm_node` 的 `bind_tools()` 已就绪，可能需要优化 tool schema 注入方式（Progressive Disclosure）
- **agent/skills/__init__.py**: `get_skill_manager()` 和 `build_skill_context()` 中 LLM 意图分类相关代码可清理
- **skillify-sdk**: PatternMatcher 和 LLM intent 模块不再被业务调用，SDK 进入维护模式
- **前端**: API 接口不变，`skills` 字段返回内容从 `[skillify_route, xxx]` 变为 `[xxx]`（去掉 routing 前缀）
- **延迟变化**: 只读 skill 请求从 ~200ms 增加到 ~2-3s（需经过 LLM），但回答质量显著提升
- **成本变化**: 每次请求都调用 LLM，但省去了 skillify LLM 意图分类的额外调用（净增加可控）
