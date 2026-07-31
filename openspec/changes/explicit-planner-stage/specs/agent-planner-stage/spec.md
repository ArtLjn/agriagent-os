## ADDED Requirements

### Requirement: Stage 2 显式 Planner 节点

每个会话首轮,在 router r1 决策之后、ReAct 循环之前,必须执行 `planner.draft` 节点。该节点产出 PlanDraft(LLMPlannerOutput 或规则降级版本),作为软提示注入 system prompt,并写入 trace。

#### Scenario: 首轮调 LLM planner

- **WHEN** 会话首轮用户输入 "帮我规划秋季草莓 20 亩"
- **THEN** planner.draft 节点调 LLM 拿 `LLMPlanOutput`,经 wrapper 转 PlanIR,过 `validate_plan_ir` + `compile_plan_ir`,成功则注入 system prompt

#### Scenario: LLM 失败时降级到规则 PlanDraft

- **WHEN** LLM 调用超时/schema 校验失败/输出空
- **THEN** planner.draft 降级到 `plan_draft_from_router_decision`,trace 记录 `reason=llm_fallback`

#### Scenario: 后续轮次复用首轮 PlanDraft

- **WHEN** 同一会话的第 2+ 轮,且 router 未检测到 task_type 切换
- **THEN** planner.draft 节点直接读 AgentState 缓存的 PlanDraft,不调 LLM

#### Scenario: PlanDraft 作为软提示不强制约束 ReAct

- **WHEN** PlanDraft 含 4 个 step,但 LLM 在 ReAct 中只调了 1 个工具就回复
- **THEN** 不视为错误,trace 正常记录实际 tool_calls,PlanDraft 保留作上下文

#### Scenario: task_type 切换时重新调 planner

- **WHEN** 后续轮次 router r1 检测到 task_type 从 `crop_cycle_setup` 切换到 `cost_analysis`
- **THEN** planner.draft 重新调 LLM 生成新 PlanDraft,覆盖 AgentState 中缓存的旧值
