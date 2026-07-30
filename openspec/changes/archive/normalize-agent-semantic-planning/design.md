## Context

Farm Manager 当前是单主 Agent 流水线：SkillRouter 选择候选 Skill，LLM 生成 tool_call，Tool Executor 拦截写操作为 pending action/plan，Reflector 在 pending 或工具结果阶段做一致性检查。这个范式足够支撑日常查询和明确写操作，但对隐式多意图输入覆盖不足。

典型失败输入是“李海这个月干了15天压瓜”。它同时包含农事事实、工人用工事实和工资/欠款推导线索。当前规则可能没有生成 `IntentFrame`，导致 LLM 在无工具调用时直接回复“已记录”。这不是多 Agent 数量不足，而是前置语义计划和最终写入话术守门不足。

## Goals / Non-Goals

**Goals:**

- 在主对话链路中保留单 Agent + Skill 范式。
- 增加轻量 Semantic Gate，识别隐式写入、多意图写入和农事用工句。
- 复用现有 `IntentFrame`、`RouterDecision`、pending action、pending plan、Reflection，不引入新运行时。
- 保证写操作没有 pending confirm 时不能声称成功。
- 为农事用工、多意图计划、参数抽取错误建立回归测试。

**Non-Goals:**

- 不引入全量多 Agent 协作框架。
- 不让 Skill 互相调用。
- 不新增外部依赖或 HTTP API。
- 不解决所有自然语言解析问题，只覆盖高风险写入和当前失败模式。
- 不改变已确认写操作的执行语义和权限模型。

## Decisions

### Decision 1: 用 Semantic Gate 增强 Router，而不是引入多 Agent

Semantic Gate 是一组轻量规则和受限解析函数，放在 router/classifier 边界内或作为其薄包装。它只输出结构化意图帧和澄清原因，不直接调用工具。

选择原因：

- 当前问题发生在 router 前后，不需要多个自治 Agent。
- 规则可测试、可回归、成本低。
- 可复用现有 `IntentFrame` 和 `RouterDecision` trace。

替代方案：

- LLM planner：理解力更强，但成本高、稳定性和测试性较差。
- 多 Agent planner/reviewer：适合离线分析，不适合主聊天低延迟链路。

长期约束：

- 本 change 的轻量规则只用于安全门、高频稳定表达和已知失败样本兜底。
- 不允许把长期自然语言理解能力建设成不断增长的正则列表。
- 当同一业务域持续出现相似语义补丁时，应升级为 Structured Planner + Domain Validator：Planner 输出结构化 `intent_frames`、实体、缺失字段、置信度和风险；Validator 负责校验工人、地块、茬口、默认工资、金额、日期范围是否可唯一确定。
- 即使 Planner 识别成功，写操作仍必须进入 pending action/plan；没有工具或 pending 证据时，Reflection 继续禁止“已记录/已创建/已保存”等成功话术。

### Decision 2: 农事用工输入优先收敛到 `create_operation_work_order`

当输入同时包含工人、作业类型、用工数量或工资策略时，默认主 Skill 是 `create_operation_work_order`，因为它能同时表达农事作业、用工明细和人工成本。

例外：

- 明确只说“记工资/工资记录”时使用 `manage_wages`。
- 明确“结算/发工资/补付”时使用 `settle_labor_payment`。
- 只记录无工人的农事动作时使用 `log_farm_activity`。

### Decision 3: 缺关键字段时澄清，不生成空 pending plan

Semantic Gate 可以识别计划候选，但只有关键参数足够确定时才进入 pending action/plan。否则返回澄清，或绑定写 Skill 让执行器产生 NEED_CLARIFY，但不得展示空参数确认。

关键字段包括：

- 作业类型。
- 工人姓名。
- 时间语义能否落为单日或范围策略。
- 工资策略：明确单价、不计薪、已付，或可唯一使用工人默认日薪。
- 茬口/范围是否可唯一推断。

### Decision 4: Reflection 增加 pre-final 写入话术守门

现有 Reflection 主要在 selected_tools 或 tool_messages 存在时触发。新增守门规则：即使 selected_tools 为空，只要输入像写入且最终回复声称“已记录/已创建/已保存/已执行”，也必须返回安全兜底或澄清。

这条规则只阻断写入成功话术，不阻断普通解释、建议或闲聊。

### Decision 5: pending plan 只覆盖确定性多意图

允许的 MVP 计划：

- 新工人 + 作业：`manage_workers` -> `create_operation_work_order`。
- 作业 + 用工 + 明确工资：`create_operation_work_order`。
- 作业 + 用工 + 可唯一默认工资：`create_operation_work_order`。

暂不支持：

- 删除 + 新增混合计划。
- 需要复杂数据库搜索才能定位多个历史记录的计划。
- 需要外部实时数据参与写入的计划。

## Risks / Trade-offs

- [Risk] 规则误判把普通叙述当写操作 → Mitigation: 仅对包含作业/工人/数量/写入成功风险的组合触发，新增闲聊和查询反例测试。
- [Risk] 参数抽取再次出错，例如把“6号棚压蔓”抽成工人 → Mitigation: 工人名抽取使用上下文 workers 优先，地块/作业词作为排除边界，并补回归。
- [Risk] pending plan 覆盖范围过窄 → Mitigation: MVP 只覆盖确定性场景，复杂场景澄清。
- [Risk] Reflection 误拦截只读回复 → Mitigation: 守门条件必须同时满足“写入型输入或写入型回复成功话术”，只读业务事实仍走现有检查。
- [Risk] RouterPolicy `max_write_tools=1` 与多步骤计划冲突 → Mitigation: 不放宽普通 LLM 绑定预算；仅对 Semantic Gate 产出的确定性 plan candidate 使用 pending plan 路径。

## Migration Plan

1. 添加回归测试，先覆盖当前失败样例和反例。
2. 增强 router/classifier 的农事用工识别与参数抽取。
3. 增加 pre-final 写入话术守门。
4. 补 pending plan 确定性场景支持。
5. 更新设计文档和评测用例。

回滚策略：

- Semantic Gate 以小函数和独立测试接入，可通过禁用新增规则退回原路由。
- Reflection 守门只影响成功写入话术，可局部回滚该检查。
