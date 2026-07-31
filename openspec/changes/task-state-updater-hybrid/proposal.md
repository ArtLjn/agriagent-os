## Why

缺陷 #3: `task_state_updater` 当前纯规则版(`fix-task-state-context-gating` 引入),只能识别"面积/季节/种植单元名称"三类正则匹配,实际承接场景表达多样("两万平米"代替"20 亩"、"原来叫阳光棚"重命名、"算了不种了"取消)。spike `task_state_db_injection` 显示规则版仅覆盖约 60% 真实表达,其余落 `no_task_state_signal` 兜底。需要把 updater 升级为 hybrid(规则优先,规则 miss 时调 LLM)。

## What Changes

- 在 `task_state_updater.py` 中加 LLM 路径:规则版抽不到 entity 时,调 LLM 用 `LLMTaskStateUpdate` schema 输出
- LLM 路径产出:`{matched_missing_fields: [...], extracted_entities: {...}, reasoning: "..."}`
- 加熔断机制(复用 `_is_summary_circuit_open` 模式),LLM 失败时降级到规则版结果
- 接入 trace,记录每次更新走的是 rule / llm / fallback 路径

## Capabilities

### New Capabilities

无(扩展 `task-state-auto-update` capability)。

### Modified Capabilities

- `task-state-auto-update`: 升级为 hybrid(规则优先 + LLM 兜底 + 熔断),覆盖多样化表达

## Impact

- 受影响代码:
  - `backend/app/agent/runtime/task_state_updater.py`(加 LLM 路径)
  - 新增 prompt `memory.task_state_extract`(在 `app/memory/prompts/` 加 jinja 模板)
  - `backend/app/agent/runtime/llm_support.py`(复用熔断机制)
- 受影响测试:`backend/tests/agent/runtime/test_task_state_updater.py` 加 LLM mock case
- LLM 成本:每个承接 turn +1 次 LLM 调用(仅当规则 miss 时)
- 依赖:`explicit-planner-stage` 上线后(共享 LLM 熔断与 trace infrastructure)
- 回滚:禁用 LLM 路径,保留规则版
