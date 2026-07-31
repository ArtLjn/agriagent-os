## Context

当前 PlanDraft 由 `plan_draft_from_router_decision` 从 RouterDecision 派生,本质是 router 决策的"格式化重排",不引入新信息。trace 里它和其他节点混在一起,看不出来"agent 在想什么"。

`planner_probe.py` 实证:LLM 拿到 capability catalog + task_type 枚举 + side_effect 规则后,能在 `LLMPlanOutput` schema 上稳定输出 4-5 步的 PlanIR,通过 `validate_plan_ir` + `compile_plan_ir` 4 层校验。5 case 全过(probe raw output 偶有 schema 偏差,经 wrapper 修正后 OK)。

## Goals / Non-Goals

**Goals**:
- 让 trace 出现独立 `planner.draft` 节点,可读、可评测
- 让 LLM 在首轮可选输出结构化 plan,作为软提示注入 system prompt
- 删除已无调用方的 `looks_like_web_search` 函数

**Non-Goals**:
- 不强制 PlanDraft 约束 ReAct(LLM 仍可自由调工具,PlanDraft 只是参考)
- 不引入 task_graph 的 FactSource / slot extractor(留给 `task-graph-disposition` 决策)
- 不改 capability catalog 内容(沿用现有 CAPABILITY_CATALOG)

## Decisions

**D1: LLMPlannerOutput schema 用 probe 验证过的版本**

rationale: `planner_probe.py` 的 `LLMPlanStep`/`LLMPlanOutput`(id/action_type/capability/depends_on/side_effect/description)已经过 5 case 验证,直接迁移而非重新设计。LLM 友好字段名(id 而非 step_id、action_type 而非 op)降低 schema 偏差率。

**D2: 软提示而非硬约束**

rationale: probe 显示 LLM 拆解偶有"多一步/少一步"偏差,硬约束会让 ReAct 卡死。软提示(注入 system prompt)让 LLM 自由偏离,同时给人可观测的"agent 当前在想什么"。

**D3: 只在首轮调 planner,后续轮次复用**

rationale: 多轮会话中 task_type 不变,每轮调 planner 是浪费。首轮生成后存入 AgentState,后续轮次直接读。如果用户意图明显切换(router 检测到 task_type 变化),才重新调。

**D4: 删除 looks_like_web_search**

rationale: 阶段 0 已删 web_search 特判,函数无调用方。死代码清理符合 python-style.md "删除不再使用代码"原则。

## Risks / Trade-offs

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| LLM planner 失败率 > 20% | 中 | 阶段 3 决策走"删 task_graph" | probe 已验证 5 case,失败时降级到规则 PlanDraft |
| 软提示让 LLM 分心,ReAct 决策变差 | 中 | 主链路指标下降 | A/B 实验:50% 会话开 planner,50% 不开,对比 tool_calls 准确率 |
| LLM 输出 schema 偏差率高 | 中 | planner 节点频繁失败 | probe 已封装 LLMPlanOutput wrapper 修正,直接复用 |
| 删 `looks_like_web_search` 后某处隐藏依赖 | 低 | runtime error | grep 全仓库确认无其他调用方;CI spike 兜底 |
