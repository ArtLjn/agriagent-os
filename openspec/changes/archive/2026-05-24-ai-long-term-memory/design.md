# Design: AI 长时记忆架构

## Phase 1: 增强 Skills（已完成设计，见 implementation plan）

---

## Phase 2: 记忆摘要

### 架构图

```
┌──────────────────────────────────────────────────────────────┐
│                     记忆摘要生成管线                           │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  触发方式                                                     │
│  ├── 定时任务 (APScheduler): 每天 02:00 生成                 │
│  └── 事件驱动: 成本/农事记录变更后 30s 延迟生成                │
│         │                                                    │
│         ▼                                                    │
│  ┌─────────────┐                                            │
│  │ 数据聚合     │  SQL 查询用户全部数据                        │
│  │             │  - 周期统计、收支汇总、农事频次               │
│  └──────┬──────┘                                            │
│         │                                                    │
│         ▼                                                    │
│  ┌─────────────┐                                            │
│  │ LLM 生成摘要 │  Prompt: "请用一段话总结这个农场的概况..."  │
│  │             │  输出: 自然语言摘要文本                       │
│  └──────┬──────┘                                            │
│         │                                                    │
│         ▼                                                    │
│  ┌─────────────┐                                            │
│  │ 存储 & 缓存  │  - user_profile_summaries 表               │
│  │             │  - Redis 缓存 (TTL: 1小时)                  │
│  └──────┬──────┘                                            │
│         │                                                    │
│         ▼                                                    │
│  ┌─────────────┐                                            │
│  │ System Prompt│  每次对话前读取最新摘要注入                  │
│  │ 注入        │                                            │
│  └─────────────┘                                            │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 数据模型

```python
class UserProfileSummary(Base):
    __tablename__ = "user_profile_summaries"

    id = Column(Integer, primary_key=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False, unique=True)
    summary_text = Column(Text, nullable=False)
    data_hash = Column(String(64))  # 数据指纹，用于判断是否需要更新
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
```

### 摘要内容模板

```
【农场概况】（更新于 {updated_at}）

您目前管理 {cycle_count} 个种植周期：
{active_cycles}

{current_year}年收支情况：
- 总支出：{total_cost} 元
- 总收入：{total_income} 元
- 净利润：{net_profit} 元

支出最多的三项：{top_cost_categories}
最近农事：{latest_logs}

当前关注：{weather_concern}
```

### 增量更新策略

- 计算当前数据哈希（MD5 周期数+记录数+最近记录时间）
- 与存储的 data_hash 对比
- 只有数据发生实质变化时才重新生成摘要
- 生成摘要使用 LLM，成本较高，避免频繁调用

---

## Phase 3: 向量语义检索

### 架构图

```
┌──────────────────────────────────────────────────────────────┐
│                     向量语义检索架构                           │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  数据源                                                       │
│  ├── 农事记录 → 文本化 → "2025-03-10 在1号棚西瓜施肥..."     │
│  ├── 成本记录 → 文本化 → "2025-03-15 支出 化肥 500元..."     │
│  └── 周期信息 → 文本化 → "1号棚西瓜，育苗期，开始于..."       │
│         │                                                    │
│         ▼                                                    │
│  ┌─────────────┐                                            │
│  │ Embedding   │  text-embedding-v2 / text-embedding-3      │
│  │ 模型        │  输出 1024/1536 维向量                      │
│  └──────┬──────┘                                            │
│         │                                                    │
│         ▼                                                    │
│  ┌─────────────────────────────────────────┐                │
│  │          向量数据库                      │                │
│  │  ┌─────────────────────────────────┐   │                │
│  │  │ Collection: farm_records        │   │                │
│  │  │  - id, embedding, text,         │   │                │
│  │  │    farm_id, record_type,        │   │                │
│  │  │    created_at                   │   │                │
│  │  │  - metadata filter: farm_id={}  │   │                │
│  │  └─────────────────────────────────┘   │                │
│  └─────────────────────────────────────────┘                │
│         ▲                                                    │
│         │ 相似度检索                                          │
│  ┌──────┴──────┐                                            │
│  │ 用户提问     │  "我上次施肥是什么时候"                      │
│  │             │  ↓ embedding                                  │
│  │             │  ↓ top-k 检索 (k=5, farm_id=1)               │
│  │             │  ↓ 返回最相似的记录                           │
│  └─────────────┘                                            │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 技术选型决策

推荐 **pgvector** 方案：

| 维度 | pgvector | Chroma | sqlite-vec |
|------|----------|--------|------------|
| 部署复杂度 | 低（现有PG扩展） | 中（额外服务） | 低 |
| 事务支持 | 是 | 否 | 是 |
| 多用户隔离 | 表级/行级 | collection | 表级 |
| 性能（10万条） | ~100ms | ~50ms | ~200ms |
| 维护成本 | 低 | 中 | 低 |
| 推荐度 | ★★★★★ | ★★★☆☆ | ★★★★☆ |

理由：项目已有 PostgreSQL，pgvector 是扩展而非新服务，事务支持对数据一致性很重要。

### pgvector 表设计

```sql
-- 启用扩展
CREATE EXTENSION IF NOT EXISTS vector;

-- 向量表
CREATE TABLE record_embeddings (
    id SERIAL PRIMARY KEY,
    farm_id INTEGER NOT NULL REFERENCES farms(id),
    source_type VARCHAR(20) NOT NULL,  -- 'farm_log' / 'cost_record' / 'cycle'
    source_id INTEGER NOT NULL,
    text_content TEXT NOT NULL,
    embedding vector(1024),  -- 根据模型调整维度
    created_at TIMESTAMP DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_embeddings_farm ON record_embeddings(farm_id);
CREATE INDEX idx_embeddings_vector ON record_embeddings
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
```

### 检索接口

```python
async def semantic_search(
    query: str,
    farm_id: int,
    limit: int = 10,
    source_type: str | None = None,
) -> list[dict]:
    """语义搜索农场记录。

    1. 将 query embedding
    2. 在 pgvector 中按 cosine similarity 检索
    3. 过滤 farm_id 和可选的 source_type
    4. 返回 [{id, text, similarity, source_type, source_id}]
    """
```

### 与 Agent 集成

新增 `semantic_search` Skill：

```python
class SemanticSearchSkill(Skill):
    def name(self): return "semantic_search_records"
    def description(self):
        return "语义搜索农事记录和成本记录。触发词: 上次、之前、找、搜索"
    def parameters_schema(self):
        return {
            "query": {"type": "string", "description": "搜索意图，如'上次施肥'"},
            "limit": {"type": "integer", "default": 5},
        }
```

### 流水线触发

```
用户记账/记日志
    │
    ├──► 数据入库
    │
    ├──► 文本化
    │
    ├──► Embedding 模型 → 向量
    │
    └──► 写入 pgvector
```

---

## 三阶段数据流对比

```
Phase 1 (Skills):     用户问 → LLM选Skill → SQL查 → 格式化 → 回答
                       ↑ 每次都要理解意图、选工具

Phase 2 (摘要):       用户问 → 读摘要 → LLM直接用已知信息 → 回答
                       ↑ 常见问题的答案已预置

Phase 3 (向量):       用户问 → Embedding → 向量检索 → 相关记录 → LLM整合 → 回答
                       ↑ 模糊语义匹配，不需要精确SQL
```
