## Context

`task_state_should_inject` 是 `ContextBuildRequest` 的字段,默认 True。`TaskStateSelector` 只看这个字段决定是否注入。当前调用链(`ContextBuilder.build_runtime_context_bundle` → `build`)从不显式传 `should_inject`,所以永远是 True。

`evaluate_task_state_relevance` 已经能给出 should_inject 决策,但当前只用于 `routing_input_for_task_state`(给 router 用),不传给 ContextBuilder。

`missing_information` 当前只在创建 active task 时写入,turn 后没有任何更新路径。用户回答的信息只能靠 LLM 在自己回复里"看到",不会反映到 task_state 表。

## Goals / Non-Goals

**Goals**:
- 让 TaskStateSelector 真正消费 relevance 决策(should_inject=False 时不注入)
- 让用户回答能自动剔除 missing_information 中对应的字段
- 规则版 extractor 覆盖面积/季节/种植单元名称三个最常见的 missing 类型

**Non-Goals**:
- 不引入 LLM 版 extractor(留给 `task-state-updater-hybrid`)
- 不改 relevance 判定算法本身
- 不改 task_state schema(无新字段)

## Decisions

**D1: relevance 调用放在 ContextBuilder 入口,而非 selector 内部**

rationale: selector 内部调 relevance 会破坏 selector 的"纯读"语义(还要传 user_input + active_task_dict),且多个 selector 都可能需要类似决策。统一在 builder 入口算好,通过 `ContextBuildRequest` 字段传下去。

**D2: extractor 用规则版优先,而非 LLM**

rationale: 规则版(`_AREA_RE/\d+亩/`/`_UNIT_NAME_RE/(叫|名称叫)/X/`)在 spike 上已实证有效,成本低、可解释、无外部依赖。LLM 版成本高且不稳定,延后。

**D3: extractor 在 turn 结束、assistant 回复写库后调**

rationale: extractor 只看 user_input,但放在 turn 末尾便于 trace 关联(round 完成时一并更新)。如果未来加 LLM 版,可借助 assistant reply 的"追问面积"信号辅助判定。

**D4: missing_information 用列表相等而非追加**

rationale: 当前 missing 是 list,extractor 抽到"20 亩"后从 list 中剔除"面积",其余保留。用 set 操作简洁,不引入新结构。

## Risks / Trade-offs

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| 规则误抽("20 亩"被识别成种植单元) | 低 | missing 错误剔除 | `_AREA_RE` 严格匹配 `\d+亩`,`_UNIT_NAME_RE` 要求前缀"叫/名称叫",误抽概率低 |
| 某些承接场景因 should_inject=False 漏注入 | 中 | 多轮承接回退 | spike `task_state_db_injection` 已覆盖 4 turn,turn 2-4 should_inject 都为 True |
| active_task 已 completed 但 selector 仍查到 | 低 | 旧任务态污染 | AgentTaskStateStore 已过滤 ACTIVE_STATUSES,本变更不动 |
| 用户用同义表达("两万平米"代替"20 亩") | 高 | 规则版漏抽 | 接受为已知限制,LLM 版 extractor 在 `task-state-updater-hybrid` 解决 |
