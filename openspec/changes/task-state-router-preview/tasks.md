## 1. 代码改动

- [ ] 1.1 在 `backend/app/agent/router/service.py` 找到 r1 调用入口,在调用前查 `AgentTaskStateStore(db).get_active_task(farm_id, user_id, session_id)`
- [ ] 1.2 调 `evaluate_task_state_relevance(user_input, active_task_dict)` 拿决策
- [ ] 1.3 当 `should_inject=True` 时,用 `task_state_routing_input(user_input, active_task_dict)` 拼接路由输入并替换 r1 入参
- [ ] 1.4 在 AgentState 写入 `task_state_relevance` + `task_state_routing_input` 字段(供下游 trace 与 ContextBuilder 复用)

## 2. 测试

- [ ] 2.1 新增 `backend/tests/agent/router/test_router_task_state_preview.py`:
  - test_active_task_with_area_input_should_inject_prefix
  - test_active_task_with_greeting_should_not_inject
  - test_no_active_task_falls_through
- [ ] 2.2 更新现有 router 测试,凡涉及多轮承接的 case 需补 task_state seed

## 3. 验证

- [ ] 3.1 playground 多轮承接 case 通过(用户做完茬口创建第一步,第二轮 "20 亩" 路由到 manage_crop_cycle 而非 get_farm_status)
- [ ] 3.2 跑 `bash harness-check.sh` 全量回归
- [ ] 3.3 trace 检查:多轮承接场景的 router trace 含 `task_state_relevance.should_inject=True`

## 4. 上线

- [ ] 4.1 提交 PR,关联 `docs/specs/2026-07-31-agent-harness-design.md` 阶段 1
- [ ] 4.2 在变更记录追加"阶段 1 已实施"
