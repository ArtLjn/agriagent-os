# 03 — Context 工程

> 状态：草稿 | 维护：BlockShip | 关联：[01_Agent平台架构](./01_Agent平台架构.md)、[04_Memory工程](./04_Memory工程.md)、[05_Prompt工程](./05_Prompt工程.md)

---

## 1. 为什么需要 Context 工程

农户的对话历史长，业务数据多（茬口/账单/工人/天气），全量塞进 system prompt 会：
- Token 爆炸（成本飙升 + window 溢出）
- 注意力分散（模型找不到关键信息）
- 延迟增加（首 token > 3s）

Context 工程的目标：**给 LLM 喂刚刚好的上下文，不多不少**。

## 2. 核心组件

```
ContextBuildRequest (farm_id, intent, tool_names, session_id)
  ↓
ContextPolicy（决策：用哪些 selector、token 上限）
  ↓
ContextBuilder（编排各 selector）
  ↓
Selectors（按业务域拉数据）
  ├─ farm_selector
  ├─ cycle_selector
  ├─ settings_selector
  ├─ ledger_selector
  ├─ weather_selector
  ├─ conversation_selector
  ├─ memory_selector
  └─ retrieval_selector（预留，当前空实现）
  ↓
TokenBudget（裁剪 + 压缩）
  ↓
ContextBundle（最终产物）
  ├─ system_prompt_facts
  ├─ runtime_context
  ├─ memory_view
  └─ preload_knowledge
  ↓
Runtime（消费 ContextBundle）
```

## 3. ContextBundle 结构

```python
class ContextBundle(BaseModel):
    """Runtime 消费的上下文包，不可变。"""
    farm: FarmFacts                    # 当前农场基础信息
    cycle: CycleFacts | None           # 当前茬口（如有）
    settings: UserSettingsFacts        # 用户偏好（语言、人设、单位）
    ledger: LedgerSnapshot | None      # 最近账务快照
    weather: WeatherSnapshot | None    # 当前天气 + 预报
    conversation: ConversationSummary  # 最近会话摘要
    memory: MemoryView                 # 短时记忆 + 长时记忆摘要
    preload: PreloadKnowledge | None   # 高频知识（作物物候期、记账分类）
    metadata: ContextMetadata          # token、budget、selector 命中
```

**约束**：
- ContextBundle 是只读的，Runtime 不能修改
- Runtime 不感知 selector 的存在
- Memory View 由 Memory Service 提供，不在 Context 层实现

## 4. Selector 列表

| Selector | 数据来源 | 输出 | 触发条件 |
| --- | --- | --- | --- |
| `farm_selector` | Farm 表 | 农场名、地区、规模 | 总是 |
| `cycle_selector` | CropCycle 表 + CropTemplate | 当前茬口（作物、阶段、起止） | intent 涉及农事 |
| `settings_selector` | UserSettings 表 | 语言、人设、货币、时区 | 总是 |
| `ledger_selector` | Cost 表 | 当月支出汇总、最近 5 笔 | intent 涉及记账 |
| `weather_selector` | Weather cache | 当前 + 未来 3 天 | intent 涉及浇水/打药/采收 |
| `conversation_selector` | ConversationMessage 表 | 最近 10 轮对话摘要 | 总是 |
| `memory_selector` | MemoryService | 短时记忆 + 长时记忆 | 总是 |
| `retrieval_selector` | （预留） | — | 未来 RAG 接入 |

## 5. Token Budget（预算与裁剪）

```python
class TokenBudget:
    total: int = 8000           # 总预算（不含 system prompt 骨架）
    reserve_for_response: int = 2000
    usable_for_context: int = 6000

    def allocate(self, bundle: ContextBundle) -> ContextBundle:
        # 1. 计算各 block 的 token
        # 2. 按优先级裁剪：farm > settings > cycle > conversation > ledger > weather > memory > preload
        # 3. 低优先级超预算时摘要化或丢弃
        # 4. 返回裁剪后的 bundle
```

**优先级理由**：用户基础信息（farm/settings）必须有，业务上下文（cycle）次之，历史对话再次，参考数据（weather/preload）最后。

## 6. 压缩策略

### 6.1 实际实现（5 道关卡串行过滤）

