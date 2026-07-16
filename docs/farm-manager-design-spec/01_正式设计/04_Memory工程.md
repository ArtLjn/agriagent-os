# 04 — Memory 工程

> 状态：草稿 | 维护：BlockShip | 关联：[01_Agent平台架构](./01_Agent平台架构.md)、[03_Context工程](./03_Context工程.md)

---

## 1. 为什么需要 Memory

农户和 Agent 的关系是长期的：跨茬口、跨季度、跨年。Agent 必须记得：
- 这家农场种过什么、用过什么化肥、跟谁赊过账
- 用户偏好（人设、单位、语言、提醒时间）
- 历史事件（去年霜冻、上季滞销）
- 互动模式（喜欢简洁回复、偏好下午浇水建议）

短时记忆（最近对话）解决「指代消解」；长时记忆（持久化）解决「跨会话一致性」。

## 2. 部署边界（关键约束）

**当前 2C4G 部署不内置 RAG、向量数据库、embedding 模型或重排服务**。长期记忆和检索只通过 `MemoryService` 端口预留扩展点：

| 场景 | 当前行为 | 未来 |
| --- | --- | --- |
| `MemoryService.build_context()` | 返回空长期记忆上下文 | 接入外部 RAG service |
| `MemoryService.search()` | 返回空检索结果 | 接入向量检索 |
| `MemoryService.observe()` | 写入短时记忆 + JSONL event | 同步到 RAG |

未配置外部 RAG 时，Agent 靠短时记忆 + 业务工具 + Prompt 正常执行。

## 3. 架构

```
memory/
├── service.py             # MemoryService 端口，Runtime/Application 通过它访问
├── ports.py               # 接口定义
├── models.py              # 数据模型（MemoryRecord、ObservationEvent）
├── schemas.py             # Pydantic schemas
├── short_term/            # 短时记忆：会话级
│   ├── store.py
│   └── view.py
├── long_term/             # 长时记忆：跨会话
│   ├── store.py
│   └── extract.py
├── retrieval/             # 检索（预留）
│   └── empty.py
└── consolidation/         # 记忆整合：定期归纳、去重、淘汰
    ├── summarizer.py
    └── pruner.py
```

## 4. Memory 类型

| 类型 | 说明 | 示例 | 上限 | 来源 |
| --- | --- | --- | --- | --- |
| `preference` | 用户偏好 | 喜欢简洁回复、单位用亩 | 30 条 | 显式/隐式 |
| `profile` | 用户属性 | 姓名、农场规模、主要作物 | 10 条 | 显式 |
| `event` | 重要事件 | 去年霜冻、上季滞销、获奖励 | 50 条 | 显式/LLM 提取 |
| `habit` | 操作习惯 | 喜欢下午浇水建议、记账爱用「块」 | 50 条 | LLM 提取 |
| `alias` | 别名 | 「老王农资店」=「老王」 | 100 条 | LLM 提取 |
| `fact` | 业务事实 | 当前茬口番茄苗期 | — | 业务表（不入 Memory） |

超出上限时自动淘汰最旧条目（LRU + importance score）。

## 5. MemoryService 端口

```python
class MemoryService(Protocol):
    """Agent 访问记忆的唯一端口。"""

    async def build_context(self, request: MemoryContextRequest) -> MemoryView:
        """构造记忆视图，供 ContextBundle 使用。"""

    async def observe(self, event: ObservationEvent) -> None:
        """记录交互事件（用户消息、Agent 回复、工具调用）。"""

    async def search(self, query: MemoryQuery) -> list[MemoryRecord]:
        """检索记忆（当前空实现，预留 RAG）。"""

    async def store(self, record: MemoryRecord) -> None:
        """显式存储长时记忆（如用户偏好）。"""

    async def consolidate(self, session_id: str) -> ConsolidationResult:
        """会话结束时整合短时记忆到长时。"""
```

**约束**：
- Runtime 只通过此端口访问 Memory
- 不允许 Runtime 直接 import `memory.short_term.store`
- Application 提交 ObservationEvent 是允许的

## 6. 短时记忆（Short-term）

### 6.1 设计意图

