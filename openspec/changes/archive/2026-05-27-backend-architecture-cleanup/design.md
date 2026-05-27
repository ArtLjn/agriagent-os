## Context

后端 `app/core/` 目录有 19 个模块（1,526 行），承担了三类不同职责：

1. **真正的基础设施**：config、database、logger、date_context、json_repair
2. **Agent 专属逻辑**：llm、guardrails、prompt_registry、prompt_renderer、term_whitelist
3. **可观测性/运维**：trace_collector、trace_dao、trace_context、trace_cleaner、circuit_breaker、limiter、pending_actions、skill_cache

其中 `term_whitelist.py`（61 行）已确认零引用，属于死代码。`prompt_registry.py` 中的 `_DEFAULT_PROMPTS`（约 50 行硬编码字符串）与 `prompts/*.j2` 文件内容重复且已不同步 — 文件版有完整的【能力范围】、【时间信息】段，硬编码版缺失。

## Goals / Non-Goals

**Goals:**
- 删除已确认的死代码（term_whitelist.py）
- 消除 prompt 双数据源，统一为文件单一数据源
- 将 core/ 拆分为 core/（基础设施）、agent/（Agent 专属）、infra/（可观测性），使职责清晰
- 所有改动不影响外部 API

**Non-Goals:**
- 不做 DDD 重构（项目规模不需要）
- 不重命名包名或调整分层架构（api/services/models/schemas 保持不变）
- 不改变任何业务逻辑
- 不做 storage-redesign 的内容（那是另一个 change）

## Decisions

### D1: 删除 term_whitelist.py

**选择：** 直接删除，无任何代码引用。

**理由：** grep 确认 `is_whitelisted` 和 `_AGRICULTURAL_TERMS` 在整个项目中零引用。

### D2: 删除 _DEFAULT_PROMPTS，移除 get_fallback

**选择：** 删除 `prompt_registry.py` 中的 `_DEFAULT_PROMPTS` 字典和 `get_fallback()` 方法。`prompt_renderer.py` 中模板未注册时直接抛 KeyError 而非返回过时内容。

**备选方案：**
- A) 定期同步两份 → 人为操作，必然再次不同步
- B) 启动时从文件加载写入 _DEFAULT_PROMPTS → 多此一举，文件本身就是持久化的

**理由：** 过时的 fallback prompt 比报错更危险 — 用户以为系统正常运行，实际 prompt 行为已偏离。运行时加载失败应该暴露问题而非掩盖。

### D3: core/ 拆分为三个包

**选择：**

```
app/
├── core/           ← 瘦身到 5 个基础设施模块
│   ├── config.py
│   ├── database.py
│   ├── security.py    ← storage-redesign 新增
│   ├── logger.py
│   ├── date_context.py
│   └── json_repair.py
│
├── agent/          ← 从 agents/ + core/ 合并，Agent 领域模块
│   ├── graph.py
│   ├── advisor.py
│   ├── report.py
│   ├── state.py
│   ├── llm.py
│   ├── guardrails.py
│   ├── prompt_registry.py
│   ├── prompt_renderer.py
│   └── skills/
│
├── infra/          ← 可观测性 + 运维模块
│   ├── trace_collector.py
│   ├── trace_dao.py
│   ├── trace_context.py
│   ├── trace_cleaner.py
│   ├── circuit_breaker.py
│   ├── limiter.py
│   ├── pending_actions.py
│   └── skill_cache.py
│
├── api/            ← 不变
├── models/         ← 不变
├── schemas/        ← 不变
└── services/       ← 不变
```

**移动映射：**

| 原路径 | 新路径 | 理由 |
|--------|--------|------|
| `agents/` 4 个文件 | `agent/` | 重命名为 agent（去掉 s），与包内其他模块统一 |
| `core/llm.py` | `agent/llm.py` | 只被 agent 层使用 |
| `core/guardrails.py` | `agent/guardrails.py` | 只在 agent 输入输出链路中使用 |
| `core/prompt_registry.py` | `agent/prompt_registry.py` | 只为 agent 提供模板 |
| `core/prompt_renderer.py` | `agent/prompt_renderer.py` | 只为 agent 渲染 prompt |
| `core/trace_*.py` (4个) | `infra/` | 可观测性横切关注点 |
| `core/circuit_breaker.py` | `infra/` | 被 llm.py 使用的容错基础设施 |
| `core/limiter.py` | `infra/` | 请求限流 |
| `core/pending_actions.py` | `infra/` | 写操作确认机制 |
| `core/skill_cache.py` | `infra/` | Skill 缓存 |

**不动：**
- `core/config.py` — 全局配置，所有模块都依赖
- `core/database.py` — 数据库连接，所有模块都依赖
- `core/logger.py` — 日志，所有模块都依赖
- `core/date_context.py` — 请求上下文，api 和 service 都使用
- `core/json_repair.py` — 通用工具，多处使用
- `core/seed.py` — 启动时迁移，main.py 直接调用
- `core/term_whitelist.py` — 删除（D1）

**备选方案：**
- A) 维持 core/ 不拆 → 当前 19 个模块，新增 auth 后更膨胀
- B) 按领域分组（farm/、agent/、auth/）→ DDD 过重，项目只有 2-3 个领域

**理由：** 三分法（基础设施 / Agent / 运维）简单直观，每个包 5-8 个模块可管理，符合当前项目规模。

## Risks / Trade-offs

- **[Import 路径变更范围大]** 约 30+ 处 import 需要更新，遗漏会导致运行时 ImportError。→ 移动后立即运行全量测试 + ruff 检查
- **[与 storage-redesign 交叉]** 两个 change 可能修改同一批文件。→ 先完成此清理，再做 storage-redesign，避免合并冲突
- **[agents/ → agent/ 重命名] 可能与 langchain 的 agents 模块混淆。→ 内部包名，不影响外部；agent 更符合单数命名惯例
- **[记忆负担]** 新的包结构需要团队适应。→ 更新 CLAUDE.md 项目地图