当前所有压缩都是**截断 / 丢弃**，没有真正的 LLM 语义摘要。多轮失忆的直接根因。

| 关卡 | 位置 | 机制 | 关键阈值 |
| --- | --- | --- | --- |
| 1. ContextBuilder 预算裁剪 | [context/budget.py](../../../backend/app/context/budget.py) | 按 `priority` 排序，超预算的 `compressible` 块被截断、其余 drop | 默认 `max_tokens=1200`；policy 模式 512-900 |
| 2. 文本压缩器 | [context/compressors/text.py](../../../backend/app/context/compressors/text.py) | `text[:max_chars-1] + "…"`，硬截断 | 按字符 |
| 3. ConversationSelector | [context/selectors/conversation.py](../../../backend/app/context/selectors/conversation.py) | 从 DB 取最近 N 条 message | `limit=6` |
| 4. sliding_window_compact | [agent/runtime/messages.py](../../../backend/app/agent/runtime/messages.py) | 保留最近 N 轮，旧 ToolMessage 替换为 `[已执行 xxx]` | `keep_rounds=5` |
| 5. FinalPromptBudget | [agent/runtime/final_prompt_budget.py](../../../backend/app/agent/runtime/final_prompt_budget.py) | 超 800 token 的 ToolMessage 截断；超 6000 token 触发 `summarize_old_messages` | `max_tokens=6000`、`recent_messages=6` |

**`summarize_old_messages` 实现注意**：取最后 12 条 × 每条前 80 字符拼接，**不是 LLM 摘要**，本质仍是截断。

### 6.2 多轮失忆根因（按影响排序）

| # | 根因 | 影响 |
| --- | --- | --- |
| 1 | ContextBuilder 默认预算仅 1200 token | 一有天气/账本就把对话挤掉 |
| 2 | ConversationSelector 只取 6 条 | 第 7 条起整条丢 |
| 3 | `set_session_summary()` 是死接口（[memory/short_term/store.py](../../../backend/app/memory/short_term/store.py)），从未被写入 | 设计了摘要但没接生产 |
| 4 | 压缩器只有截断 | 关键信息可能被切掉（金额、日期、ID 落在截断点之后） |
| 5 | sliding_window 把旧 ToolMessage 替换成 placeholder | "上次查到 X 数据"→ 无法回忆 |
| 6 | Long-term / Retrieval 是空骨架 | 跨 session 完全无记忆 |
| 7 | Short-term 是 in-memory deque | 进程重启 / 多 worker 全丢 |

### 6.3 主流方案对比

| 方案 | 核心机制 | 复杂度 | 适配度 |
| --- | --- | --- | --- |
| **LangGraph** | trim / filter / summarize + checkpointer 持久化 | 低 | ⭐⭐⭐⭐⭐（推荐借鉴） |
| **Claude Code** | 单一阈值 → 全量 LLM 摘要 → 替换历史 + 重读关键文件 | 极低 | ⭐⭐⭐⭐（state protect 思路值得借鉴） |
| **Letta / MemGPT** | OS 隐喻（core/recall/archival 三级）+ LLM 自治调工具管理 | 高 | ⭐（2C4G 扛不住，过度设计） |

参考链接：
- LangChain Context Engineering：https://www.langchain.com/blog/context-engineering-for-agents
- LangGraph Memory 文档：https://docs.langchain.com/oss/python/langgraph/add-memory
- Claude Code Compaction Deep Dive：https://decodeclaude.com/compaction-deep-dive/
- Letta Agent Memory：https://www.letta.com/blog/agent-memory/

### 6.4 推荐方案：Running Summary + State Protect

**核心思路**：LangGraph 路线 + Claude Code 的 state protect 思路，不引入 MemGPT。

```
[Response 节点] → 异步触发 → [MaybeSummarize 节点]
                                  ↓
                          持久化到 conversations.summary 字段
```