```
会话开始
  ↓
读取最近 N 条 ConversationMessage（默认 10）
  ↓
构造 MemoryView.recent_messages
  ↓
随对话进行增量更新
  ↓
会话结束 → consolidation 提取要点 → 长时记忆
```

短时记忆解决：
- 指代消解（「上面那笔账」）
- 上下文延续（「再记一笔」）
- 修正（「不对，是 250 块」）

### 6.2 当前实现（[memory/short_term/store.py](../../../backend/app/memory/short_term/store.py)）

| 项 | 现状 | 问题 |
| --- | --- | --- |
| 存储 | 进程内 `deque(maxlen=12)` | 进程重启即丢；多 worker 不共享 |
| `recent_messages` | deque 读写 | 同上 |
| `session_summary` | dict 读写 | **`set_session_summary()` 全代码无调用方** → 死接口 |
| `pending_action` | dict + TTL 过期 | 同 in-memory 问题，重启丢失待确认动作 |
| `temporary_task_state` | dict | 同上 |

### 6.3 已识别问题

1. **跨进程不共享**：systemd 重启 / 多 worker 部署会导致 in-memory 数据全丢。
2. **session_summary 形同虚设**：接口已定义，没有自动生成逻辑接入。
3. **pending_action 重启丢失**：用户确认到一半进程崩了，动作状态丢失（实际由 `pending_actions` 表持久化兜底，但 short_term 这层不一致）。

### 6.4 修复方向

- **接通 `set_session_summary`**：详见 § 12 多轮失忆治理路线。
- **短期记忆从 in-memory 迁到 DB**：读写 `conversation_messages` + `conversations.summary`，单户每秒 < 1 次对话，DB 完全扛得住，**不需要 Redis**（详见 § 13 存储演进路线）。
- **pending_action 以 `pending_actions` 表为准**：short_term 仅做内存加速层。

## 7. 长时记忆（Long-term）

### 7.1 设计意图

```
显式存储（用户说「记一下我喜欢下午浇水」）
  ↓
extract.py 解析 → MemoryRecord(type=preference, content="...")
  ↓
store.py 持久化（MySQL memory_records 表）
  ↓
build_context 时按相关性 + 时间衰减取出
```

**LLM 提取**（consolidation 阶段）：

```
会话结束 → 摘要 LLM 分析整段对话
  ↓
提取候选记忆：
  - 「用户说：以后都用万元为单位」→ preference
  - 「用户提到：去年因为台风损失了 3 万」→ event
  - 「用户连续 3 次让 Agent 在记账时加备注」→ habit
  ↓
写入 memory_records，importance_score = 0.3（待人工/规则确认才升）
```

### 7.2 落地实施（2026-06-19 brainstorming 后定稿）

参考 [docs/superpowers/specs/2026-06-19-knowledge-and-memory-architecture-design.md § 4](../../../docs/superpowers/specs/2026-06-19-knowledge-and-memory-architecture-design.md)。

**数据流**：与 `maybe_summarize` 共用一套异步触发钩子，一次 LLM 调用同时输出 summary + observations（节省成本）。

```
Response 节点完成
    ↓
asyncio.create_task(memory_service.extract_observations(...))
    ↓
LLM 抽取（qwen3.6 + 现有熔断器）
    ↓
分流入库：
  高置信 (≥0.85) + preference/habit/alias → 直接写 importance=0.5（待升）
  中置信 / fact/event → 候选队列 importance=0.3
```

**memory_records 表（新建，当前 long_term 是空实现）**：

```python
class MemoryRecord(Base):
    __tablename__ = "memory_records"
    id, farm_id, user_id
    type        # preference / habit / alias / event / fact
    content     # 自然语言
    importance  # 0.0-1.0
    status      # candidate / confirmed / superseded / archived
    confidence  # LLM 抽取置信度
    source      # user_explicit / llm_extracted
    superseded_by_id  # 软覆盖指针
    created_at, confirmed_at, last_referenced_at
```

**importance 流转规则**：

