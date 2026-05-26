## Context

当前 LangGraph 执行流程 (`graph.py`)：
```
用户消息 → _llm_node (渲染 prompt + 调用 LLM) → _should_continue
         → _parallel_tool_node (执行 Skill) → _llm_node (循环)
```

没有任何中间数据被记录。`logger.info` 只打印了 skill 名称和截断的返回值，无法回溯完整链路。

参考 product-agent 的 trace 系统：
- `trace_context.py`：`contextvars` + `TraceInfo(session_id, record_id, request_id, parent_id, depth)`
- `trace_collector.py`：每次调用记录 `node_type + input/output + timing`
- `monitor.html`：Gantt 图按轮次展示执行链路，点击节点看详情
- `metrics.py`：Prometheus 指标（我们用 SQLite 简化替代）

关键约束：
- 不能影响正常请求性能（trace 写入必须异步/批量）
- SQLite 存储，不引入新依赖
- trace 数据量会增长，需要 TTL 自动清理策略

## Goals / Non-Goals

**Goals:**
- 每次对话请求自动记录完整执行链路（LLM 调用、Skill 调用、prompt 渲染）
- 按轮次 (round) 展示 Gantt 图时间线（前端可消费的 API）
- 记录每次 LLM 调用的 token 消耗（prompt_tokens / completion_tokens / total_tokens）
- 按用户统计日/月 token 用量，支持配额检查
- 提供 Admin API 供前端查询 trace 和统计数据

**Non-Goals:**
- 不做 Prometheus 指标（SQLite 足够）
- 不做实时 WebSocket 推送 trace（查询式 API 即可）
- 不做前端 UI 重写（单独 change 处理）
- 不做用户认证系统（单独 change 处理，当前 farm_id=1）
- 不做 trace 数据导出（后续可加）

## Decisions

### D1: contextvars 链路追踪（借鉴 product-agent）

**选择**: 复用 product-agent 的 `contextvars` 模式。每次对话请求生成 `request_id`，每个节点（LLM/Skill）生成子 `node_id`。

```python
@dataclass
class TraceInfo:
    request_id: str       # 一次对话请求唯一 ID
    session_id: str       # 会话 ID（预留，当前为 farm_id）
    farm_id: int
    created_at: float     # 请求开始时间

_trace_context: contextvars.ContextVar[TraceInfo | None] = contextvars.ContextVar(...)
```

**备选方案**:
- A) 全局字典 + threading.local → asyncio 场景不安全
- B) 在 AgentState 中传递 → LangGraph 的 state 已经在传递，但 trace 是横切关注点，不应污染业务 state

**理由**: `contextvars` 是 Python 异步链路追踪的标准方案，product-agent 已验证可行。

### D2: SQLite 存储 + 异步批量写入

**选择**: trace 数据写入 SQLite，使用内存队列 + 后台 worker 批量写入。

```python
# 写入流程：
graph.py 埋点 → TraceCollector.record() → 内存 queue
                                          ↓
                                    后台 worker（每 5s 或积累 20 条）→ 批量 INSERT
```

**备选方案**:
- A) 每次同步写入 SQLite → 阻塞请求，影响延迟
- B) 写入文件日志 → 查询不便，需要额外解析
- C) MongoDB（product-agent 方案）→ 引入新依赖

**理由**: 内存队列解耦，不阻塞请求。SQLite 查询灵活，项目已使用。

### D3: 数据模型

