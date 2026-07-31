## Context

`task_graph/` 1580 行,设计意图是支持完整 PlanIR DAG + Capability 编排,但实际主链路从未接入。`backend/scripts/planner_probe.py` 实证 LLM 能直接输出合法 PlanIR,经 `validate_plan_ir` + `compile_plan_ir` 通过即可,不需要 task_graph 的 FactSource/slot_extractor/parallel/branch 等重型抽象。

`explicit-planner-stage` 上线后,会有 2 周 A/B 数据回答:"LLM planner 成功率是否 > 80%"。这是决策的核心输入。

## Goals / Non-Goals

**Goals**:
- 在 `explicit-planner-stage` A/B 数据可用时,产出明确决策(吸收 vs 删除)
- 决策结果落盘到 `docs/specs/`,带数据依据
- 执行决策(吸收某个子模块 或 删除整个目录)

**Non-Goals**:
- 不在 `explicit-planner-stage` 上线前做决策(没有数据基础)
- 不在决策前重写 task_graph 代码
- 不引入新的 PlanIR schema(沿用 `app.agent.task_graph.models.PlanIR`)

## Decisions

**D1: 决策门槛——LLM planner 成功率 > 80%**

rationale:
- ≥ 80% → LLM planner 稳定,task_graph 的 slot_extractor/FactSource 价值降低,因为 LLM 自己能补缺失字段。删除路径。
- < 80% → LLM planner 不可靠,需要 task_graph 的重型抽象兜底。吸收路径,把 slot_extractor 接入。

**D2: 删除路径下保留 validate_plan_ir + compile_plan_ir**

rationale: 这两个函数是无依赖的纯函数,主链路在用,有价值。迁移到 `app.agent.runtime.planner.validation` + `compiler`,与 task_graph 目录脱钩。

**D3: 吸收路径下只接 slot_extractor,不接 parallel/branch**

rationale: parallel/branch 在当前业务没有用例(crop_cycle_setup / cost_analysis 等都是线性流程)。slot_extractor 是 task_graph 唯一对 planner.draft 有实际增益的子模块(辅助 LLM 抽 entity)。

**D4: 决策记录是 first-class artifact**

rationale: 不在 PR description 里散落,落到 `docs/specs/<date>-task-graph-disposition-decision.md`,含 A/B 数据截图、决策依据、反对意见。

## Risks / Trade-offs

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| 决策时 A/B 数据不充分(实验未跑完) | 中 | 决策推迟 | 决策日推迟到 A/B 数据充分,不强行决策 |
| 删除路径下 git history 找回成本 | 低 | 误删恢复 | task_graph 历史在 git 里永久可查,删除前打 tag `task_graph_archive_<date>` |
| 吸收路径下 slot_extractor 接入引入新 bug | 中 | planner 失败率上升 | 单独 PR 接入,接 CI spike + planner_probe 双重回归 |
| 决策长期推迟(> 1 个月) | 中 | task_graph 继续占 1580 行死代码 | 设置 hard deadline:A/B 启动后 30 天内必须产出决策 |
