## 1. Trace 基础设施

- [ ] 1.1 创建 `app/core/trace_context.py` — 定义 `TraceInfo` dataclass（request_id, session_id, farm_id, created_at）+ `contextvars.ContextVar` 全局变量
- [ ] 1.2 实现 `init_trace(session_id, farm_id) -> TraceInfo` — 初始化上下文，生成 request_id
- [ ] 1.3 实现 `get_trace() -> TraceInfo | None` — 获取当前上下文
- [ ] 1.4 实现 `clear_trace()` — 清除上下文
- [ ] 1.5 创建 `app/core/trace_collector.py` — `TraceCollector` 类，`record()` 方法将 trace 数据放入内存队列
- [ ] 1.6 实现内存队列（`asyncio.Queue`，最大 1000 条）+ 后台 worker（每 5s 或 20 条批量写入 SQLite）
- [ ] 1.7 实现 `get_trace_collector()` / `init_trace_collector()` 全局单例管理
- [ ] 1.8 创建 `app/core/trace_dao.py` — `TraceDAO` 类，批量 INSERT trace_records + 累加 token_daily_stats
- [ ] 1.9 实现 `record_batch(traces: list[dict])` — 批量 INSERT trace_records
- [ ] 1.10 实现 `accumulate_token_stats(farm_id, date, model, call_type, prompt_tokens, completion_tokens)` — UPSERT token_daily_stats

## 2. 数据模型 + 迁移

- [ ] 2.1 创建 `app/models/trace.py` — `TraceRecord` SQLAlchemy 模型（对应 trace_records 表）
- [ ] 2.2 创建 `app/models/token_stats.py` — `TokenDailyStats` SQLAlchemy 模型（对应 token_daily_stats 表）
- [ ] 2.3 在 `app/models/__init__.py` 导入新模型
- [ ] 2.4 生成并执行 Alembic 迁移

## 3. Graph 埋点

- [ ] 3.1 `app/agents/advisor.py` — `invoke_advisor` 入口调用 `init_trace()`，请求结束调用 `clear_trace()`
- [ ] 3.2 `app/agents/advisor.py` — `stream_advisor` 同理
- [ ] 3.3 `app/agents/graph.py` — `_llm_node` 开始时记录 prompt_render trace（render_prompt 结果）
- [ ] 3.4 `app/agents/graph.py` — `_llm_node` LLM 调用前后记录 llm_call trace（input/output/token/耗时）
- [ ] 3.5 `app/agents/graph.py` — `_parallel_tool_node` 每个 Skill 调用前后记录 skill_call trace
- [ ] 3.6 `app/agents/graph.py` — 在 trace context 中追踪 round_index（每进入 _llm_node 时 +1）

## 4. Token 配额检查

- [ ] 4.1 `app/core/config.py` — 新增 `TokenQuotaConfig`（daily_limit: int = 100000, over_quota_action: str = "warn"）
- [ ] 4.2 `app/core/config.py` — `Settings` 新增 `token_quota: TokenQuotaConfig` 字段
- [ ] 4.3 创建 `app/services/quota_service.py` — `check_quota(farm_id) -> bool` 查询当日用量
- [ ] 4.4 `app/services/quota_service.py` — `get_today_usage(farm_id) -> int` 从 token_daily_stats 聚合
- [ ] 4.5 `app/agents/graph.py` — `_llm_node` 调用 LLM 前检查配额，超配额按策略处理

## 5. Trace TTL 清理

- [ ] 5.1 `app/core/trace_cleaner.py` — `clean_expired_traces()` 清理 7 天前的 trace_records + 90 天前的 token_daily_stats
- [ ] 5.2 `app/main.py` — 启动时执行一次清理
- [ ] 5.3 `app/main.py` — 注册 `lifespan` 定时任务，每日 00:00 执行清理

## 6. Admin Trace API

- [ ] 6.1 创建 `app/api/admin_trace.py` — `GET /admin/traces` 查询接口（request_id/session_id/farm_id/limit 筛选）
- [ ] 6.2 `GET /admin/traces/{request_id}/timeline` — 按 round 分组返回 Gantt 图数据
- [ ] 6.3 `GET /admin/traces/{request_id}/nodes/{node_id}` — 节点详情（完整 input/output）
- [ ] 6.4 `DELETE /admin/traces` — 按日期清理

## 7. Admin Token Stats API

- [ ] 7.1 创建 `app/api/admin_stats.py` — `GET /admin/stats/tokens` 近 N 天汇总
- [ ] 7.2 `GET /admin/stats/tokens/daily` — 指定日期明细（by model/by call_type）

## 8. Admin Config API

- [ ] 8.1 创建 `app/api/admin_config.py` — `GET /admin/skills` 列出所有注册 skill
- [ ] 8.2 `GET /admin/prompts` 列出所有 prompt 模板
- [ ] 8.3 `GET /admin/prompts/{name}/render` 渲染预览
- [ ] 8.4 `POST /admin/prompts/reload` 热加载
- [ ] 8.5 `GET /admin/config` 运行时配置查看（key 脱敏）
- [ ] 8.6 `POST /admin/config/validate-key` API key 连通性测试
- [ ] 8.7 `POST /admin/cache/clear` 清空缓存
- [ ] 8.8 `app/main.py` — 注册 `/admin/*` 路由（带 `/admin` 前缀）

## 9. 端到端验证

- [ ] 9.1 测试：对话后 trace_records 有记录（llm_call + skill_call + prompt_render）
- [ ] 9.2 测试：`GET /admin/traces/{request_id}/timeline` 返回正确的 Gantt 数据
- [ ] 9.3 测试：token_daily_stats 正确累加
- [ ] 9.4 测试：`GET /admin/stats/tokens` 返回正确的汇总
- [ ] 9.5 测试：超配额时按策略处理（reject/warn）
- [ ] 9.6 测试：`GET /admin/config` key 脱敏显示
- [ ] 9.7 测试：`POST /admin/cache/clear` 清空缓存后下次请求重新获取
- [ ] 9.8 测试：TTL 清理正确删除过期数据
- [ ] 9.9 ruff check + ruff format 通过