```sql
-- 执行链路记录
trace_records (
    id INTEGER PRIMARY KEY,
    request_id TEXT NOT NULL,        -- 一次对话请求
    session_id TEXT,                 -- 会话 ID（预留）
    farm_id INTEGER NOT NULL,
    round_index INTEGER DEFAULT 0,   -- 第几轮 LLM 循环（0=首次, 1=tool后第二次...）
    node_type TEXT NOT NULL,         -- 'llm_call' / 'skill_call' / 'prompt_render'
    node_name TEXT NOT NULL,         -- skill 名 / 'llm' / 'system_prompt'
    parent_id TEXT,                  -- 父节点 request_id（预留嵌套）
    depth INTEGER DEFAULT 0,
    input_data TEXT,                 -- JSON: 传给节点的参数
    output_data TEXT,                -- JSON: 节点返回值（截断到 4000 字符）
    start_time REAL NOT NULL,        -- time.time()
    end_time REAL,
    duration_ms INTEGER,
    token_usage TEXT,                -- JSON: {prompt_tokens, completion_tokens, total_tokens}
    status TEXT DEFAULT 'success',   -- 'success' / 'error'
    error_message TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)

-- Token 日用量汇总（定时聚合，避免每次查 trace_records）
token_daily_stats (
    id INTEGER PRIMARY KEY,
    farm_id INTEGER NOT NULL,
    date TEXT NOT NULL,              -- 'YYYY-MM-DD'
    model TEXT NOT NULL,
    call_type TEXT NOT NULL,         -- 'chat' / 'daily_advice' / 'report'
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    request_count INTEGER DEFAULT 0,
    estimated_cost_cny REAL DEFAULT 0.0,
    UNIQUE(farm_id, date, model, call_type)
)
```

### D4: 埋点位置

在 `graph.py` 的三个关键位置埋点：

1. **`_llm_node`** — 记录 LLM 调用（input=prompt+messages 摘要, output=AIMessage 摘要, token_usage）
2. **`_parallel_tool_node`** — 记录每个 Skill 调用（input=args, output=result 摘要, 耗时）
3. **`_llm_node` prompt 渲染** — 记录渲染后的 system prompt（便于调试 "prompt 注入对不对"）

round_index 追踪：在 `AgentState` 中新增可选字段 `round_index: int = 0`，`_llm_node` 每次进入时 +1。

### D5: Token 配额检查

**选择**: 在 `_llm_node` 调用 LLM 前检查 `token_daily_stats` 当日用量。

```python
# 检查流程
quota = get_daily_quota(farm_id)  # 默认 100,000 tokens/天
used = get_today_usage(farm_id)
if used >= quota:
    if strategy == "reject":
        return {"messages": [AIMessage(content="今日用量已达上限，明天再来吧")]}
    elif strategy == "downgrade":
        llm = get_llm(cheap_model=True)  # 切到更便宜模型
```

**备选方案**:
- A) 不做配额检查，事后统计 → 无法防滥用
- B) 每次调用后检查 → 无法预防超限

**理由**: 当前单用户（farm_id=1）配额检查简单。后续多用户时只需扩展 quota 表。

### D6: TTL 自动清理

**选择**: trace 数据保留 7 天，token 统计保留 90 天。启动时 + 每日定时清理。

**理由**: trace 数据量大（每次对话 5-15 条记录），7 天后调试价值极低。token 统计需要月度对比，保留 90 天。

### D7: Admin API 设计

```
GET  /admin/traces?request_id=&session_id=&farm_id=&limit=   # 查询 trace 链路
GET  /admin/traces/{request_id}/timeline                      # Gantt 图数据（按 round 分组）
GET  /admin/stats/tokens?farm_id=&days=                       # Token 用量统计
GET  /admin/stats/tokens/daily?farm_id=&date=                 # 指定日期明细
GET  /admin/skills                                            # 所有注册 skill 列表
GET  /admin/prompts                                           # 所有 prompt 模板
GET  /admin/prompts/{name}/render                             # 渲染预览
POST /admin/prompts/reload                                    # 热加载
GET  /admin/config                                            # 运行时配置（key 脱敏）
POST /admin/config/validate-key?service=                      # 验证 key 连通性
POST /admin/cache/clear                                       # 清空缓存
DELETE /admin/traces?before=                                   # 清理历史 trace
```

## Risks / Trade-offs

- **[trace 写入影响性能]** → 异步队列 + 批量写入，请求线程零阻塞。队列满时丢弃（不丢失主功能）
- **[SQLite trace 表膨胀]** → 7 天 TTL 自动清理。估算：日均 100 次对话 × 10 节点 × 7 天 = 7000 行，SQLite 轻松处理
- **[token 统计延迟]** → 日用量从 `token_daily_stats` 聚合表读取（每次 LLM 调用后累加），非实时查 trace 表
- **[round_index 追踪不准]** → 当前 `micro_compact` 会压缩旧 tool result，但不影响 round 计数。round_index 只记在 trace 中，不污染 LangGraph state（改为 trace context 中追踪）
