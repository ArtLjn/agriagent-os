## Why

qwen3.6-flash 等弱模型在面对 10 个 Tool 时 tool selection 准确率不足（约 75%），表现为直接文本回复而非调用 Tool（幻觉数据）或假装已执行写操作。根因是 Context Distraction——10 个 Tool 的重叠 description 导致模型混淆。Spike 验证：将候选 Tool 从 10 个缩减到 1-3 个，写操作用 regex 确定性匹配（100% 召回），查询操作用关键词匹配（~95% 召回），总召回率 100%。

## What Changes

- 新增 `tool_selector.py`：两层预筛模块
  - **Layer 1 — Regex 模式匹配**：5 个写操作 Tool 各维护一组 regex pattern，deterministic 命中
  - **Layer 2 — 关键词匹配**：5 个查询 Tool 用策划触发词表匹配，从 system prompt【可用工具】映射表派生
  - 无命中时 fallback 全量注入
- 修改 `graph.py` 的 `_llm_node`：`bind_tools(tools)` → `bind_tools(select_tools(user_msg, tools))`
- 触发词表来自 `base.j2` 的【可用工具】映射表，保持单一数据源

## Capabilities

### New Capabilities
- `tool-pre-filter`: Tool 两层预筛选机制——写操作 regex 确定性匹配 + 查询操作关键词匹配，在 `bind_tools()` 前将候选 Tool 缩减到 1-3 个

### Modified Capabilities
- `llm-tool-calling`: `_llm_node` 的 `bind_tools()` 从全量注入改为注入预筛选后的 Tool 子集

## Impact

- **代码变更**: 新增 `agent/tool_selector.py`，修改 `agent/graph.py`（_llm_node 约 3 行改动）
- **无配置变更**: 触发词表内嵌在 `tool_selector.py` 中，从 `base.j2` 映射表手动同步
- **无破坏性变更**: 预筛无命中时 fallback 到全量注入，不劣于现状
- **Spike 验证**: 34 个测试用例 100% 通过，写操作 24/24 100%，单次匹配 0.005ms
