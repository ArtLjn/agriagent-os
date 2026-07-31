## 1. 修复 #6:relevance 闸门

- [ ] 1.1 在 `backend/app/context/builder.py` `build_runtime_context_bundle` 入口,从 db 查 active task(`AgentTaskStateStore.get_active_task`),构造 dict
- [ ] 1.2 调 `evaluate_task_state_relevance(request.query, active_task_dict)`,拿到 `should_inject`
- [ ] 1.3 把 `should_inject` 写入 `ContextBuildRequest.task_state_should_inject`(覆盖默认 True),再传入 build
- [ ] 1.4 在 bundle.metadata 写入 `task_state_relevance_decision` 供 trace 检查

## 2. 修复 #7:规则版 entity extractor

- [ ] 2.1 新建 `backend/app/agent/runtime/task_state_updater.py`,导出 `update_task_state_from_user_input(db, farm_id, user_id, session_id, user_input)`
- [ ] 2.2 函数内:查 active task;若无返回;按 missing_information 字段类型匹配规则:
  - 含"面积/亩" → 用 `_AREA_RE` 抽
  - 含"季节/茬口" → 用 `_SEASON_RE` 抽
  - 含"种植单元名称/地块名称/名称" → 用 `_UNIT_NAME_RE` 抽
- [ ] 2.3 命中则调 `AgentTaskStateStore.upsert_active_task(missing_information=[剔除已补字段])`,写 trace event `task_state_missing_updated`
- [ ] 2.4 在 `backend/app/agent/runtime/nodes.py` turn 末尾(assistant reply 写库后)调 `update_task_state_from_user_input`

## 3. 测试

- [ ] 3.1 新增 `backend/tests/context/test_builder_task_state_gating.py`:
  - test_relevance_should_inject_false_blocks_task_state
  - test_relevance_should_inject_true_includes_task_state
  - test_no_active_task_skips_selector
- [ ] 3.2 新增 `backend/tests/agent/runtime/test_task_state_updater.py`:
  - test_area_input_removes_missing_area
  - test_unit_name_input_removes_missing_name
  - test_greeting_input_no_change
  - test_no_active_task_short_circuit
- [ ] 3.3 更新 `backend/tests/agent/runtime/test_context_multiturn_spike_cases.py`(若有),验证 turn 1 不注入 + turn 3 missing 自动剔除

## 4. 验证

- [ ] 4.1 跑 `backend/scripts/context_multiturn_spike.py --only task_state_db_injection`:
  - turn 1 bundle 不含 `active_task_state`
  - turn 3 后 bundle 中 missing 不再含"面积"
  - turn 4 后 missing 不再含"种植单元名称"
- [ ] 4.2 playground 多轮承接 case:LLM 不再反复追问"种多少亩"
- [ ] 4.3 `bash harness-check.sh` 全量回归

## 5. 上线

- [ ] 5.1 提交 PR,关联 `docs/specs/2026-07-31-agent-harness-design.md` 阶段 1.5 Layer 0
- [ ] 5.2 灰度 1 周,监控 `task_state_missing_updated` event 计数 + 用户承接满意度
- [ ] 5.3 在变更记录追加"阶段 1.5 Layer 0 已实施"
