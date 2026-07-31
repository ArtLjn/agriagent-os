## Context

`fix-task-state-context-gating` 修复了 should_inject 闸门,但仍可能因下游 selector 异常、active_task 表过期、context_pack 漏拉 等原因出现"relevance 说该注入但 bundle 实际没注入"的脱钩。当前 trace 不打告警,这种漂移只能靠人工查。

summary 触发参数当前 threshold=12,debounce=30min。spike `recent_messages_truncation` 显示 turn 11(summary 触发)能完美救回 turn 1+9 的关键决策,但 turn 9-10 之间存在窗口失忆(threshold 还没到、recent limit=8 已截断)。

CI 当前无 spike probe,改 router/context 后无自动化回归。

## Goals / Non-Goals

**Goals**:
- 让 relevance vs bundle 不一致在 trace 中显式可见
- 收窄 summary 触发窗口到 turn 8(threshold=8),消除 spike 实证的失忆窗口
- 把 3 个核心 spike 跑成 CI 必过项,任何回归立即失败

**Non-Goals**:
- 不引入新 alerting 系统(用现有 trace infrastructure)
- 不改 summary 算法本身(留给远期)
- 不增加 unit test 覆盖率(本变更只接 spike)

## Decisions

**D1: 一致性检查放在 ContextBuilder 出口,trace level=warning**

rationale: builder 出口最接近 bundle 最终状态,可同时校验 `metadata.task_state_relevance_decision` 与 `blocks` 中是否存在 `active_task_state`。warning 而非 error,避免阻塞主流程。

**D2: threshold 12→8 而非更激进**

rationale: spike 显示 turn 8(summary 触发)能覆盖 turn 1-7 的关键决策。threshold 更小(如 6)会让 summary 频繁触发,LLM 成本不可控。8 是平衡点。

**D3: debounce 30→10 而非 0**

rationale: 完全去掉 debounce 会让连续多轮 user 输入触发并发 summary 写入,乐观锁冲突上升。10 分钟 debounce 保留去抖,且 spike 显示用户多轮密集输入场景 summary 仍能及时落库。

**D4: CI 跑 3 个核心 scenario 而非全部**

rationale: 全部 scenario(7+)成本高且重复。挑 3 个最具代表性的:`task_state_db_injection` / `recent_messages_truncation` / `long_query_summary_trigger`,覆盖 #6/#7/截断/summary 触发四类失忆点。

## Risks / Trade-offs

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| summary 频率上升导致 LLM 成本超预算 | 中 | 月度成本 +X% | 接 `session_summary_generated_total` 监控,W3 观察期校验 |
| trace warning 噪声过大 | 低 | oncall 疲劳 | warning level 而非 error,且只在 should_inject 与 bundle 真不一致时触发 |
| CI spike job 跑得慢(每个 scenario 5-10s LLM 调用) | 高 | PR 流水线变慢 | 并行跑 3 个 scenario,设 60s 超时,失败不强制 block(初版 warn-only) |
| threshold 调整后历史 session 行为不一致 | 低 | 用户体验波动 | 灰度发布,旧 session 走旧参数,新 session 走新参数 |
