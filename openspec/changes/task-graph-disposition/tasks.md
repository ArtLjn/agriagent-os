## 1. 决策准备(前置,等 explicit-planner-stage 上线 2 周)

- [ ] 1.1 收集 A/B 实验数据:LLM planner 成功率(planner_probe 5 case + playground 实际)
- [ ] 1.2 收集 task_graph 现有 import:`grep -rn "from app.agent.task_graph" backend/`
- [ ] 1.3 评估 slot_extractor 当前实现状态(是否独立可用、依赖范围)

## 2. 决策产出

- [ ] 2.1 召开决策评审(或 AI 自决),明确走"吸收"还是"删除"
- [ ] 2.2 写 `docs/specs/2026-XX-XX-task-graph-disposition-decision.md`,含:
  - A/B 数据(成功率、成本、用户满意度)
  - 决策依据(对照 explicit-planner-stage design.md D1 的 80% 门槛)
  - 反对意见(若有)
  - 执行计划(指向下面的步骤 3 或 4)

## 3. 删除路径(若决策为删除)

- [ ] 3.1 打 tag `task_graph_archive_<date>`,git push --tags
- [ ] 3.2 把 `backend/app/agent/task_graph/plan_ir.py` 中 `validate_plan_ir` + `PlanIRValidationError` 迁移到 `backend/app/agent/runtime/planner/validation.py`
- [ ] 3.3 把 `backend/app/agent/task_graph/compiler.py` 中 `compile_plan_ir` 迁移到 `backend/app/agent/runtime/planner/compiler.py`
- [ ] 3.4 更新 `backend/app/agent/runtime/planner/llm_planner.py` 与 `backend/scripts/planner_probe.py` 的 import 来源
- [ ] 3.5 删除 `backend/app/agent/task_graph/` 整个目录
- [ ] 3.6 更新 `backend/tests/agent/task_graph/` 迁移到 `backend/tests/agent/runtime/planner/`

## 4. 吸收路径(若决策为吸收)

- [ ] 4.1 把 `backend/app/agent/task_graph/slot_extractor.py` 接入 `planner.draft` 节点,作为 LLM 输出后的 entity 校验/补全
- [ ] 4.2 在 task_graph 目录 README.md 标注"仅 slot_extractor + validation + compiler 在用,其余废弃"
- [ ] 4.3 加 integration test:LLM planner + slot_extractor 联调,验证 entity 抽取准确率

## 5. 验证与上线

- [ ] 5.1 跑 `backend/scripts/planner_probe.py` 5 case 全过(迁移后无回归)
- [ ] 5.2 跑 `bash harness-check.sh` 全量回归
- [ ] 5.3 提交 PR,关联 `docs/specs/2026-07-31-agent-harness-design.md` 阶段 3 + 决策文档
- [ ] 5.4 在 harness 设计文档变更记录追加"阶段 3 已实施(<日期> 决策为 <删除/吸收>)"

## 6. 决策日 hard deadline

- [ ] 6.1 A/B 启动后 30 天内必须完成步骤 2(决策产出),否则 escalate
- [ ] 6.2 决策产出后 14 天内必须完成步骤 3 或 4(执行)
