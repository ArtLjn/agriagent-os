## Context

SkillRouter 的三层架构(见 `docs/specs/2026-07-31-agent-harness-design.md` 5.0 节):
- Layer 1: BM25+向量召回(HybridOperationRetriever)
- Layer 2: 硬规则门禁(写操作风险/寒暄兜底/schema 预算)
- Layer 3: LLM 自选(bind_tools top-K)

当前 `_allow_model_choice_read_candidate` (policy.py:407) 对 web_search 做了**单工具关键词二次校验**——BM25+向量已把 web_search 召回,但 policy 用 `looks_like_web_search` 关键词规则再次过滤,把 web_search 踢出候选。这是把"Layer 1 召回信号"误当成"Layer 2 硬规则"用,违反分层治理原则。

spike 实证(2026-07-31, 10 case): Mode A 总命中 50%, web_search 类 28.6%;删特判后 Mode B(LLM 自选)总命中 90%, web_search 类 100%。

## Goals / Non-Goals

**Goals**:
- 让 BM25+向量召回的 web_search 候选直接进入 LLM 自选,不再被关键词规则二次过滤
- 保持其他 read 工具行为不变
- 提供灰度止血路径(hints 表补词),便于分阶段上线

**Non-Goals**:
- 不删除 `looks_like_web_search` 函数本身(留给阶段 2 显式 Planner 一起做)
- 不重构 SkillRouter 三层架构(本阶段仅删一处特判)
- 不改 BM25+向量权重(bm25=0.15/vector=0.85 保留)

## Decisions

**D1: 直接删 web_search 分支,所有 read 候选一视同仁**

rationale: spike 实证 Mode B 命中率全面优于 Mode A,LLM 自选在 web_search 类 100% 命中。保留特判无收益。

**D2: hints 表补词作为可选止血,不强制**

rationale: 删特判后,即使保留 `looks_like_web_search` 函数也无调用方。但 hints 表里"价格/行情/政策/上市"是真实业务词汇缺失,补上对其他启发式路径(如 classifier_frames)有正向价值,且风险极低。

**D3: 不改写操作门禁**

rationale: 写操作 (`write_confirm/write_high`) 是真正的 Layer 2 硬规则,与 web_search 特判无关,不在本变更范围。

## Risks / Trade-offs

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| web_search 调用频率上升带来 LLM/搜索 API 成本 | 中 | 月度成本 +X% | 上线后 1 周监控 `session_summary_generated_total` 类指标,异常则灰度回滚 |
| 某些边界 case(如"农场工人今天做了什么")误调 web_search | 低 | 用户体验下降 | spike 已覆盖此类 case,Mode B 在 farm_status/cost_internal 类 100% 命中 |
| 测试快照失败 | 高 | CI 红 | 更新 `tests/agent/router/test_*` 中 web_search 相关 case 的期望值,这是预期行为变更 |
