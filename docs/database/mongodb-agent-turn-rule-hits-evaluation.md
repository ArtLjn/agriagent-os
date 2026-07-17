# agent_turns.rule_hits 拆分迁移评估

> 评估时间：2026-06-26。结论适用于 MongoDB 文档存储第 2 期。

## 结论

第 2 期不迁移 `agent_turns.rule_hits`，继续由 MySQL `agent_turns.rule_hits` 作为运行时读写来源。当前字段与 `rule_score`、`risk_score`、`risk_dominant_signal`、`risk_severity`、judge 结果和 Data Flywheel 多维筛选强耦合，单独拆到 Mongo 会引入跨库一致性和分页筛选复杂度，收益不足以覆盖风险。

后续若需要减轻 `agent_turns` JSON 负担，建议先做离线统计和样本物化，不直接进入在线 `mongo-read`。

## 写入路径

- `app.evaluation.discovery.rule_engine.evaluate_turn()`：规则引擎根据 turn 上下文计算 `hit_rule_ids`，写回 `rule_hits`、`rule_score`、`risk_score`、`risk_dominant_signal`、`risk_severity`。
- `app.services.agent_turn_service.finish_turn()`：补全助手消息后调用规则评估。
- `app.services.agent_turn_service.mark_event_range()`：事件日志范围补齐后重新调用规则评估。
- `app.evaluation.discovery.judge_worker._apply_judge_result()`：不写 `rule_hits`，但读取 `rule_score` 后刷新综合风险分。

## 读取路径

- `app.platforms.data_flywheel.service`：样本列表和详情直接返回 `rule_hits`，并基于 rule hits 生成 issue candidates。
- `app.platforms.data_flywheel.review_issue_chain.service`：按 `risk_score`、`risk_severity` 筛选候选，结合 rule hits 生成问题链上下文。
- `app.platforms.data_flywheel.review_issue_chain.helpers`：在风险上下文、诊断摘要和证据完整性判断中读取 rule hits。
- `app.evaluation.discovery.judge_worker`：构造 judge 输入时读取 rule hits；低风险闲聊判断也依赖 rule hits 是否为空。
- 测试覆盖包括 `backend/tests/services/test_agent_turn_service.py`、`backend/tests/api/test_admin_data_flywheel.py`、`backend/tests/api/test_admin_data_flywheel_review_issue_chain_closure.py`。

## 数据特征与统计脚本

本期没有把统计脚本纳入运行时路径。建议上线前在只读副本执行：

```sql
SELECT
  COUNT(*) AS total_turns,
  SUM(CASE WHEN JSON_LENGTH(rule_hits) = 0 THEN 1 ELSE 0 END) AS empty_rule_hits,
  AVG(JSON_LENGTH(rule_hits)) AS avg_rule_hits,
  MAX(JSON_LENGTH(rule_hits)) AS max_rule_hits
FROM agent_turns;
```

若 MySQL 方言不支持 `JSON_LENGTH`，可导出 `id, rule_hits` 后用离线脚本统计空数组比例、平均长度、最大长度和 P95 长度。

## 方案对比

| 方案 | 收益 | 风险 | 结论 |
| --- | --- | --- | --- |
| 保持 MySQL `agent_turns.rule_hits` | 无运行时改造；Data Flywheel 查询保持单库一致 | JSON 字段仍留在 MySQL | 第 2 期采用 |
| 独立 `agentTurnRuleHits` 集合 | 可减轻 MySQL JSON 字段；方便按 rule id 做文档分析 | turn 与 rule hits 跨库一致性、分页筛选和回滚复杂 | 后续单独 OpenSpec 评估 |
| 物化到 Data Flywheel 样本文档 | 适合离线样本和评测，不影响在线 turn | 样本不是 source of truth，需定义刷新策略 | 可作为后续低风险优化 |

## 后续建议

1. 先运行数据统计，确认空数组比例、平均长度、最大长度和 P95 长度。
2. 若 `rule_hits` 平均长度很低，继续保留 MySQL。
3. 若需要按 rule id 做高频分析，优先新增离线物化或分析集合，不改变 `AgentTurn` 在线读写。
4. 若未来拆分为 `agentTurnRuleHits`，必须单独设计双写、补偿、回填、校验和 Data Flywheel 查询改造。
