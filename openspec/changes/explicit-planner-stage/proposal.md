## Why

当前 agent 没有显式 Planner 阶段(缺陷 #4),`runtime/planning/adapter.py:plan_draft_from_router_decision` 把 router 决策"伪拆"成 PlanDraft,trace 难读、评测难做。`backend/scripts/planner_probe.py` 实证:LLM 在 `LLMPlanOutput` schema 上能稳定输出合法 PlanIR,5 case 通过 4 层校验。需要把"假 Planning"显式化为独立 trace 节点 `planner.draft`,并允许 LLM 在第一轮可选地输出结构化 plan。

## What Changes

- 把 `plan_draft_from_router_decision` 提升为独立 trace 节点 `planner.draft`,作为 Stage 2 显式存在
- 引入 `LLMPlannerOutput` schema(参考 `planner_probe.py`),让 LLM 在第一轮可选输出结构化 plan
- PlanDraft 作为**软提示**注入 system prompt,不强制约束 ReAct 循环
- 删除 `looks_like_web_search` 函数本身(阶段 0 已删特判,函数无调用方)

## Capabilities

### New Capabilities

- `agent-planner-stage`: 显式 Planner 阶段,产出 PlanDraft 注入 system prompt 作软提示

### Modified Capabilities

- `agent-intent-router`: 删除 `looks_like_web_search` 函数(已无调用方)
- `agent-trace`: 新增 `planner.draft` node_type

## Impact

- 受影响代码:
  - 新文件 `backend/app/agent/runtime/planner/llm_planner.py`(LLMPlannerOutput schema + invoke)
  - `backend/app/agent/runtime/planning/adapter.py`(提升为 trace 节点)
  - `backend/app/agent/runtime/nodes.py`(在 r1 router 之后、ReAct 之前插入 planner 节点)
  - `backend/app/agent/router/classifier_signals.py`(删除 `looks_like_web_search`)
- 受影响测试:`backend/tests/agent/runtime/test_planner_*` 新增、`backend/tests/agent/router/test_*` 更新
- LLM 成本:每会话首轮 +1 次 LLM 调用(planner.draft),后续轮次不调
- 回滚:禁用 LLM PlannerOutput 路径,保留规则 PlanDraft
