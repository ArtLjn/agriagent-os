## Context

`fix-task-state-context-gating` 引入的规则版 updater 在 spike 上覆盖了核心 case(20 亩/3 号棚),但实际生产表达多样:

- "两万平米种草莓" → `_AREA_RE` 只认"亩",漏抽
- "原来那个阳光棚" → `_UNIT_NAME_RE` 要求"叫/名称叫"前缀,漏抽
- "算了不种了" → 用户取消意图,updater 应建议把 task_state 标记 cancelled
- "改种番茄 30 亩吧" → 同时含取消(原作物)+ 补充(新作物+面积)

这些规则版都处理不了,会落 `no_task_state_signal` 兜底,bundle 里 missing 不变,LLM 反复追问。

## Goals / Non-Goals

**Goals**:
- 把规则版 ~60% 覆盖率提升到 ~90%(LLM 兜底)
- 复用现有熔断模式(`_is_summary_circuit_open` / `_record_llm_failure`),不引入新依赖
- trace 完整记录每次更新走哪条路径(rule / llm / fallback / cancelled)

**Non-Goals**:
- 不改规则版本身(它仍是 fast path,先试规则)
- 不引入 LangChain agent / ReAct(updater 是单次 LLM 调用,不需要循环)
- 不改 task_state schema(仍只更新 missing_information / entities / status)

## Decisions

**D1: 规则优先,LLM 兜底,而非并联**

rationale: 规则版无 LLM 成本、可解释、对核心 case 100% 准确。LLM 兜底仅覆盖规则 miss 的 case,成本可控(估算 ~40% turn 走 LLM 路径)。

**D2: LLMTaskStateUpdate schema 用结构化输出**

rationale: pydantic BaseModel + `with_structured_output`,proven by planner_probe 模式。schema 字段:
- `matched_missing_fields: list[str]` —— 命中 missing_information 的哪些字段
- `extracted_entities: dict[str, str]` —— 抽出的 entity 值
- `status_change: literal["", "cancelled", "completed"]` —— 任务态变更
- `reasoning: str` —— LLM 推理过程(trace 可见)

**D3: 熔断器复用 summary 的 key 但独立计数**

rationale: 同一 LLM provider 失败可能并发影响 summary 与 updater。复用 `_build_circuit_key(llm)` 拿到 key,但 `_record_llm_failure` / `_record_llm_success` 走独立 counter,避免 summary 失败拖累 updater。

**D4: LLM 输出过 validator,异常时降级**

rationale: LLM 可能输出"`matched_missing_fields=['面积']` + `extracted_entities={'面积': '未知'}`"(说命中但抽不到值)。加 validator:matched 字段必须在 extracted_entities 里有非空值,否则视为 LLM 失败,降级到规则版结果。

## Risks / Trade-offs

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| LLM 路径延迟(turn 末尾 +1-2s) | 高 | 用户体验下降 | LLM 调用走 background task,不阻塞主链路回复 |
| LLM 误抽("种草莓 20 亩"误识别为取消) | 中 | task_state 错误标记 cancelled | validator + 用户后续输入可纠正;cancelled 状态可逆 |
| LLM 成本超预算 | 中 | 月度成本 +X% | 熔断器 + 50% 流量灰度 + counter 监控 |
| updater 与 planner.draft 双重调 LLM | 低 | 成本翻倍 | planner.draft 仅首轮调,updater 每轮调,无冲突 |
