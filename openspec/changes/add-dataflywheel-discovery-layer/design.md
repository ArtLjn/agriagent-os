## Context

当前 DataFlywheel 已落地列表/详情/标注/case draft（见 [agent-evaluation-foundation](../../../openspec/specs/agent-evaluation-foundation/spec.md) 和 [failure-repair-pack-export](../../../openspec/specs/failure-repair-pack-export/spec.md)）。痛点：

- 列表默认按 `created_at DESC`，标注员要从全量会话中人工捞坏例
- 农场场景下 **95%+ 是正常会话**（"你好"、"今天天气怎么样"），标注 ROI 极低
- 每日标注 < 20 条；反馈延迟 > 3 天

部署约束：2C4G 单机；MySQL + JSONL；明确**不引入新基础设施**（Kafka/Flink/向量库均禁止）。

## Goals / Non-Goals

**Goals:**

- 标注员默认看 `risk_score DESC` 排序，而非时间倒序
- 自动隐藏低风险会话（`risk_score < 0.3`）
- P0 问题（幻觉执行 / 工具错误被忽略 / 业务关键字段缺失 / 安全）顶置告警
- MVP 1 周上线（4.5 人日）
- 月成本 ≤ $200，超限自动降级
- Judge 不污染真值，与 `agent-evaluation-foundation` § 自动标注三层一致

**Non-Goals:**

- 不做加权融合评分（避免单强信号被弱信号稀释）
- 不做 GBDT / 在线学习（1000+ 标注前学不到稳定权重）
- 不做聚类（V2 触发：1000+ 标注或误判率 > 30%）
- 不做向量库 / Embedding 索引
- 不做实时流（用 cron 即可）
- 不修改现有标签体系
- 不替代人工真值

## Decisions

### D1: 2 级过滤 + 取 max 评分（vs 6 级漏斗 / 加权融合 / GBDT）

**选择**：2 级（Rule + Judge）+ `risk_score = max(rule_score, judge_bad_prob)`

**理由**：

- 取 max 而非加权：避免一个强信号被多个弱信号稀释（例：幻觉执行 rule_score=0.95，加权会被其他 0 分信号拉低）
- 不做 6 级漏斗（规则/行为/Outlier/Judge/聚类/排序）：当前数据量（万级/天）不需要
- 不做 GBDT：1000+ 标注前学不到稳定权重

**Alternatives considered**：

- 加权融合：单强信号被稀释，rejected
- 6 级漏斗：过度设计，rejected
- LightGBM 二分类：标注数据不够，rejected

### D2: Rule Engine 在线，LLM Judge 批处理

**选择**：

- Rule Engine：在 turn 写入时同步触发（< 1ms）
- LLM Judge：每天 02:00 cron 批处理

**理由**：

- 规则便宜，可在线（避免离线 task 延迟）
- Judge 贵（~$0.005/session），批处理合并
- 不需要实时 Judge（标注员看的是当天数据，T+1 可接受）

**Alternatives considered**：

- 全在线 Judge：成本爆炸（10k/天 → $50/天），rejected
- 全批处理 Rule：规则便宜没必要批处理，rejected

### D3: rules.yaml 走配置中心，不发版

**选择**：yaml 文件 + 文件 watcher 热更新

**理由**：

- 标注员发现新坏case 模式时，加规则不发版
- 避免代码改动 → 测试 → 部署的循环
- yaml 简单可读，无需 DSL

**Alternatives considered**：

- 写死代码：更新慢，rejected
- DSL 引擎（如 drools）：过度设计，rejected

### D4: Judge 用 Claude Haiku，不用 Sonnet

**选择**：Haiku

**理由**：

- 单 session 判断任务简单（输入 < 2k token，输出 JSON）
- Haiku 成本 ~$0.005，Sonnet ~$0.03
- 1 万 session/天，Haiku $50/天 vs Sonnet $300/天

**Alternatives considered**：

- Sonnet：6x 成本，质量提升不显著，rejected
- 本地小模型：部署成本 > API 成本，rejected

### D5: 工作台只改 3 处，不重构 Tab

**选择**：

1. 默认排序改 `risk_score DESC`
2. 加「隐藏低风险」开关
3. 卡片显示风险分数 + 主导信号图标

不重构现有 Tab 结构（全部用户会话 / 规则候选 / AI预判 / 已标注问题）

**理由**：

- 最小化前端改动
- 渐进升级，标注员不重新学习

**Alternatives considered**：

- 加 🔥高风险 / 🔧工具异常 / 📦问题簇 多个新 Tab：过度设计，rejected

### D6: P0 / P1 二级分级（vs P0/P1/P2/P3 四级）

**选择**：P0 + P1

**理由**：

- MVP 阶段二级够用
- P2/P3（措辞、格式）当前不是 ROI 重点

### D7: Judge 结果不作为最终真值

**选择**：Judge 仅作 risk_score 输入，最终真值仍来自人工标注

**理由**：

- 与 `agent-evaluation-foundation` § 自动标注三层一致
- 防止「同模型既生产又评分」的自我强化偏见
- Judge 错误只会影响排序，不会污染数据集

## Risks / Trade-offs

- **Judge 误判导致坏case 排在末尾被忽略** → 缓解：保留 5% 随机采样进入标注池（防漂移漏检），保留全量列表 Tab 作 fallback
- **规则覆盖率低，遗漏新型坏case** → 缓解：每周复盘未命中坏case，补充规则
- **risk_score 字段加索引影响写入性能** → 缓解：MySQL B-tree 索引，单字段，写入开销 < 1ms
- **Judge 成本超预算** → 缓解：月成本 > $200 自动降级到 rule-only 模式 + 告警
- **rules.yaml 热更新失败** → 缓解：文件 watcher 重启时全量重载 + 校验，失败保持旧规则
- **标注员抵触新排序** → 缓解：URL 参数 `?sort=time|risk` 并存，灰度切流

## Migration Plan

**Day 1-2（后端）**：

1. Alembic migration：`agent_turns` 加 `risk_score` / `risk_dominant_signal` / `judge_bad_prob` / `judge_issue_type` / `judge_suggested_label` 字段 + 索引
2. 部署 rule engine（同步触发 + rules.yaml 加载 + watcher）
3. 部署 judge worker（cron 调度 + Haiku client + 成本累计器）

**Day 3-4（前端）**：

4. 工作台列表 API 加 `sort_by` / `min_risk` 参数
5. 前端列表组件改造（默认排序、隐藏开关、卡片显示）

**Day 5（灰度）**：

6. 灰度环境验证：rules 命中、judge 输出、risk_score 计算、工作台显示
7. 调规则权重（基于标注员反馈）

**Rollback**：

- DB migration：`alembic downgrade -1`
- Rule engine：`rules.yaml` 加 `enabled: false` 关闭同步触发
- Judge worker：禁用 cron job
- 前端：URL 参数 `?sort=time` 回退到时间排序

## Open Questions

- Q1: rules.yaml 放在 `app/evaluation/discovery/rules.yaml` 还是 `config/rules.yaml`？倾向前者（业务规则与代码同包，与 skill.md 治理一致）
- Q2: Judge prompt 版本管理是否走现有 prompt management（`prompt/` 目录）？倾向是
- Q3: 标注员对风险分数显示形式的偏好（数字 / 进度条 / 雷达图）？MVP 倾向数字 + 主导信号图标（最简），收集反馈后调整
