## Context

当前后端已经存在 `app/context` 模块，包含 `ContextBlock`、`ContextBundle`、selector、token budget、cache 和 preload；`app/memory` 也已预留短时/长期记忆边界。实际 Agent Runtime 主链路仍主要通过 `build_farm_runtime_context()` 注入 `farm_location`、`farm_coords`、`display_name`、`active_crops` 四个字段，再用 `sliding_window_compact()` 保留最近消息并压缩旧工具结果。

这套方式避免了全量注入，但存在三个问题：第一，`ContextBundle` 的预算和 trace 能力未成为主链路决策入口；第二，短时记忆仍以消息列表滑窗为主，缺少 session 摘要和 pending action 的统一策略；第三，用户资料、农场信息、活跃茬口、账务等缓存缺少统一失效规则，容易在写操作后短时间注入旧上下文。

## Goals / Non-Goals

**Goals:**
- 将上下文分为热上下文、工作记忆、按需检索上下文三层。
- 让 Agent Runtime 基于 intent、selected tools 和 request metadata 构建 `ContextBundle`。
- 统一最终 prompt 的 token 预算、压缩、丢弃和 trace 记录。
- 将短时记忆定义为 session 级工作记忆，支持最近窗口、会话摘要、pending action 和临时任务状态。
- 保证用户相关信息从认证和数据库边界精确获取，并在写操作后清理相关缓存。

**Non-Goals:**
- 不在本变更中引入外部向量数据库。
- 不要求一次性实现完整长期记忆沉淀和语义检索。
- 不改变现有 HTTP API 的主要请求/响应结构，除非测试发现需要补充内部字段。
- 不移除现有 skill 主动获取机制；上下文注入只提供必要背景，详细业务数据仍优先由工具按需查询。

## Decisions

### Decision 1: 三层上下文模型

采用三层模型：
- 热上下文：每次注入，极小且高可信，包括用户称呼、位置、坐标、当前 farm、活跃茬口、当前日期和季节。
- 工作记忆：session 级，包括最近消息窗口、旧消息摘要、pending action、临时任务状态。
- 按需检索上下文：由 intent 和 selected tools 决定是否注入，包括账务摘要、天气摘要、农事日志、长期记忆命中、外部检索结果。

替代方案是继续把所有上下文都放进 system prompt。该方案实现简单，但 token 难控，且容易把不相关业务数据误导给 LLM。

### Decision 2: ContextPolicy 驱动 selector

新增 `ContextPolicy` 或等价配置层，根据 `intent`、`selected_tool_names`、`farm_id`、`session_id` 决定启用哪些 selector 和各类 token 预算。`ContextBuilder` 只负责执行 selector、组装 block、应用预算和记录 trace，不内嵌业务判断。

替代方案是在 `nodes.py` 中硬编码 selector 选择逻辑。该方案初期更快，但会让 runtime 节点持续膨胀，且不利于 selector 单测。

### Decision 3: 短时记忆作为 Memory Service 的 session 视图

短时记忆不等同于完整 conversation 表。Memory Service 提供面向 Agent 的 session 视图：
- 最近 N 轮原文消息。
- 超出窗口的会话摘要。
- 当前 pending action。
- 临时任务状态。

Conversation Service 继续负责消息持久化和会话生命周期。Memory Service 负责将持久化消息转为可注入上下文。

### Decision 4: token-aware 最终预算

保留当前 `ContextBlock.priority` 机制，但最终预算必须覆盖：
- system prompt 静态部分。
- 热上下文。
- 工作记忆。
- 按需检索上下文。
- 工具结果。

短期可以继续使用保守估算，接口上预留 tokenizer 适配；实现时不得仅依赖字符长度判断最终输入是否安全。

### Decision 5: 工具主动获取优先于大块注入

账务明细、天气详情、农事日志、债务列表等高波动或可查询数据不做默认全量注入。上下文只注入摘要和定位信息，详细数据由 selected tools 主动获取。

这延续当前架构优点：低 token、低幻觉、数据来源可追踪。

## Risks / Trade-offs

- [Risk] selector 过多导致请求延迟增加 → 通过 ContextPolicy 限制默认 selector，并保留 tool cache preload。
- [Risk] 预算裁剪丢掉用户关键信息 → 热上下文 block 标记 required，且 trace 记录所有 dropped block。
- [Risk] 缓存失效遗漏导致上下文过期 → 在用户设置、农场、周期、账务、日志写接口加统一 invalidation helper，并补测试。
- [Risk] 会话摘要质量影响追问理解 → 第一阶段可使用确定性摘要模板或保守保留最近窗口，摘要生成失败时降级为空摘要。
- [Risk] 引入 ContextPolicy 增加复杂度 → 先实现内置规则表，不引入外部 DSL 或数据库配置。

## Migration Plan

1. 保留现有 `build_farm_runtime_context()` 和 prompt cache，先新增 ContextPolicy 与短时记忆接口。
2. 将 runtime 主链路从直接取四字段升级为构建 `ContextBundle`，同时继续渲染原 `system_base` 变量，降低回归风险。
3. 将 ConversationSelector 和 MemorySelector 接入 session 短时记忆，替换纯 `sliding_window_compact()` 的旧窗口策略。
4. 为写接口添加 context/prompt cache invalidation。
5. 通过 trace 对比新旧上下文 token、selector 选择和 Agent 回复质量，再逐步扩大按需 selector 覆盖。

Rollback 策略：保留配置开关，允许 Runtime 回退到 `build_farm_runtime_context()` 四字段注入和旧消息滑窗。

## Open Questions

- 最终 token 估算是否使用模型供应商 tokenizer，还是项目内统一保守估算器？
- 会话摘要第一阶段由 LLM 生成，还是先采用确定性截断摘要？
- 长期记忆检索的存储层是继续 SQL 表预留，还是后续接入向量数据库？
