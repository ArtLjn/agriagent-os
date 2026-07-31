## 1. 删除 looks_like_web_search 死代码

- [ ] 1.1 `grep -rn "looks_like_web_search" backend/` 确认全仓库无生产代码调用(仅 tests/ 引用)
- [ ] 1.2 删除 `backend/app/agent/router/classifier_signals.py` 中 `looks_like_web_search` 函数及相关常量(`WEB_CURRENT_EVENT_TOPIC_HINTS`、`WEB_CURRENT_EVENT_BLOCKERS` 等)
- [ ] 1.3 删除 `backend/tests/agent/router/test_router_governance_eval.py` 中专测 `looks_like_web_search` 的 case
- [ ] 1.4 确认 `backend/scripts/router_c_spike.py` 不再 import(改 Mode A 实现为"直接判 should_inject=False"或删除 Mode A 列)

## 2. LLMPlannerOutput schema

- [ ] 2.1 新建 `backend/app/agent/runtime/planner/schemas.py`,迁移 `backend/scripts/planner_probe.py` 的 `LLMPlanStep`/`LLMPlanOutput`(pydantic BaseModel)
- [ ] 2.2 新建 `backend/app/agent/runtime/planner/llm_planner.py`,导出 `async generate_plan_draft(llm, user_input, catalog) -> PlanIR | None`
- [ ] 2.3 内部用 `llm.with_structured_output(LLMPlanOutput)`,失败返回 None
- [ ] 2.4 wrapper 函数:LLMPlanOutput → PlanIR(填 ir_id/context_hash/planner_version 等元数据,复用 probe 逻辑)

## 3. planner.draft 节点

- [ ] 3.1 在 `backend/app/agent/runtime/nodes.py` 新增 `planner_draft_node(state)`,在 router r1 之后、ReAct 之前执行
- [ ] 3.2 节点内:
  - 检查 AgentState 是否已有缓存的 PlanDraft,有则直接返回
  - 调 `generate_plan_draft`,失败则降级 `plan_draft_from_router_decision`
  - 写 trace `planner.draft`,含 task_type/intent/steps 摘要
  - 把 PlanDraft 渲染成文本,注入 system prompt(软提示)
- [ ] 3.3 检测 task_type 切换:对比 AgentState 中 router r1 当前决策 vs 上一轮的 task_type,不同则强制重算

## 4. 测试

- [ ] 4.1 新增 `backend/tests/agent/runtime/planner/test_llm_planner.py`:mock LLM 返回,验证 wrapper 转 PlanIR、过 4 层校验
- [ ] 4.2 新增 `backend/tests/agent/runtime/planner/test_planner_draft_node.py`:
  - test_first_round_invokes_llm
  - test_llm_failure_falls_back_to_rule
  - test_subsequent_round_reuses_cache
  - test_task_type_switch_re_invokes
- [ ] 4.3 更新 `backend/tests/agent/router/test_router_governance_eval.py`:移除 `looks_like_web_search` 相关 case
- [ ] 4.4 在 `backend/scripts/planner_probe.py` 改 import 来源为 `app.agent.runtime.planner.schemas`(消重)

## 5. 验证

- [ ] 5.1 跑 `backend/scripts/planner_probe.py` 5 case 通过率 ≥ 80%
- [ ] 5.2 playground 首轮输入 "帮我规划秋季草莓 20 亩",trace 含 `planner.draft` 节点,PlanDraft 含 4+ step
- [ ] 5.3 第 2 轮输入 "20 亩",trace 不含 `planner.draft`(命中缓存)
- [ ] 5.4 `bash harness-check.sh` 全量回归

## 6. 上线

- [ ] 6.1 提交 PR,关联 `docs/specs/2026-07-31-agent-harness-design.md` 阶段 2
- [ ] 6.2 A/B 实验:50% 会话开 planner.draft LLM 路径,50% 走规则降级,对比 tool_calls 准确率与 LLM 成本
- [ ] 6.3 2 周后根据 A/B 数据决定是否全量启用 LLM planner
- [ ] 6.4 在变更记录追加"阶段 2 已实施"
