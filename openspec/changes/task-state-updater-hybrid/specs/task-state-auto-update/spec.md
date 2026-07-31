## MODIFIED Requirements

### Requirement: Hybrid Entity Extractor(规则优先 + LLM 兜底 + 熔断)

`update_task_state_from_user_input` 必须按以下顺序执行:
1. 调规则版 extractor(`_AREA_RE`/`_UNIT_NAME_RE`/`_SEASON_RE`)
2. 规则全部 miss 时,若 LLM 熔断器闭合且会话有 active task,调 LLM 走 `LLMTaskStateUpdate` 结构化输出
3. LLM 输出过 validator(每个 matched_missing_fields 必须有非空 extracted_entities),否则降级到规则版结果(无更新)
4. LLM 失败(超时/校验异常/熔断开)时,trace 记录 `task_state_update_fallback`,updater 返回无更新

#### Scenario: 规则命中走 fast path

- **WHEN** active task missing 含"面积",用户输入 "20 亩"
- **THEN** updater 走规则版,不调 LLM,trace 路径标 `rule`

#### Scenario: 规则 miss 但 LLM 命中

- **WHEN** active task missing 含"面积",用户输入 "两万平米"
- **THEN** 规则 miss,updater 调 LLM,LLM 输出 `{matched_missing_fields:["面积"], extracted_entities:{"面积":"两万平米"}}`,updater 剔除 missing,trace 路径标 `llm`

#### Scenario: LLM 输出无效(matched 但无值)

- **WHEN** LLM 输出 `{matched_missing_fields:["面积"], extracted_entities:{}}`(命中但抽不到值)
- **THEN** validator 拒绝,降级到规则版结果(无更新),trace 路径标 `fallback`

#### Scenario: LLM 检测到取消意图

- **WHEN** 用户输入 "算了不种了",LLM 输出 `{status_change: "cancelled"}`
- **THEN** updater 调 `AgentTaskStateStore.mark_cancelled`,trace 路径标 `llm_cancelled`

#### Scenario: 熔断器开时直接降级

- **WHEN** LLM provider 近期失败率超阈值(`_is_summary_circuit_open` 返回 True)
- **THEN** updater 不调 LLM,直接返回规则版结果,trace 路径标 `circuit_open`