| 当前 | 触发 | 流转 |
| --- | --- | --- |
| candidate (0.3) | 用户主动说"对" / "以后都这样" | confirmed (0.8) |
| candidate (0.3) | 同类候选重复 N=3 次 | confirmed (0.7) |
| confirmed | 用户说"不对" / "改一下" | superseded_by 新记录 |
| 任意 | 90 天未被引用 + importance < 0.5 | archived |

**显式 vs 隐式**：
- 显式：用户说"记一下" → `source=user_explicit`，直接 confirmed (0.8)
- 隐式：LLM 抽取 → `source=llm_extracted`，走候选流程

**注入**：[context/selectors/memory.py](../../../backend/app/context/selectors/memory.py) MemorySelector 扩展查询 `WHERE status IN ('confirmed','candidate') AND importance >= 0.3 ORDER BY importance DESC, last_referenced_at DESC LIMIT 5`，作为 `memory.long_term` block 注入（priority 介于 conversation_summary 与 retrieval 之间）。

**不做**：
- ❌ 不做 embedding 相似检索（事实型偏好不需要语义匹配，SQL where 够）
- ❌ 不让候选队列无限堆积（90 天自动 archive）
- ❌ 不每轮抽取（与 summary 共触发，~12 条阈值）
- ❌ 不上 LLM-as-judge 二次校验（成本不划算，用户确认即可）

## 8. 检索（Retrieval，预留）

### 8.1 占位接口

```python
class RetrievalPort(Protocol):
    """预留 RAG 接口。"""

    async def search(self, query: str, types: list[str], top: int = 5) -> list[MemoryRecord]:
        """当前返回 []，未来接 Qdrant。"""
```

### 8.2 引入 Qdrant 的触发条件（必须同时满足）

参考 [docs/superpowers/specs/2026-06-19-knowledge-and-memory-architecture-design.md § 5](../../../docs/superpowers/specs/2026-06-19-knowledge-and-memory-architecture-design.md)。

| # | 条件 | 当前 | 触达方式 |
| --- | --- | --- | --- |
| 1 | 用户主动问农技长尾问题（"XX 病怎么治"、"XX 药稀释比例"）≥ 周均 20 条 | ❌ | trace 抽样统计 intent + 关键词 |
| 2 | 有内容运营资源（人工录入或合作方数据授权） | ❌ | 业务方确认 |
| 3 | 现有结构化表无法覆盖（不在作物模板/账单分类/物候期里） | 部分 | 由 1 推断 |
| 4 | LLM 当前对这类问题满意度 < 60% | 未知 | trace 抽样评分 |

**任一不满足 → 不引入 Qdrant**。Qdrant 资源不是约束（已调研 50 用户量内扛得住），约束是**业务驱动 + 内容来源**。

### 8.3 引入时的边界（预案，现在不做）

- `docker-compose` 加 Qdrant 服务
- 实现 `RetrievalPort` 的 Qdrant 适配器（独立模块 `backend/app/memory/retrieval/qdrant_adapter.py`）
- 内容录入工具（admin web 单独页面）
- [context/selectors/retrieval.py](../../../backend/app/context/selectors/retrieval.py) RetrievalSelector 已存在，自动消费
- **ContextBuilder / MemoryService 边界不动**

接入 RAG 时，只需实现此端口并替换 MemoryService 内部依赖。

## 9. 整合（Consolidation）

定期任务（每日凌晨）扫描近 7 天会话，运行：

1. **去重**：相似 memory（embedding 相似度 > 0.9）合并
2. **更新**：旧 memory 被新 memory 覆盖时打 `superseded_by`
3. **淘汰**：importance_score < 0.1 且 30 天未引用 → 归档
4. **升级**：高置信 LLM 提取的 memory 经人工确认后 importance → 0.8

## 10. 隐私与安全

- Memory 表的 `farm_id` 必须索引，跨农场检索禁止
- 显式偏好（用户主动说的）importance 高
- LLM 提取的隐式记忆必须打 `source=llm_extracted` 标签
- 用户可查询/删除自己的所有 memory（隐私合规预留）
- 删除农场时级联删除所有 memory

## 11. 与 Context 工程的接口

