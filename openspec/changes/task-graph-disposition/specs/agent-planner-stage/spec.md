## MODIFIED Requirements

### Requirement: validate_plan_ir 与 compile_plan_ir 的归属

`explicit-planner-stage` 上线后,根据 A/B 数据决策 `task_graph/` 的去向。决策结果必须落盘到 `docs/specs/<date>-task-graph-disposition-decision.md`。无论决策是吸收还是删除,`validate_plan_ir` 与 `compile_plan_ir` 必须保留并被 planner.draft 节点调用。

#### Scenario: A/B 成功率 ≥ 80% 走删除路径

- **WHEN** `explicit-planner-stage` A/B 实验完成,LLM planner 成功率 ≥ 80%
- **THEN** 删除 `backend/app/agent/task_graph/` 目录,把 `validate_plan_ir` + `compile_plan_ir` 迁移到 `app.agent.runtime.planner.validation` + `compiler`,更新所有 import 来源

#### Scenario: A/B 成功率 < 80% 走吸收路径

- **WHEN** `explicit-planner-stage` A/B 实验完成,LLM planner 成功率 < 80%
- **THEN** 把 `task_graph.slot_extractor` 接入 `planner.draft` 节点,辅助 LLM 抽取 entity;保留 task_graph 目录但标注"仅 slot_extractor 在用"

#### Scenario: 决策必须落盘

- **WHEN** 决策日到达(A/B 启动后 30 天内)
- **THEN** 必须有 `docs/specs/<date>-task-graph-disposition-decision.md`,含 A/B 数据、决策依据、反对意见(若有)
