## Context

当前 `_llm_node` 每次 LLM 调用都将全部 10 个 Tool 通过 `bind_tools()` 注入。弱模型（qwen3.6-flash）面对 10 个候选时出现 Context Distraction，tool selection 准确率仅 ~75%。

已实施优化（description 意图场景描述 + system prompt directive 映射表）将命中率提升到 ~75%，但不够稳定。需要从根源减少模型需要选择的 Tool 数量。

Spike 验证结论：两层规则匹配（regex + keyword）在 34 个测试用例上达到 100% 召回率，单次耗时 0.005ms，零额外 API 调用。

## Goals / Non-Goals

**Goals:**
- 写操作（记账/还账/建茬口/记农事/更新阶段）tool selection 准确率 → 100%
- 查询操作（天气/余额/趋势/日志/茬口详情）准确率 → ~95%
- 零额外 API 调用、零延迟增加、安全 fallback

**Non-Goals:**
- 不做 embedding/语义匹配（当前 10 个 Tool 语义边界清晰，不需要）
- 不改 Tool description 或 system prompt 内容
- 不改 LangGraph 图结构

## Decisions

### D1: 两层架构 — 写操作 regex + 查询操作 keyword

**选择：** 写操作用 regex pattern 确定性匹配，查询操作用策划触发词表匹配

**备选方案：**
- A) 统一用关键词匹配：写操作 95% 但非 100%，"卖西瓜收入5w"等口语可能漏
- B) 统一用 regex：查询操作 regex 难写（"余额"有多少种说法？）
- C) 两层分离：写操作 regex（deterministic）+ 查询操作 keyword（模糊匹配）

**理由：** 写操作（记账/还账）准确性要求极高——漏一笔就是对账误差。Regex 对"买了X元""还了Y钱"这类模式是确定性匹配，不依赖模型理解力。查询操作漏了最多追问一次，95% 足够。

### D2: 触发词数据源 — 从 base.j2 映射表手动同步

**选择：** `tool_selector.py` 中硬编码触发词表，与 `base.j2` 的【可用工具】映射表保持同步

**备选方案：**
- A) 运行时从 description 自动提取：Spike v1 证明 2-gram 噪声太多，召回率 86.7%
- B) 运行时解析 base.j2 提取触发词：耦合模板格式，脆弱
- C) 硬编码 + 与 base.j2 手动同步：精确、可测、可审

**理由：** Spike v1 用自动提取只有 86.7%，Spike v2 用策划词表直接到 95%。触发词表总共 ~70 个词，维护成本极低。与 base.j2 是同一份信息的两个视图（prompt 给 LLM 看，trigger table 给匹配器看）。

### D3: 模块位置 — `agent/tool_selector.py`

独立模块，不嵌入 `graph.py`（图编排）或 `skills/__init__.py`（Tool 注册）。

### D4: Fallback 策略 — 无命中返回全量

预筛零命中时返回全部 10 个 Tool。不比现状差，模型从 10 个中选。

### D5: 写操作 Regex 模式设计

```python
WRITE_PATTERNS = {
    "create_cost_record": [
        r"(买了|卖了|花了|收入|支出|赊账|记账|记一笔|付了|收了)",
        r"\d+\s*(元|块|万|w|W|千|百)",
    ],
    "settle_debt": [
        r"(还[了钱账给]|清账|结清|欠款|还款)",
        r"(账[结清]|结了.*账|欠.*结)",
    ],
    "create_crop_cycle": [
        r"(创建|建|开)\s*.*茬口",
        r"(种植|种[了上下]?)\s*(西瓜|番茄|辣椒|豆角|黄瓜|玉米)",
        r"(春茬|秋茬|夏茬|冬茬)",
    ],
    "log_farm_activity": [
        r"(浇[了水]|施[了肥]|打[了药]|除[了草]|翻[了地]|播[了种])",
        r"(记录|记下)\s*(农事|操作|浇水|施肥)",
    ],
    "update_crop_stage": [
        r"(进[了入]?).*(期|阶段)",
        r"(到[了]?|进入)\s*(苗期|开花期|结果期|采收期|伸蔓期|定植期)",
    ],
}
```

核心原则：**宁可多匹配（候选中多一个写操作 Tool），不可漏匹配**。写操作有 pending_actions 确认机制兜底，误触发不会造成数据错误。

## Risks / Trade-offs

| 风险 | 影响 | 缓解 |
|------|------|------|
| 新增写操作 Tool 时需同步更新 regex | 遗漏导致新 Tool 不被预筛 | CI 测试覆盖；fallback 兜底 |
| 触发词表与 base.j2 不同步 | prompt 映射和预筛结果不一致 | 代码评审 checklist |
| Regex 误触发写操作 Tool | 候选多了一个无关 Tool | pending_actions 确认机制；模型可忽略多余 Tool |
| 口语变体未覆盖 | fallback 全量，不劣于现状 | 持续补充 pattern |
