## Why

农场场景下 **95%+ 的真实会话是正常会话**（"你好"、"今天天气怎么样"、"你是谁"）。当前 DataFlywheel 默认按时间倒序展示全部会话，标注员需要从大量正常会话中人工捞坏例，导致：

- 标注效率低（每日标注 < 20 条）
- 覆盖率差（"细粒度"问题被遗漏）
- 反馈延迟（从会话发生到被发现，平均 > 3 天）

目标：**从 10000 条会话中自动找出最值得标注的 100 条**，让标注员默认按风险倒序而非时间倒序查看。这是数据飞轮从「能跑」到「能转」的关键升级，对应 [design-spec 01.06 § 9](../../../farm-manager-design-spec/01_正式设计/06_数据飞轮与评测.md) 已落地设计。

## What Changes

- 新增 **Rule Engine**：10-15 条业务规则（工资缺失、工具错误被忽略、幻觉执行、负反馈词、天气查询未触发 search 等），实时打标 `< 1ms`
- 新增 **LLM Judge Worker**：Claude Haiku 每天批处理未标注 session，输出 `bad_prob` + `issue_type` + `suggested_label`
- 新增 **风险评分**：`risk_score = max(rule_score, judge_bad_prob)`，不做加权融合、不做 GBDT、不做在线学习
- 数据库：`agent_turns` 表加 `risk_score`、`risk_dominant_signal`、`judge_bad_prob`、`judge_issue_type` 字段 + 索引
- 工作台 3 处改动：①默认排序改 `risk_score DESC`；②加「隐藏低风险（score < 0.3）」开关；③卡片显示风险分数 + 主导信号图标
- P0/P1 分级：P0（幻觉执行 / 工具错误被忽略 / 业务关键字段缺失 / 安全问题）顶置告警；P1 正常排序
- Judge 不作为最终真值（与现有 `agent-evaluation-foundation` § 自动标注三层一致），仅作为 `risk_score` 的输入信号
- **不引入新基础设施**：复用 Postgres + cron + 现有 LLM client，不引入 Kafka/Flink/向量库

## Capabilities

### New Capabilities

- `dataflywheel-discovery-layer`: 为 DataFlywheel 标注工作台提供风险发现层。包含规则引擎、LLM Judge、风险评分、风险队列与工作台改造。目标是从全量真实会话中按风险倒序推送候选样本，让标注员只看值得标注的会话。

### Modified Capabilities

<!-- Discovery Layer 是上游新增能力，不改变现有 agent-evaluation-foundation（回放评测）、failure-repair-pack-export（修复包导出）、feedback-collection（用户反馈）的行为契约。其产出的 risk_score 和 judge 信号被下游标注流程消费，但不修改下游契约。 -->

## Impact

- **后端代码**：
  - 新增 `app/evaluation/discovery/`：`rule_engine.py`、`judge_worker.py`、`risk_scorer.py`、`rules.yaml`
  - 修改 `app/api/admin_dataflywheel.py`：列表 API 加 `sort_by=risk_score`、`min_risk` 过滤参数
  - 修改 `app/observability/`：在 turn 写入时触发 rule 评估（异步 task）
  - 修改 `app/models/agent_turn.py`：加 `risk_score` 等字段
- **数据库**：新增 Alembic migration（add risk_score to agent_turns）
- **前端（admin-web）**：修改 `src/pages/DataFlywheel/` 的列表与卡片组件（排序、过滤开关、风险分数显示）
- **配置**：`rules.yaml` 走配置中心（不发版更新规则）
- **运维**：cron job 配置（每天 02:00 跑 LLM Judge）
- **依赖**：复用现有 LLM client（`core/llm_client_manager.py`），无新外部依赖
- **成本**：Judge 月成本预估 ≤ $200，超限自动降级到 rule-only 模式
- **工作量**：MVP 4.5 人日（migration 0.5 + rule engine 1 + judge worker 1.5 + 工作台 1 + 灰度 0.5）
