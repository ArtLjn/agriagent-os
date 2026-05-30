## Why

当前 Agent 每轮请求全量注入 farm_context_summary（~300 tokens）到 system prompt，且第二轮工具调用后回退为全量 11 个工具绑定（~4500 tokens），对话历史无压缩。实测 qwen3.6-35b-a3b 模型下，首轮 ~2400 tokens、第二轮起 ~6200 tokens，10 轮对话累计 ~30000 tokens。按 DashScope 计费，每日 100 轮对话约消耗 150 万 tokens，成本偏高且响应延迟随对话轮次增长。

Spike 验证结果（qwen3.6-35b-a3b 真实 API 调用）：
- **假设 1 Context as Tool**: 召回 100%（5/5），精确 83%（1 次闲聊误调用），**可行**
- **假设 2 工具筛选一致性**: 第二轮仅保留首轮工具，token 节省 28%，回答质量正常，**可行**
- **假设 3 Sliding Window 压缩**: 10 轮对话压缩后 token 节省 41%，关键信息（200 元化肥）仍正确引用，**可行**

## What Changes

- **Context as Tool**：将 `farm_context_summary` 从 system prompt 移除，包装为 `get_farm_status` 只读 Skill，Agent 按需调用获取农场状态。system prompt 前缀稳定化（角色+规则+时间不变），提升 KV-cache 命中率。
- **工具筛选一致性**：第二轮工具调用后不再回退全量（`has_tool_results → selected_tools = tools`），改为保留首轮筛选结果 + 工具链关联工具（TOOL_CHAIN_MAP），最多 5 个。
- **Sliding Window 对话压缩**：`micro_compact` 升级为 sliding window，最近 5 轮完整保留，窗口外旧消息用规则模板压缩为意图摘要（不做 LLM 摘要，零额外 token 开销）。

## Capabilities

### New Capabilities
- `get_farm_status`：只读 Skill，封装 farm_context_service.build_summary()，TTL 缓存 5min，Agent 按需调用

### Modified Capabilities
- `tool-selection`：新增 TOOL_CHAIN_MAP 工具链关联映射，第二轮使用 `首轮结果 ∪ 关联工具` 替代全量回退
- `history-compression`：micro_compact 升级为 sliding window + 规则压缩

## Spike 数据

### 假设 1: Context as Tool
| 场景 | 输入 | 调用 get_farm_status | tokens |
|------|------|---------------------|--------|
| 需要 | 我的辣椒长得怎么样了 | ✅ | 572 |
| 需要 | 最近有什么农事要做的吗 | ✅ | 908 |
| 需要 | 帮我看看账还清了没 | ✅ | 667 |
| 需要 | 这个月花了多少钱 | ✅ | 680 |
| 需要 | 有什么建议给我吗 | ✅ | 712 |
| 闲聊 | 你好 | ⚠️ 误调用 | - |
| 闲聊 | 西瓜什么时候种最好 | ✅ 不调用 | - |
| 闲聊 | 番茄怎么防治蚜虫 | ✅ 不调用 | - |
| 闲聊 | 什么是轮作 | ✅ 不调用 | - |

结论：**召回 100%，精确 83%**。闲聊误调用可通过调整 description 降低。

### 假设 2: 工具筛选一致性
| 方案 | tokens | 回答质量 |
|------|--------|---------|
| 全量工具 (baseline) | 756 | 正常 |
| 仅首轮工具 | 543 | 正常 |

结论：**节省 28%，质量无损**。

### 假设 3: Sliding Window
| 方案 | tokens | 提到 200 元化肥 |
|------|--------|----------------|
| 全量 10 轮 | 1447 | ✅ |
| 压缩 (4 轮+摘要) | 860 | ✅ |

结论：**节省 41%，关键信息保留**。

## Impact

- `app/agent/graph.py` — 移除 farm_context_service 调用，第二轮工具绑定逻辑改为 TOOL_CHAIN_MAP，micro_compact 升级为 sliding window
- `app/agent/skills/` — 新增 `get-farm-status` Skill 目录
- `app/services/farm_context_service.py` — 不变，被新 Skill 复用
- `prompts/base.j2` — 移除 `{{ farm_context_summary }}` 注入段
- `app/agent/tool_selector.py` — 新增 TOOL_CHAIN_MAP 和 chain 扩展逻辑

## Non-goals

- 不做 LLM 摘要压缩（额外 token 开销，规则压缩已够用）
- 不做 RAG-MCP 语义检索（11 个工具太少，regex+keyword 已足够）
- 不做 Progressive Disclosure（需要 Agent 状态机，当前阶段过重）
- 不做 Scratchpad + Memory Store（跨会话场景目前不存在）

## 预估收益

| 场景 | 改前 tokens | 改后 tokens | 节省 |
|------|------------|------------|------|
| 首轮请求 | ~2400 | ~1200 | 50% |
| 第二轮(有工具) | ~6200 | ~2700 | 56% |
| 5 轮对话累计 | ~15000 | ~6000 | 60% |
| 10 轮对话累计 | ~30000 | ~10000 | 67% |
