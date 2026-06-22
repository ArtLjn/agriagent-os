## Why

`add-running-summary-compaction` 解决的是同一 session 内的多轮失忆：把窗口外历史压成 `conversations.summary`。但农户跨 session 的偏好、习惯和事实仍然不会沉淀，例如"我喜欢下午浇水"、"记账用万元"、"老王就是王师傅"。

当前 `memory/long_term/` 仍为空实现，用户每次开启新会话都要重新说明这些信息。本提案从 running summary 提案中拆出，专注落地长期记忆抽取、确认、注入与归档。

## What Changes

- **新增**：`memory_records` 表（5 类记忆：preference / habit / alias / event / fact，含 status / importance / confidence / source / superseded_by_id 字段）+ Alembic 迁移
- **新增**：`backend/app/memory/extractor.py` 与 `memory/prompts/observations.md`，从对话中抽取长期记忆候选
- **新增**：候选→confirmed 流转规则（candidate importance=0.3 → 用户确认或重复 N=3 次升 confirmed）
- **新增**：用户显式说"记一下我喜欢..."时直接 confirmed (importance=0.8)，跳过候选阶段
- **新增**：90 天未引用 + importance < 0.5 自动 archive
- **修改**：`backend/app/memory/long_term/store.py` 从空实现改为查询 `memory_records` 表
- **修改**：`backend/app/context/selectors/memory.py` 注入 `memory_long_term` ContextBlock

## Capabilities

### New Capabilities

- `long-term-memory-policy`: 定义用户偏好/习惯/事实等长期记忆的抽取、流转、注入行为契约（5 类记忆、candidate→confirmed 流转、显式 vs 隐式、archive 规则、与 short-term-memory-policy 的边界）

### Modified Capabilities

- `context-engineering`: 补充"长期记忆 block"作为可压缩工作记忆 block，明确优先级低于 `conversation_summary` 与最近窗口

## Impact

**新增文件**：
- `backend/app/memory/extractor.py` — LLM 抽取封装
- `backend/app/memory/prompts/observations.md` — 抽取 prompt 模板
- `backend/app/models/memory_record.py` — MemoryRecord 模型
- `backend/alembic/versions/<ts>_add_memory_records.py` — 迁移
- `backend/tests/memory/test_extractor.py` — extractor 单测
- `backend/tests/memory/test_long_term_flow.py` — candidate→confirmed 流转集成测试

**修改文件**：
- `backend/app/core/config.py` — 新增长期记忆 feature flag 与阈值配置
- `backend/config.yaml` / `backend/config.yaml.example` — 新增长期记忆配置项
- `backend/app/api/admin_config.py` — 暴露 `enable_long_term_memory`
- `backend/app/memory/service.py` — 加 `extract_observations()`、`confirm_observation()`、`record_explicit()`、`archive_stale()` 等方法
- `backend/app/memory/long_term/store.py` — 从空实现改为查询 `memory_records` 表
- `backend/app/agent/runtime/nodes.py` — Response 节点末尾挂异步长期记忆任务
- `backend/app/context/selectors/memory.py` — 扩展 long_term 查询逻辑
- `backend/app/observability/metrics.py` — 增加长期记忆 metrics

**Schema 迁移**：新增 `memory_records` 表。

**外部依赖**：无新增。

**生产成本**：受 feature flag 控制；第一版低频触发，成本上限通过 trace 与 metrics 观察后确定。

**回滚**：关闭 feature flag `ai.enable_long_term_memory`；`memory_records` 表可保留不参与查询。

**关联文档**：
- [farm-manager-design-spec/01_正式设计/04_Memory工程 § 4 / § 14](../../../farm-manager-design-spec/01_正式设计/04_Memory工程.md)
- [docs/superpowers/specs/2026-06-19-knowledge-and-memory-architecture-design.md](../../../docs/superpowers/specs/2026-06-19-knowledge-and-memory-architecture-design.md)
