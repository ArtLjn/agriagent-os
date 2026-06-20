## Context

当前 Agent 请求已经拆出 Application、Runtime、Router、Executor、Response、Memory、Evaluation 和 Observability 边界。Runtime 图仍是 `llm -> tools -> llm` 的 ReAct 循环；写操作通过 pending action / pending plan 做 Plan-Then-Execute；Evaluation 和诊断可以离线解释失败，但在线链路缺少统一的自检控制点。

这次变更把 Reflection 定义为触发式控制层：它不面向用户暴露为“模式开关”，而是在高风险节点检查当前执行状态，并输出结构化决策。Reflection 的目标是减少错误写入、工具结果与回答不一致、应调用工具却未调用、兜底回复继续流出等问题。

## Goals / Non-Goals

**Goals:**
- 在 Agent 平台新增 `agent/reflector` 边界，提供统一的反思策略、检查模型和决策服务。
- 在写操作 pending action / pending plan 展示或执行前执行反思检查。
- 在工具执行后、最终回复前执行轻量反思检查，确保回复与工具结果一致。
- 将反思结果写入 trace，供 Evaluation、diagnostics 和数据飞轮复用。
- 采用高风险触发策略，控制延迟和 token 成本。

**Non-Goals:**
- 不提供用户可手动选择的“反思模式”聊天入口。
- 不要求每轮 Agent 请求都额外调用 LLM 做 self-critique。
- 不改变现有 `/agent/chat` 和 `/agent/chat/stream` 外部 API 契约。
- 不在本变更中引入新的向量库、RAG 服务或训练管线。

## Decisions

### Decision 1: Reflection 是控制层，不是第三个 Runtime 模式

Reflection 以服务形式挂在 Agent Application/Runtime 的关键节点：

```text
Router/Planner
  -> ReAct 或 Plan
  -> Reflector
      -> pass
      -> ask_clarification
      -> require_tool
      -> block_write
      -> retry_generation
      -> fallback_response
  -> Response
```

选择这个方案是因为 ReAct 和 Plan 是执行形态，而 Reflection 是质量控制形态。把它平铺成第三种模式会导致用户意图路由更复杂，也容易把同一轮请求拆成互斥分支。

备选方案：在 LangGraph 中新增固定 `reflect` 节点，每轮都跑。该方案实现直观，但会增加所有请求延迟，并把简单问候、确定性查询等低风险场景拖入额外流程。

### Decision 2: 反思结果使用结构化模型

新增模型建议包含：
- `ReflectionTrigger`: 触发来源，如 `pre_write_plan`、`post_tool_result`、`pre_final_response`、`fallback_guard`。
- `ReflectionIssue`: 问题类型、严重级别、证据和建议动作。
- `ReflectionDecision`: `pass`、`ask_clarification`、`require_tool`、`block_write`、`retry_generation`、`fallback_response`。
- `ReflectionResult`: 触发器、检查项、问题列表、最终动作和 trace payload。

结构化结果能被测试、trace、diagnostics 和数据飞轮直接消费，避免只靠自然语言 critique 难以断言。

备选方案：只在 prompt 中让模型“回答前先自检”。该方案成本低，但不可观测、不可测试，也无法稳定阻断写操作。

### Decision 3: 先做规则优先，LLM 反思只作为可选增强

MVP 检查优先使用确定性规则：
- 写操作参数缺失、风险等级不匹配、确认文案与参数不一致。
- Router 选择了读工具但最终回复没有工具证据。
- 工具执行失败后仍生成肯定式成功回复。
- 有 selected_tools 且检测到应调工具未调。
- pending plan 多步骤依赖缺失或顺序不合法。

LLM 反思可作为后续增强，仅在复杂多工具总结或规则无法判断时触发。

备选方案：直接使用独立 LLM critic 评审每次输出。该方案可能提升覆盖面，但会增加成本、延迟和新的不确定性。

### Decision 4: Trace 事件与 Evaluation 复用同一 payload

每次触发 Reflection 都记录 `node_type="reflection_check"` 事件，至少包含 trigger、decision、issues、selected_tools、pending_plan_id、tool_call_ids、response_summary 和 latency。Evaluation 从这些事件生成失败标签和回放样本。

备选方案：只写日志，不进入 trace。该方案调试成本低，但无法支持数据飞轮和回归样本自动沉淀。

## Risks / Trade-offs

- 规则误判导致合法写操作被阻断 → 反思决策先返回澄清或重新生成 pending action，不直接丢弃用户输入；高风险阻断必须带 evidence。
- 每轮增加延迟 → 使用触发式策略，低风险闲聊、确定性直达读查询不触发 LLM 反思。
- Runtime 节点继续变胖 → Reflection 放在 `agent/reflector` 边界，Runtime 只调用窄接口。
- trace 事件体过大 → 只记录摘要、ID 和结构化问题，不记录完整敏感参数或长文本。
- LLM critic 与主模型互相矛盾 → MVP 以规则检查为主，LLM critic 输出只能降级为建议，不能直接执行写操作。

## Migration Plan

1. 新增 `agent/reflector` 模块和单元测试，不接入主链路。
2. 接入 pending action / pending plan 展示前检查，先覆盖写操作参数和确认文案一致性。
3. 接入 pending plan 执行前检查，确保用户确认的计划仍有效且未过期。
4. 接入工具后最终回复检查，对明显不一致场景返回澄清或安全兜底。
5. 记录 `reflection_check` trace，并在 Evaluation/diagnostics 中展示。
6. 增加回归用例后再扩大触发范围。

回滚策略：保留配置开关 `agent.reflection.enabled` 和触发器级开关；出现误阻断时可关闭对应触发器，主链路回退到现有 ReAct/Plan 行为。

## Open Questions

- 是否需要在管理后台展示 reflection 事件和 issue 标签，还是先只进入 debug export？
- LLM critic 是否与主模型使用同一 provider，还是固定使用轻量模型？
- 反思结果是否需要进入长期 Memory observation，还是只进入 Evaluation 数据飞轮？
