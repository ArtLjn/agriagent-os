## Why

农户在多轮对话中频繁遇到 Agent "失忆"：超过 5-6 轮就忘记前面提到的金额、地块、上下文。根因有二：

1. 当前会话压缩机制全部基于**字符串截断**，没有真正的 LLM 语义摘要；`short-term-memory-policy` 与 `conversation-management` spec 早已声明"会话摘要"要求，但代码侧 `MemoryService.set_session_summary()` 是死接口（无任何调用方），`conversations.summary` 字段已存在却从未被写入。
2. 用户偏好与习惯（"我喜欢下午浇水"、"记账用万元"）每次对话都要重说，因为 `memory/long_term/` 仍是空实现（[store.py](../../../backend/app/memory/long_term/store.py) 返回空 LongTermMemoryContext）。

本提案落地 spec 已有要求，闭合"多轮失忆"和"用户喜好无沉淀"两个最痛的问题，并复用同一异步触发钩子，使一次 LLM 调用同时输出 summary + observations，节省成本。

参考：[docs/superpowers/specs/2026-06-19-knowledge-and-memory-architecture-design.md](../../../docs/superpowers/specs/2026-06-19-knowledge-and-memory-architecture-design.md) § 3-4。

## What Changes

### 会话摘要部分（同前）

- **新增**：异步触发阈值（messages ≥ 12）的会话摘要生成任务，写入 `conversations.summary` + `summary_updated_at`
- **新增**：摘要 prompt 模板（强制保留金额 / 日期 / 实体 / pending action 等结构化字段）
- **修改**：ConversationSelector 在查询时拼接 `conversations.summary` 到上下文开头
- **修改**：MemoryService 暴露 `maybe_summarize()` 入口，由 Runtime Response 节点异步调用
- **修改**：摘要失败时降级到现有字符串截断逻辑（保持可用性）

### 长期记忆抽取部分（与摘要共触发）

- **新增**：`memory_records` 表（5 类记忆：preference / habit / alias / event / fact，含 status / importance / confidence / source / superseded_by_id 字段）+ Alembic 迁移
- **新增**：`memory_service.extract_observations(...)` 异步入口，与 `maybe_summarize` 共用 Response 后台钩子，**一次 LLM 调用同时输出 summary + observations**
- **新增**：候选→confirmed 流转规则（candidate importance=0.3 → 用户确认或重复 N=3 次升 confirmed=0.8）
- **新增**：用户显式说"记一下我喜欢..."时直接 confirmed (importance=0.8)，跳过候选阶段
- **新增**：90 天未引用 + importance < 0.5 自动 archive
- **修改**：[context/selectors/memory.py](../../../backend/app/context/selectors/memory.py) 扩展查询 `WHERE status IN ('confirmed','candidate') AND importance >= 0.3 ORDER BY importance DESC, last_referenced_at DESC LIMIT 5`

### 通用

- **复用**：现有 LLM client（qwen3.6-35b-a3b）、熔断器
- **不引入**：Redis、向量库、MemGPT / Letta、新依赖

## Capabilities

### New Capabilities

- `long-term-memory-policy`: 定义用户偏好/习惯/事实等长期记忆的抽取、流转、注入行为契约（5 类记忆、candidate→confirmed 流转、显式 vs 隐式、archive 规则、与 short-term-memory-policy 的边界）

### Modified Capabilities

- `short-term-memory-policy`: 落地"会话摘要"requirement —— 当前 `set_session_summary()` 死接口接通生产，提供基于阈值的自动摘要生成、持久化、降级路径
- `conversation-management`: 落地"历史超过窗口时摘要替代"requirement —— ConversationSelector 在查询最近窗口时同时把已生成的 `conversations.summary` 注入到 ContextBundle
- `context-engineering`: 补充"会话摘要 block"与"长期记忆 block"作为可压缩工作记忆 block，明确优先级介于 pending_action 与最近窗口之间

## Impact

**新增文件**：
- `backend/app/memory/summarizer.py` — LLM 摘要封装（~50 行）
- `backend/app/memory/extractor.py` — LLM 抽取封装（~60 行，与 summarizer 同模式）
- `backend/app/memory/prompts/summary.md` — 摘要 prompt 模板
- `backend/app/memory/prompts/observations.md` — 抽取 prompt 模板
- `backend/app/models/memory_record.py` — MemoryRecord 模型
- `backend/alembic/versions/<ts>_add_memory_records.py` — 迁移
- `backend/tests/memory/test_summarizer.py` — 单测（~80 行）
- `backend/tests/memory/test_extractor.py` — 单测（~100 行）
- `backend/tests/memory/test_long_term_flow.py` — candidate→confirmed 流转集成测试（~80 行）

**修改文件**：
- `backend/app/memory/service.py` — 加 `maybe_summarize()` + `extract_observations()` + `confirm_observation()` + `archive_stale()` 方法（共 ~80 行）
- `backend/app/memory/long_term/store.py` — 从空实现改为查询 `memory_records` 表
- `backend/app/memory/short_term/store.py` — `set_session_summary` 接通持久化层
- `backend/app/agent/runtime/nodes.py` — Response 节点末尾挂异步任务（共触发 summary + observations，~10 行）
- `backend/app/context/selectors/memory.py` — 扩展 long_term 查询逻辑（~20 行）

**Schema 迁移**：新建 `memory_records` 表（1 个迁移）。`conversations.summary` 字段已存在，零额外迁移。

**外部依赖**：无新增。

**生产成本**：单户月增 < ¥3（摘要 + 抽取合计，每 12 条消息触发 1 次共触发，qwen3.6 单次 ~¥0.008）。

**回滚**：feature flag `ai.enable_session_summary` + `ai.enable_long_term_memory` 双开关。

**关联文档**：
- [farm-manager-design-spec/01_正式设计/03_Context工程 § 6](../../../farm-manager-design-spec/01_正式设计/03_Context工程.md)
- [farm-manager-design-spec/01_正式设计/04_Memory工程 § 7.2 / § 12](../../../farm-manager-design-spec/01_正式设计/04_Memory工程.md)
- [docs/superpowers/specs/2026-06-19-knowledge-and-memory-architecture-design.md](../../../docs/superpowers/specs/2026-06-19-knowledge-and-memory-architecture-design.md)