| 设计点 | 选择 | 理由 |
| --- | --- | --- |
| 触发方式 | 阈值（messages ≥ 12） | 摊薄成本，不要每轮 |
| 摘要模式 | Running summary（追加，不重写） | 已固定部分不动，只摘要新增 |
| 摘要模型 | 复用 qwen3.6-35b-a3b | 单户月成本 < ¥2，不需要单独 Haiku |
| 摘要存储 | `conversations.summary` + `summary_updated_at` | 字段已存在，零迁移 |
| State protect | 强制保留 pending_action / 最近 Skill 关键参数 / 当前茬口 | 借鉴 Claude Code "protect context" |
| 失败降级 | 复用现有熔断器，失败 fallback 到字符串截断 | 保证可用性 |

**禁止**：
- ❌ 上 MemGPT / Letta（架构污染、2C4G 扛不住）
- ❌ 上向量数据库做 retrieval（spec 已声明 2C4G 不做 RAG）
- ❌ 每轮都摘要（成本爆炸）
- ❌ 让 LLM 自治管理 memory（不可控）

### 6.5 落地路线

详见 [04_Memory工程 § 12 多轮失忆治理路线](./04_Memory工程.md#12-多轮失忆治理路线)。

- **Phase A**（1.5-2d）：接通 `set_session_summary` 自动生成 + 持久化
- **Phase B**（0.5d）：ConversationSelector 提到 12 条 + 拼 summary + ToolMessage 关键字段保留
- 验证：内测 5-10 农户跑 2 周，看 trace 里关键字段命中率

## 7. 缓存（Farm Context Cache）

```
context/cache.py
  ├─ FarmContextCache：按 farm_id 缓存 ContextBundle
  ├─ TTL：5 分钟（业务数据变化时主动失效）
  └─ 失效触发：写操作 Skill 成功后 → context_invalidation
```

**禁止**：缓存只读业务的 ContextBundle；写操作 Skill 后必须失效。

## 8. 预加载（Preload）

```
context/preload.py
  ├─ 高频知识：作物物候期表、记账分类、单位换算
  ├─ 加载时机：用户首次进入会话
  └─ 存放：Redis（未来）/ 内存 cache（当前）
```

预加载知识是「无需 LLM 推理即可决定」的数据，比如：
- 「番茄苗期多少天」→ 直接查物候期表
- 「化肥属于什么分类」→ 直接查分类表

## 9. Context Policy（策略）

```python
class ContextPolicy:
    """决定 ContextBuilder 调用哪些 selector、token 怎么分配。"""

    def build_for(self, intent: Intent, tool_names: list[str]) -> ContextBuildRequest:
        if intent == Intent.GREETING:
            return ContextBuildRequest(selectors=["farm", "settings", "conversation"])
        if intent == Intent.COST_RECORD:
            return ContextBuildRequest(selectors=["farm", "settings", "ledger", "conversation"])
        if intent == Intent.CROP_PLAN:
            return ContextBuildRequest(selectors=["farm", "cycle", "weather", "conversation"])
        # ... 其他意图
```

策略可配置，不硬编码到 Runtime。

## 10. 边界与禁止

- Runtime 不能直接调 selector，只能消费 ContextBundle
- Selector 不能调 Prompt Composer 或 LLM
- Memory View 由 Memory Service 提供，不在 Context 层实现存储
- Token Budget 计算用 anthropic 的 token counter，不自己估算
- Cache 读写必须经过 FarmContextCache 抽象，不直接操作 Redis client

## 11. 当前状态

- ✅ ContextBundle / Builder / Policy 骨架
- ✅ selectors/ 各业务 selector 落地（farm/cycle/settings/ledger/weather/conversation/memory/planting/work_order/worker/labor/cost_category/retrieval）
- ✅ budget.py token 预算（默认 1200，policy 模式 512-900）
- ✅ cache.py + invalidation.py
- 🚧 compressors/ —— **当前仅 `text.py` 截断函数**，micro/auto/manual 三层尚未实现（详见 § 6.1）
- 🚧 preload.py 物候期/分类表（部分落地）
- 🚧 retrieval_selector（预留空实现，待外部 RAG 接入）
- ✅ conversation_summary 注入已接通：`conversations.summary` 非空时由 ConversationSelector 注入 working/session block

## 12. 相关文档

- [01_Agent平台架构](./01_Agent平台架构.md)
- [04_Memory工程](./04_Memory工程.md)
- [05_Prompt工程](./05_Prompt工程.md)
- [03_接口协议/02_Agent内部接口](../03_接口协议/02_Agent内部接口.md)
