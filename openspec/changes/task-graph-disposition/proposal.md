## Why

`backend/app/agent/task_graph/` 共 1580 行代码(capability_catalog / compiler / plan_ir / runtime 等),但当前主链路只用了其中的 `validate_plan_ir` + `compile_plan_ir` 用于静态校验,其余未接入(缺陷 #2)。死代码候选。本变更不直接做吸收或删除,而是**根据 `explicit-planner-stage` 上线后的 A/B 数据做决策**,产出决策记录与执行 PR。

## What Changes

- **决策点**:根据 `explicit-planner-stage` 上线 2 周后的 A/B 数据,决定 task_graph 是吸收还是删除
- **吸收路径**:把 task_graph 的 slot_extractor / FactSource / static_validator 之一接入 planner.draft 节点
- **删除路径**:删除 task_graph 目录,仅保留 `validate_plan_ir` + `compile_plan_ir`(迁移到 `app/agent/runtime/planner/`)
- 产出决策记录到 `docs/specs/2026-07-31-task-graph-disposition-decision.md`

## Capabilities

### New Capabilities

无(本变更是决策与执行,不引入新能力)。

### Modified Capabilities

依赖决策结果:
- **若吸收**:新增 `task-graph-fact-source` 等 capability(决策后追加 spec)
- **若删除**:在 `agent-planner-stage` 中 MODIFIED 把 `validate_plan_ir` 来源标注为 `app.agent.runtime.planner.validation`

## Impact

- 受影响代码:
  - 吸收:`backend/app/agent/runtime/planner/llm_planner.py` 接入 task_graph 子模块
  - 删除:`backend/app/agent/task_graph/` 整个目录(保留 validation+compiler)
- 受影响测试:相应清理或迁移
- 决策依据:`explicit-planner-stage` 的 A/B 实验数据 + planner_probe 5 case 成功率
- 回滚:决策前不动代码,删除路径下保留 git history 可恢复