```
ContextBuilder
  ↓
调用 MemoryService.build_context(MemoryContextRequest)
  ↓
返回 MemoryView：
  ├─ recent_messages（最近对话）
  ├─ active_preferences（用户偏好）
  ├─ relevant_events（按 intent 检索的事件）
  └─ summary（会话级摘要，如有）
  ↓
注入 ContextBundle.memory
```

## 12. 多轮失忆治理路线

### 12.1 推荐方案：Running Summary + State Protect

详见 [03_Context工程 § 6.4](./03_Context工程.md#64-推荐方案running-summary--state-protect)。摘要：

| 设计点 | 选择 |
| --- | --- |
| 触发方式 | 阈值（messages ≥ 12）异步触发 |
| 摘要模式 | Running summary（追加，不重写已固定部分） |
| 摘要模型 | 复用 qwen3.6-35b-a3b（单户月成本 < ¥2） |
| 摘要存储 | `conversations.summary` + `summary_updated_at`（字段已存在，零迁移） |
| State protect | 强制保留 pending_action / 最近 Skill 关键参数 / 当前茬口 |
| 失败降级 | 复用现有熔断器，失败 fallback 到字符串截断 |

### 12.2 Phase A 最小实现路径

```
Response 节点完成
    ↓
asyncio.create_task(maybe_summarize(conversation_id))
    ↓
maybe_summarize:
    if len(messages) < 12: return
    if now - summary_updated_at < threshold: return  # 防重复
    old_messages = messages[:-6]
    summary = await llm.invoke(summary_prompt(old_messages, current_summary))
    db.update(Conversation.summary).where(id=...)
    db.update(Conversation.summary_updated_at)
    memory_service.set_session_summary(...)
```

**改动文件清单**（预估）：

| 文件 | 改动 | 行数 |
| --- | --- | --- |
| `backend/app/memory/service.py` | 加 `maybe_summarize()` | +30 |
| `backend/app/memory/summarizer.py`（新） | 封装 LLM 摘要调用 | +50 |
| `backend/app/agent/runtime/nodes.py` | Response 节点挂异步任务 | +5 |
| `backend/app/context/selectors/conversation.py` | LEFT JOIN `conversations.summary` 拼到开头 | +15 |
| `backend/app/memory/prompts/summary.md`（新） | 摘要 prompt 模板 | — |
| `backend/tests/memory/test_summarizer.py`（新） | 单测 | +80 |

总计 **~180 行新增代码，0 行迁移，0 新依赖**。

### 12.3 Phase B 扩展（按 Phase A 效果决定）

- ConversationSelector 从 6 条扩到 12 条
- `sliding_window_compact` 把 ToolMessage 替换为结构化摘要（`{skill, key_params}`）而非裸 placeholder
- ContextBuilder 默认预算从 1200 提到 1800-2000（按 token 监控调整）

### 12.4 不做什么

- ❌ 上 MemGPT / Letta（架构污染、2C4G 扛不住）
- ❌ 上向量数据库做 retrieval（spec 已声明 2C4G 不做 RAG）
- ❌ 每轮都摘要（成本爆炸，按阈值触发就够）
- ❌ 让 LLM 自治管理 memory（不可控）

## 13. 存储演进路线（Redis 决策）

### 13.1 当前阶段不上 Redis

**结论**：几个用户 + 单机 + 单进程 systemd，Redis 是纯负担。

### 13.2 Redis 的真实成本

| 成本项 | 量化 |
| --- | --- |
| 内存 | 2C4G 上 Redis 至少占 512MB-1GB，挤占 MySQL / Python |
| 运维 | 多一个进程要监控、重启、备份 |
| 一致性 | 缓存失效策略 / cache stampede 要处理 |
| 数据安全 | Redis 默认异步持久化，重启可能丢最近几秒 |
| 调试 | 多一层状态，问题排查更难 |

### 13.3 何时需要 Redis（触发条件）

满足**任意一条**才考虑：

| 触发条件 | 当前 | 何时达到 |
| --- | --- | --- |
| 多 worker / 多进程部署 | ❌ 单 uvicorn 进程 | DAU 上百、需要水平扩展 |
| Session 跨实例共享 | ❌ 单机 | 多机部署 / 蓝绿发布 |
| 短期记忆要求重启不丢 | ❌ 重启可接受 | 用户对续聊体验有强诉求 |
| 高频缓存（限流 / Prompt cache） | ❌ 量小 | QPS > 50 |
| 实时分布式锁 | ❌ 不需要 | 多端同时编辑场景 |

### 13.4 不上 Redis 怎么解决"重启失忆"

走数据库即可：
- `conversations.summary` 字段 —— 跨重启保留摘要
- `conversation_messages` 表 —— 完整对话历史
- `pending_actions` 表 —— 待确认动作

把 short_term memory 从 in-memory deque 改成查 DB：

| 查询 | 频率 | 单次成本 |
| --- | --- | --- |
| 取最近 12 条 message | 每轮 1 次 | ~5ms（有索引） |
| 取 conversations.summary | 每轮 1 次 | ~2ms |

单户每秒 < 1 次对话，DB 完全扛得住。

### 13.5 演进路线

```
Phase 3（当前，几个用户）→ DB-only，无 Redis
   ↓
Phase 5（200+ 用户，单机扛不住）→ 先优化 DB 索引 + Prompt cache
   ↓
Phase 5（200+ 用户，需要多 worker）→ 引入 Redis 仅做 session 共享
   ↓
Phase 6（多机部署）→ Redis cluster + 持久化策略
```

**禁止**：在触发条件未达时提前引入 Redis。听到"听说 Redis 好"不是引入理由。

## 14. 当前状态

- ✅ MemoryService 端口
- ✅ short_term/ 短时记忆骨架（in-memory deque，`recent_message_limit=12`）
- ✅ ObservationEvent 提交（每次对话都记录）
- ✅ Conversation 表 `summary` + `summary_updated_at` 字段已接通 running summary 自动生成与持久化（零迁移）
- ✅ `set_session_summary()` 已由 MemoryService 同步更新，保持 in-memory cache 兼容
- 🚧 long_term/ 当前是空实现（[memory/long_term/store.py](../../../backend/app/memory/long_term/store.py) 返回空 LongTermMemoryContext）—— 落地实施详见 § 7.2
- 🚧 consolidation/ 整合任务（骨架，待落地）
- 🚧 retrieval/ RAG 接入（预留空实现，触发条件详见 § 8.2）
- 🚧 extract.py LLM 自动提取（落地实施详见 § 7.2）
- 🚧 short_term 从 in-memory 迁到 DB（详见 § 6.4、§ 13.4）
- ❌ Qdrant 不上（详见 § 8.2 触发条件）

## 15. 与典型多 Agent 系统的对比

| 维度 | 典型多 Agent 系统 | Farm Manager |
| --- | --- | --- |
| 记忆类型 | habit/alias/preference/event/profile | 同 |
| 上限 | habit 50/alias 100/preference 30/event 20/profile 10 | 同（一致） |
| 存储 | 外部 RAG 服务 | 自有 MySQL + 预留 RAG 端口 |
| 检索 | 语义相似度 + confidence | 当前空，预留 |
| 跨设备共享 | 同 home_id 共享 | 同 farm_id 共享 |
| 整合 | 自动淘汰 + importance | 同 |
| Session 摘要 | 自动 LLM 摘要 | **未接通**（§ 12 待落地） |
| Redis | 平台基础设施 | **不上**（§ 13） |

## 16. 相关文档

- [01_Agent平台架构](./01_Agent平台架构.md)
- [03_Context工程](./03_Context工程.md)（特别是 § 6 压缩策略、§ 6.4 推荐方案）
- [03_接口协议/02_Agent内部接口](../03_接口协议/02_Agent内部接口.md)
- [04_相关规范/01_Prompt与人设规范](../04_相关规范/01_Prompt与人设规范.md)
- [06_项目管理/01_里程碑与路线图](../06_项目管理/01_里程碑与路线图.md)（Phase 4 智能化包含本章节落地）
- [../../../docs/superpowers/specs/2026-06-19-knowledge-and-memory-architecture-design.md](../../../docs/superpowers/specs/2026-06-19-knowledge-and-memory-architecture-design.md) — 知识与记忆架构梳理（三件事边界 + Qdrant 触发条件）
