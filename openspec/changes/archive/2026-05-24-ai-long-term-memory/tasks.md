# Tasks: AI 长时记忆 — 全阶段

## Phase 1: 增强 Skills（当前进行）

### 1.1 增强 cost-summary Skill
- [x] 将 `cycle_id` 改为可选参数
- [x] 新增 `farm_id` 参数（从 context 获取）
- [x] 新增 `date_range` 参数（start_date, end_date）
- [x] 新增 `record_type` 参数（cost/income/all）
- [x] 新增 `category` 参数（按分类筛选）
- [x] 新增 `group_by` 参数（category/month/none）
- [x] 更新 Skill 描述，让 LLM 知道新能力

### 1.2 新增 cost-analytics Skill
- [x] 创建 `get_cost_analytics` Skill
- [x] 支持全局查询（不依赖 cycle_id）
- [x] 支持同比/环比计算
- [x] 返回结构化分析结果（分类排行、趋势）

### 1.3 增强现有 Skills 的 farm_id 支持
- [ ] farm-logs Skill：支持 farm_id 过滤
- [ ] crop-cycle Skill：支持 farm_id 过滤

### 1.4 更新 Agent System Prompt
- [x] 更新 system prompt，描述增强后的 Skill 能力
- [x] 引导 LLM 在适当场景调用分析类 Skill

### 1.5 API 与前端适配
- [x] 完成 `/costs/parse` AI 帮记接口
- [x] 前端 CostCreateScreen 增加 AI 输入区域
- [x] 前端 CostListScreen 分类归档汇总

---

## Phase 2: 记忆摘要

### 2.1 数据模型设计
- [ ] 创建 `UserProfileSummary` 数据库模型
- [ ] 字段：farm_id、summary_text、data_hash、created_at、updated_at
- [ ] 创建迁移脚本

### 2.2 摘要生成策略
- [ ] 实现 `generate_farm_summary(farm_id)` 函数
- [ ] 摘要内容模板：
  - 农场概览（周期数量、主种作物）
  - 本年收支总览（总支出、总收入、净利润）
  - 最大支出项 TOP3
  - 最近农事活动
  - 当前天气关注点
  - 近期异常提醒（支出突增等）
- [ ] 使用 LLM 生成自然语言摘要（非纯数据拼接）

### 2.3 定时任务/增量更新
- [ ] 选择触发方式：
  - 方案 A：APScheduler 定时任务（每天凌晨生成）
  - 方案 B：数据变更时触发（记一笔后增量更新）
- [ ] 实现数据变更监听（SQLAlchemy event）
- [ ] 实现增量更新逻辑（只更新变更部分）
- [ ] 防抖动：30 秒内多次变更只生成一次摘要

### 2.4 System Prompt 注入
- [ ] 修改 `graph.py` 的 `_llm_node`
- [ ] 每次对话前查询最新摘要
- [ ] 将摘要注入 system prompt：
  ```
  用户农场概况：
  {summary_text}
  
  以上信息帮助你更好地理解用户背景，回答时请自然地引用相关数据。
  ```

### 2.5 前端展示
- [ ] 在 AgentChatScreen 增加"农场概况"快捷卡片
- [ ] 点击可查看完整摘要

---

## Phase 3: 向量语义检索

### 3.1 技术选型
- [ ] 评估方案：
  | 方案 | 优点 | 缺点 |
  |------|------|------|
  | pgvector | 与现有 PG 一体，事务支持 | 需升级 PG，大向量性能一般 |
  | Chroma | 轻量，API 简单 | 额外服务，需维护 |
  | SQLite + sqlite-vec | 零依赖，文件存储 | 性能有限，不适合高并发 |
- [ ] 决策并记录

### 3.2 文本化策略
- [ ] 设计记录文本化模板：
  ```
  农事记录："{date} 在 {cycle_name} 进行了 {operation}，{note}"
  成本记录："{date} {type} {category} {amount}元，{note}"
  ```
- [ ] 实现 `textualize_records(farm_id)` 函数
- [ ] 批量文本化历史数据

### 3.3 向量化流水线
- [ ] 选择 Embedding 模型（DashScope / OpenAI / 本地）
- [ ] 实现 `embed_text(text)` 接口封装
- [ ] 实现批量向量化任务
- [ ] 新记录自动向量化（异步队列或事件触发）

### 3.4 检索接口
- [ ] 实现 `semantic_search(query, farm_id, limit=10)`
- [ ] 支持混合检索：向量相似度 + 关键词过滤
- [ ] 返回带相似度分数的结果

### 3.5 与 Agent 集成
- [ ] 新增 `semantic_search` Skill
- [ ] Skill 描述："语义搜索农事记录和成本记录"
- [ ] Agent 回答"我上次施肥是什么时候"时自动调用

### 3.6 多用户隔离
- [ ] 向量库 metadata 包含 farm_id
- [ ] 检索时过滤 farm_id
- [ ] 每个 farm 独立 collection / namespace

---

## 各阶段依赖关系

```
Phase 1: 增强 Skills
    │
    ▼
Phase 2: 记忆摘要（依赖 Phase 1 的 farm_id 传递）
    │
    ▼
Phase 3: 向量检索（依赖 Phase 2 的文本化策略）
```

## 优先级建议

1. **P0（立即）**: Phase 1 未完成项（farm-logs / crop-cycle 的 farm_id 支持）
2. **P1（本周）**: Phase 2 的摘要生成 + System Prompt 注入
3. **P2（下周）**: Phase 2 的增量更新优化
4. **P3（后续）**: Phase 3 技术选型 + 原型验证
