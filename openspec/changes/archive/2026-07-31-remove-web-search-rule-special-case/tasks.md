## 1. 代码改动

- [x] 1.1 删除 `backend/app/agent/router/policy.py` `_allow_model_choice_read_candidate` 函数(web_search 特判 + 函数本身,统一对所有 read 候选返回 True 通过移除调用实现)
- [x] 1.2 在 `backend/app/agent/router/classifier_signals.py` `WEB_CURRENT_EVENT_TOPIC_HINTS` 补充:价格/行情/政策/补贴/上市/下市/热点(止血用,降低迁移期其他启发式路径误判)
- [x] 1.3 检查 `_allow_model_choice_read_candidate` 的调用方,确认删除后无死代码残留(发现额外 1 处:`backend/app/agent/router/service.py:464` 也有同性质 BM25+向量候选二次过滤,一并删除;`classifier.py:84` 是 intent 分类不删,`tool_selector.py:86` 是规则路径 not BM25+向量 不删)

## 2. 测试更新

- [x] 2.1 `backend/tests/agent/router/test_skill_router.py` 删除 2 个反模式测试(`test_internal_recent_farm_read_does_not_expose_web_search_by_default`、`test_internal_recent_worker_read_filters_web_search_vector_noise`),它们测的是被删的关键词二次过滤行为
- [x] 2.2 新增 `test_web_search_candidate_preserved_after_recall`:验证 BM25+向量召回的 web_search 候选保留(新行为)
- [x] 2.3 新增 `test_farm_blocker_with_external_price_intent_keeps_web_search`:boundary case "我农场的西瓜今天价格"含 blocker 但意图外部价格,web_search 应保留

## 3. 验证

- [x] 3.1 跑 `backend/scripts/router_c_spike.py` 在 10 case 上:Mode B(LLM 自选)总命中 90%,web_search 类 100%;Mode A(纯规则)从 50% 提升到 60%(hints 补词效果)
- [ ] 3.2 playground session 重放 "今天苏州西瓜价格是"(留给集成验证)
- [x] 3.3 跑 `tests/agent/router/` 271 个测试全过

## 4. 上线与监控

- [ ] 4.1 提交 PR,关联 `docs/specs/2026-07-31-agent-harness-design.md` 阶段 0
- [ ] 4.2 上线后 1 周观察 `web_search` 调用频率 counter,与基线对比
- [ ] 4.3 在变更记录追加"阶段 0 已实施"标记
