## 1. LLMTaskStateUpdate schema

- [ ] 1.1 新建 `backend/app/agent/runtime/task_state_updater_schemas.py`,定义 pydantic `LLMTaskStateUpdate`:
  ```python
  class LLMTaskStateUpdate(BaseModel):
      matched_missing_fields: list[str]
      extracted_entities: dict[str, str]
      status_change: Literal["", "cancelled", "completed"] = ""
      reasoning: str = ""
  ```
- [ ] 1.2 加 model_validator:`matched_missing_fields` 中每个字段必须在 `extracted_entities` 里有非空值(否则 raise)
- [ ] 1.3 写 prompt 模板 `backend/app/memory/prompts/task_state_extract.md`:输入 active_task + user_input,要求 LLM 按 schema 输出
- [ ] 1.4 在 `app/prompt/registry.py` `_load_memory_prompts` 加载该模板,key 为 `memory.task_state_extract`

## 2. Hybrid updater 实现

- [ ] 2.1 在 `backend/app/agent/runtime/task_state_updater.py` 重构 `update_task_state_from_user_input`:
  - 第 1 步:跑规则版,有命中则直接返回
  - 第 2 步:规则 miss 时,检查 `_is_summary_circuit_open()`,开则 fallback
  - 第 3 步:调 LLM `with_structured_output(LLMTaskStateUpdate)`,超时 10s
  - 第 4 步:validator 过则用 LLM 结果(status_change 处理),不过则 fallback
- [ ] 2.2 LLM 成功时调 `_record_llm_success(circuit_key)`,失败时调 `_record_llm_failure`
- [ ] 2.3 写 trace event `task_state_updated`,字段含 `path: rule|llm|fallback|llm_cancelled|circuit_open`、`extracted_entities`、`status_change`

## 3. 测试

- [ ] 3.1 `backend/tests/agent/runtime/test_task_state_updater.py` 新增 case:
  - test_rule_hit_skips_llm
  - test_rule_miss_llm_hit(模拟"两万平米")
  - test_llm_invalid_output_falls_back(模拟 matched 但无值)
  - test_llm_detects_cancellation(模拟"算了不种了")
  - test_circuit_open_falls_back
  - test_llm_timeout_falls_back
- [ ] 3.2 mock LLM 用 `langchain_core.language_models.FakeChatModel` 或类似
- [ ] 3.3 spike `context_multiturn_spike_cases.yaml` 加新 scenario `diverse_expressions`,跑 5 个多样化表达 case

## 4. 验证

- [ ] 4.1 跑新 scenario `diverse_expressions`,LLM 路径命中率 ≥ 80%
- [ ] 4.2 监控 trace `task_state_updated.path` 分布:rule 占 ~60%、llm 占 ~30%、fallback 占 ~10%
- [ ] 4.3 playground 多样化表达 case 通过("两万平米种草莓"/"原来那个阳光棚"/"算了不种了")
- [ ] 4.4 `bash harness-check.sh` 全量回归

## 5. 上线

- [ ] 5.1 提交 PR,关联 `docs/specs/2026-07-31-agent-harness-design.md` 缺陷 #3 + Stage 5 hybrid updater
- [ ] 5.2 50% 灰度,监控 LLM 成本 + 用户承接满意度
- [ ] 5.3 2 周后根据数据决定全量
- [ ] 5.4 在变更记录追加"缺陷 #3 hybrid updater 已实施"

## 6. 后置依赖

- [ ] 6.1 此变更依赖 `explicit-planner-stage` 上线(共享熔断与 trace infrastructure),应在 planner 上线后启动
- [ ] 6.2 此变更依赖 `fix-task-state-context-gating` 规则版落地(本变更是其升级),不可先于其上线
