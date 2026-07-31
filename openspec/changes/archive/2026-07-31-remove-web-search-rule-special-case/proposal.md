## Why

SkillRouter 对 `web_search` 做了工具级关键词二次校验,误杀 BM25+向量召回的候选。实证 (`backend/scripts/router_c_spike.py`, 10 case):"今天苏州西瓜价格是"被路由到 `get_farm_status` 而非 `web_search`,因为 `WEB_CURRENT_EVENT_TOPIC_HINTS` 缺"价格/行情/政策"等词。Mode A(纯规则)总命中率仅 50%,web_search 类 28.6%;Mode B(LLM 自选)分别 90%/100%。Layer 1 召回正常,Layer 2 用关键词规则二次校验是 bug。

## What Changes

- 删除 `app/agent/router/policy.py:_allow_model_choice_read_candidate` 中 `web_search` 特判分支,所有 read 候选一视同仁进入 Layer 3 LLM 自选
- (止血,可选)`WEB_CURRENT_EVENT_TOPIC_HINTS` 补"价格/行情/政策/上市"等词,降低迁移期误判
- 不动 `looks_like_web_search` 函数本身(留给阶段 2 一起清理)

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `agent-intent-router`: 移除 read 候选门控中对 web_search 的单工具关键词二次校验,让 BM25+向量召回结果直接进入 LLM 自选

## Impact

- 受影响代码:`backend/app/agent/router/policy.py` (~5 行删除)、`backend/app/agent/router/classifier_signals.py` (hints 表扩展,可选)
- 受影响测试:`backend/tests/agent/router/*` 需更新 web_search 相关 case 期望值
- 运行时影响:web_search 调用频率预计上升,需监控 `tools.invoked.total{skill="web_search"}` counter
- 回滚:恢复 `_allow_model_choice_read_candidate` 的 web_search 分支即可
