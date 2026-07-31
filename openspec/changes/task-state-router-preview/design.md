## Context

router r1 当前直接拿用户原始输入做 BM25+向量召回 + LLM 自选。多轮承接场景下,r1 不知道"上一轮我们在创建茬口",可能把"20 亩"理解成"查询 20 亩地块"。

`evaluate_task_state_relevance` 已经能判定当前输入是否承接 active task(基于 `_AREA_RE/_SEASON_RE/_UNIT_NAME_RE` 等规则),`task_state_routing_input` 能把 active task 拼成路由友好前缀。这两个函数当前只用于 trace,未接入 r1 主路径。

## Goals / Non-Goals

**Goals**:
- 让 router r1 在 should_inject=True 时看到任务态前缀
- 保持 should_inject=False 时路由输入完全不变(避免污染闲聊/旁路)
- 不引入新模块,仅复用现有函数

**Non-Goals**:
- 不改 router r1 的内部决策逻辑(BM25+向量权重、LLM 自选 bind_tools 范围)
- 不改 ContextBundle 注入路径(那是 Change `fix-task-state-context-gating` 的范围)
- 不升级 `evaluate_task_state_relevance` 的判定算法(留给 Change `task-state-updater-hybrid`)

## Decisions

**D1: 在 r1 入口注入,而非 router 内部**

rationale: 路由前缀是"输入整形",不是 router 内部状态。在调用 router 前用 `routing_input_for_task_state(state, user_input)` 拿到整形后输入,再传给 router,保持 router 纯粹。

**D2: should_inject 阈值保留 0.75 不动**

rationale: `INJECT_THRESHOLD=0.75` 是 task_state_relevance.py 的现状,本变更只接通管线,不调参数。

## Risks / Trade-offs

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| 任务态前缀误导 BM25+向量(把"当前任务:茬口创建"当成查询茬口) | 中 | r1 候选召回偏差 | spike `context_multiturn_spike.py` 已覆盖,观察 selected_blocks 是否合理 |
| 闲聊场景误注入 | 低 | router 输入被污染 | should_inject=False 时不动 user_input,保证零回归 |
| active_task 表过期但未清理 | 中 | 路由前缀陈旧 | 依赖 AgentTaskStateStore.expires_at 机制(已存在),不在本变更范围 |
