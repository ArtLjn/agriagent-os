## Why

当前 Agent 对“李海这个月干了15天压瓜”这类农事 + 用工 + 工资策略的多意图输入识别不足，可能在未调用写 Skill、未生成 pending action/plan 的情况下回复“已记录”。需要在不引入重型多 Agent 架构的前提下，补齐前置语义计划、路由回归和最终回复守门。

## What Changes

- 新增轻量 `Semantic Gate`：在 SkillRouter/LLM 之前识别高风险写入、多意图写入和隐式农事用工句。
- 增强 `IntentFrame` 产出：支持表达作业、工人、用工数量、工资策略、待查询默认日薪、缺失字段等计划线索。
- 规范 `pending plan` 触发：只有确定性多写入或作业 + 用工 + 工资计划可生成待确认计划；缺关键字段时必须澄清。
- 扩展 Reflection 守门：即使 router 未选中工具，只要最终回复含“已记录/已创建/已保存”等成功写入话术，也必须 fail-closed。
- 补齐农事用工与多意图 Skill 路由回归，覆盖误抽工人名、无工具成功话术、pending plan 参数为空等风险。
- 明确保留当前单主 Agent + Skill + Pending + Reflection 范式；多 Agent 只作为离线分析/评测/报告的后续可选能力，不进入本次主链路。

## Capabilities

### New Capabilities

- `agent-semantic-planning`: 前置语义门和轻量计划能力，覆盖多意图写入识别、隐式农事用工解析、缺字段澄清和 pending plan 候选生成。

### Modified Capabilities

- `agent-intent-router`: 路由必须识别农事 + 工人 + 天数/工资策略等隐式写入，不得把该类输入漏成无工具闲聊。
- `agent-reflection-control`: Reflection 必须覆盖 selected_tools 为空但最终回复声称写入成功的场景。
- `write-skill-plan-execution`: pending plan 必须支持确定性多意图写入，同时缺关键字段时必须澄清而不是生成空参数计划。
- `skill-regression-evaluation`: 回归集必须覆盖农事用工、多意图写入、无工具成功话术和参数抽取错误。

## Impact

- 影响代码：
  - `backend/app/agent/router/classifier.py`
  - `backend/app/agent/router/models.py`
  - `backend/app/agent/router/policy.py`
  - `backend/app/agent/runtime/nodes.py`
  - `backend/app/agent/runtime/reflection.py`
  - `backend/app/agent/reflector/checks.py`
  - `backend/app/agent/runtime/tool_executor.py`
  - 相关 router/reflection/pending/evaluation 测试
- 影响文档：
  - `farm-manager-design-spec/01_正式设计/13_Agent范式规范化设计.md`
  - `farm-manager-design-spec/01_正式设计/12_Skill路由选择架构.md`
- 不新增外部依赖。
- 不改变 HTTP API。
- 不改变写操作必须用户确认后执行的安全边界。
