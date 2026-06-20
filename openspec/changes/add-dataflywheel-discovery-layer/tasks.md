## 1. 数据库与模型

- [ ] 1.1 在 `backend/app/models/agent_turn.py` 加 `risk_score`、`risk_dominant_signal`、`judge_bad_prob`、`judge_issue_type`、`judge_suggested_label` 字段
- [ ] 1.2 创建 Alembic migration `add_risk_score_to_agent_turns`
- [ ] 1.3 在 migration 中加 `risk_score` 索引（用于排序）与 `risk_dominant_signal` 索引（用于筛选）
- [ ] 1.4 跑 `alembic upgrade head` 验证 schema 应用成功
- [ ] 1.5 单测：model 字段读写、默认值（`risk_score=0.0`、`risk_dominant_signal=NULL`）

## 2. Rule Engine

- [ ] 2.1 创建目录 `backend/app/evaluation/discovery/`
- [ ] 2.2 创建 `backend/app/evaluation/discovery/rules.yaml`，写 10-15 条初始业务规则（`tool_error_ignored`、`missing_wage`、`hallucinated_execution`、`negative_feedback`、`weather_without_search` 等）
- [ ] 2.3 实现 `backend/app/evaluation/discovery/rule_engine.py`：yaml 加载、字段校验、条件 DSL 求值、`rule_score` 取 max
- [ ] 2.4 实现文件 watcher：用 `watchdog` 监听 `rules.yaml` 变更，≤ 5s 热重载，失败保持旧规则并打日志
- [ ] 2.5 接入 turn 写入路径：turn 写入后异步触发 rule engine 评估（避免阻塞 SSE 流）
- [ ] 2.6 评估结果写入 turn 的 `rule_hits`（命中规则 ID 列表）
- [ ] 2.7 单测覆盖每条规则的命中与不命中场景
- [ ] 2.8 单测：yaml 格式错误时拒绝启动、热更新失败保持旧规则

## 3. LLM Judge Worker

- [ ] 3.1 实现 `backend/app/evaluation/discovery/judge_worker.py`：查询前 24h 未标注且 `judge_bad_prob IS NULL` 的 turn
- [ ] 3.2 实现 Judge Prompt 模板（输出 JSON：`bad_prob`、`issue_type`、`suggested_label`、`evidence`）
- [ ] 3.3 接入 `backend/app/core/llm_client_manager.py` 路由 Claude Haiku
- [ ] 3.4 并发控制：`asyncio.Semaphore(32)`
- [ ] 3.5 实现成本累计器：从 LLM client 的 token usage 推算 USD，按月汇总
- [ ] 3.6 实现成本上限降级：月累计 > $200 跳过 Judge 调用 + 发告警
- [ ] 3.7 跳过 `label_source='human'` 的 turn
- [ ] 3.8 写入 `judge_bad_prob`、`judge_issue_type`、`judge_suggested_label`
- [ ] 3.9 完成后异步触发 `risk_scorer` 重算
- [ ] 3.10 配置 cron job（systemd timer 或 APScheduler）：每天 02:00 触发
- [ ] 3.11 单测：Judge 正常执行、成本上限降级、跳过人工标注、JSON 解析失败兜底

## 4. Risk Scorer

- [ ] 4.1 实现 `backend/app/evaluation/discovery/risk_scorer.py`：`risk_score = max(rule_score, judge_bad_prob)`
- [ ] 4.2 写入 `risk_score`、`risk_dominant_signal`（`rule` / `judge` / `NULL`）
- [ ] 4.3 在 rule_engine 触发后同步调用
- [ ] 4.4 在 judge_worker 完成后异步调用
- [ ] 4.5 单测：规则主导、Judge 主导、两者为空、边界值（0/1）

## 5. API 改造

- [ ] 5.1 在 `backend/app/api/admin_dataflywheel.py` 列表 API 加 `sort_by` 参数（`risk` / `time`，默认 `risk`）
- [ ] 5.2 加 `min_risk` 过滤参数（默认 0.0，开启隐藏开关时为 0.3）
- [ ] 5.3 加 `severity` 过滤参数（`P0` / `P1` / `all`）
- [ ] 5.4 响应 schema 加 `risk_score`、`risk_dominant_signal`、`rule_hits`、`judge_*` 字段
- [ ] 5.5 API 集成测试：默认排序、时间排序、隐藏低风险、P0 筛选

## 6. 工作台前端改造

- [ ] 6.1 修改 `admin-web/src/pages/DataFlywheel/` 列表组件：默认 `sort_by=risk`
- [ ] 6.2 加「隐藏低风险（score < 0.3）」Checkbox，URL query `min_risk=0.3`
- [ ] 6.3 修改会话卡片：显示 `Risk: 0.xx` 数值 + 主导信号图标（🔧 rule / 🤖 judge）
- [ ] 6.4 P0 卡片视觉强调：红色边框或徽标
- [ ] 6.5 加「P0 严重」筛选入口（顶部 toolbar）
- [ ] 6.6 支持 URL 参数 `?sort=time|risk` 切换排序（灰度切流）
- [ ] 6.7 前端单测：默认排序、隐藏开关、卡片显示、P0 视觉、URL 参数回退

## 7. 集成测试与灰度

- [ ] 7.1 集成测试：turn 写入 → rule 命中 → judge 评估 → risk_score 更新 → 工作台显示，端到端
- [ ] 7.2 历史样本回归：用近 30 天 100 条已知坏case 验证 rule + judge 综合 precision@100 > 0.7
- [ ] 7.3 基于标注员反馈微调 `rules.yaml` 权重
- [ ] 7.4 灰度部署：先放给 2 个标注员试用 1 周
- [ ] 7.5 监控 Judge 月成本是否接近 $200 阈值
- [ ] 7.6 更新 `farm-manager-design-spec/01_正式设计/06_数据飞轮与评测.md` § 9 状态：设计中 → 已落地
- [ ] 7.7 更新 `.claude/rules/` 与 `docs/architecture/boundaries.md`：新增 `app/evaluation/discovery/` 的依赖方向说明
