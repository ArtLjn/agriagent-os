## Context

当前系统使用自研 `skillify-sdk` 做 Skill 路由，架构为两层匹配：

```
用户消息 → PatternMatcher（关键词 str.find）→ 命中 → 直接执行 skill → 返回原始工具输出
                                   ↓ 未命中
                        LLM 意图分类（zero-shot）→ 命中 → 直接执行 skill
                                              ↓ 未命中
                                           LangGraph Agent
```

问题：
1. **快通道回答割裂**：只读 skill 快通道直返工具原始输出（如天气数据表），未经 LLM 组织语言，与走 LangGraph 的回答风格完全不同
2. **关键词匹配精度有限**：口语表达、同义词、隐式意图难以用 triggers 列表覆盖
3. **LLM 兜底成本不可控**：每次关键词未命中都额外调一次 LLM 做意图分类，且 zero-shot prompt 无 few-shot 示例
4. **幻觉风险**：快通道没有验证 skill 是否真的应该被调用（纯靠关键词），可能误触发

已有的 FC 基础设施：`graph.py` 的 `_llm_node` 已调用 `bind_tools()`，`_parallel_tool_node` 已支持并行执行 + 写操作拦截。LangGraph 的 `llm → tools → llm` 循环已经端到端可用。

## Goals / Non-Goals

**Goals:**
- 所有请求统一走 LangGraph `llm → tools → llm` 循环，消除快/慢通道的风格割裂
- 移除 skillify 预路由（`_try_skillify_route`），减少一层中间路由的复杂度和维护成本
- 保持写操作拦截机制（pending action）不变
- 所有回答经过 LLM 组织语言，回答风格统一自然
- LLM 只能调用已注册的 tool，从根本上消除 skill 幻觉

**Non-Goals:**
- 不做 Progressive Disclosure 的 tool schema 动态加载（当前 10 个 skill 的 schema 总量约 3K tokens，可接受，后续优化）
- 不修改 skillify-sdk 本身（SDK 进入维护模式，不删除，仅不再被业务调用）
- 不改前端 API 接口
- 不改写操作确认流程
- 不做 Prompt 模板优化（属于独立优化项）

## Decisions

### D1: 移除快通道，而非加 LLM 润色层

**选择**: 完全移除 skillify 预路由快通道
**替代方案**: 保留快通道执行 skill，在结果上加一步 LLM 润色
**理由**: 加润色层只是打补丁，引入了"快通道+润色"和"慢通道"两条路径的维护成本。直接移除快通道让架构更简洁，LangGraph 已完全支持 FC 路由。

### D2: 保留 `_execute_skill()` 用于 pending action 确认后执行

**选择**: 保留 `_execute_skill()` 函数，但仅被 pending action 确认流程调用
**理由**: 写操作确认后需要直接执行 skill，不经过 LLM。这个执行路径与快通道无关，是 pending action 流程的内部实现。

### D3: trace 中不再记录 `skillify_route` routing 节点

**选择**: 移除 routing 节点，FC 路由的 trace 由 `llm_call`（tool selection）+ `skill_call`（执行）自然覆盖
**理由**: 快通道移除后不再有预路由的概念。LangGraph 的 `_llm_node` 已经记录 `tool_calls` 决策，`_parallel_tool_node` 已经记录 skill 执行结果，trace 链路自然完整。

### D4: 前端 skills 字段保持不变

**选择**: 前端 SSE 中 `skills` 字段继续返回已执行的 skill 名称列表，但不再包含 `skillify_route`
**理由**: `agent.py` 的 `event_generator` 查询 `trace_records` 中 `node_type="skill_call"` 和 `"routing"` 的记录。移除快通道后只有 `skill_call` 记录，前端展示逻辑无需改动（`skillify_route` 本来就是额外的 routing 条目）。

## Risks / Trade-offs

| 风险 | 影响 | 缓解 |
|------|------|------|
| 只读 skill 延迟增加（~200ms → ~2-3s） | 用户体感变慢 | 1) FC 路由只走一轮 `llm → tool → llm`，~2-3s 可接受；2) 天气等高频 skill 已有 TTL 缓存，第二轮 LLM 润色耗时短 |
| 每次请求都消耗 LLM token | 成本增加 | 省去了 skillify LLM 意图分类的额外调用；FC 路由的 tool schema 注入约 3K tokens，整体可控 |
| LLM 可能不选择调用 tool（该调不调） | 漏掉 skill 执行 | 已有的 FC spec 验证过 qwen3.6-flash 的 tool selection 精度；可通过 prompt 中的 tool description 优化提升 |
| LLM 可能选择错误的 tool | 回答不准确 | LangGraph 的 tool 调用结果会回传给 LLM 做第二轮推理，LLM 可以自我纠正；tool schema 的 description 越精确，选择越准确 |
| 移除快通道后无法回退 | 不可逆 | 代码回退即可；skillify-sdk 保留在代码库中，不删除 |
