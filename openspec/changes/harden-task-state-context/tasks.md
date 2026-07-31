## 1. 一致性告警

- [ ] 1.1 在 `backend/app/context/builder.py` `build_runtime_context_bundle` 出口加 `_check_task_state_injection_consistency(bundle, relevance_decision, farm_id, session_id)` 函数
- [ ] 1.2 函数内:`expected = relevance_decision.should_inject`;`actual = any(b.key == "active_task_state" for b in bundle.blocks)`;不一致则 `get_collector().record(node_type="context_builder", node_name="task_state_injection_inconsistent", level="warning", ...)`
- [ ] 1.3 加单元测试覆盖三种 case(expected/actual 一致 True、一致 False、不一致)

## 2. summary 参数调整

- [ ] 2.1 在 `backend/app/shared/config.py` 把 `session_summary_message_threshold` 默认值改为 8
- [ ] 2.2 把 `session_summary_debounce_minutes` 默认值改为 10
- [ ] 2.3 在 `backend/config.yaml.example` 同步更新注释,说明依据是 spike 实证
- [ ] 2.4 加配置迁移说明:旧 session 不受影响(每次 maybe_summarize 读最新 settings),不需要数据迁移

## 3. CI 接入 spike probe

- [ ] 3.1 在 CI workflow 加 job `context-spike-regression`,并行跑 3 个 scenario(60s 超时)
- [ ] 3.2 解析 scenario JSON 输出,断言关键不变量(见 specs/agent-evaluation-foundation)
- [ ] 3.3 初版 warn-only(失败打 warning 但不 block PR),观察 2 周后转 hard fail
- [ ] 3.4 在 `backend/scripts/context_multiturn_spike.py` 加 `--assert-invariants` flag,内部自检关键不变量并返回非零退出码

## 4. 验证

- [ ] 4.1 故意把 `evaluate_task_state_relevance` 改坏(让 should_inject 永远 False),确认 trace warning 出现
- [ ] 4.2 跑 `recent_messages_truncation`,确认 turn 8 触发 summary(原来 turn 11)
- [ ] 4.3 在 PR 故意改 builder 跳过 selector,确认 CI spike job 失败
- [ ] 4.4 跑 `bash harness-check.sh` 全量回归

## 5. 上线与监控

- [ ] 5.1 提交 PR,关联 `docs/specs/2026-07-31-agent-harness-design.md` 阶段 1.5 Layer 1
- [ ] 5.2 灰度 1 周,监控 `session_summary_generated_total` counter 是否符合预期(+50% 左右)
- [ ] 5.3 观察 `task_state_injection_inconsistent` warning 计数,确认正常情况下为 0
- [ ] 5.4 2 周后把 CI spike job 从 warn-only 转 hard fail
- [ ] 5.5 在变更记录追加"阶段 1.5 Layer 1 已实施"
