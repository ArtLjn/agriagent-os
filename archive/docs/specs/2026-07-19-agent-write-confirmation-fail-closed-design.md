# Agent 写操作确认 Fail-Closed 修复设计

## 背景

当前 Agent 存在一类高风险缺陷：模型选择或幻觉调用写操作 Skill 时，运行时没有稳定进入
pending action / pending plan，而是可能把调用当作读工具继续执行，或者在最终回复中声称
已经完成写入。

结合当前代码热路径，问题不在 pending 存储本身，而在 pending 之前的风险判定：

```text
AI tool_call
  -> tool_executor._call_one
  -> _permission_decision
  -> requires_confirmation ?
      yes -> _pending_action_message / _pending_plan_tool_message
      no  -> _invoke_read_tool_message
```

只要 `_permission_decision.requires_confirmation` 被误判为 `False`，写操作就绕过
pending。这个判定目前依赖 Skill metadata、Registry operation risk、旧
`WRITE_SKILLS` 白名单和局部参数推断共同决定，多事实源失配后容易漏拦截。

典型风险场景：

- `manage_cost`、`manage_crop_cycle`、`manage_farm_logs` 等多 operation Skill
  自身 metadata 可声明为 read，写风险依赖 `operation` 参数升级。
- 模型调用 canonical Skill 时漏填或填错 `operation`，但参数和用户输入明显是写意图。
- PlanDraft 已判断为写入，但工具层仍按 Tool metadata 重新降级。
- 最终回复层看到已有 tool evidence 后，可能放过“已记录 / 已创建”类幻觉执行文案。

本设计目标是把写操作确认从“依赖模型和 metadata 的普通分支”升级为“不可绕过的运行时
前置安全门”。

## 外部成熟方案借鉴

### Codex：能力边界和审批策略分层

Codex 官方文档把安全控制拆成两层：

- Sandbox mode：技术上能做什么，例如可写目录、网络访问。
- Approval policy：什么时候必须暂停并询问用户，例如越过 sandbox、使用网络或运行不受信任命令。

这说明权限系统不能只靠提示词或工具描述，应在执行器层同时拥有“能力边界”和“审批策略”。
Codex 的 rules 机制还采用更严格规则优先，`forbidden > prompt > allow`，并会尝试拆解
shell wrapper，避免危险动作藏在看似安全的复合命令里。

对 farm-manager 的映射：

- Registry operation risk 是“能力边界”的事实源。
- pending action / pending plan 是“审批策略”的用户确认层。
- 写风险判断必须发生在工具执行前，且不能被 Skill 自身 read metadata 覆盖。
- 对多 operation Skill，不能只看 tool name；必须看规范化后的真实 operation 和参数影响。

参考：

- [Codex Agent approvals & security](https://developers.openai.com/codex/agent-approvals-security)
- [Codex Sandbox](https://developers.openai.com/codex/concepts/sandboxing)
- [Codex Rules](https://developers.openai.com/codex/rules)
- [Codex Config reference](https://developers.openai.com/codex/config-reference)

### Claude Code：权限由运行时执行，且可设置不可绕过前置钩子

Claude Code 文档明确说明：权限规则由 Claude Code 执行，不由模型执行；`CLAUDE.md`
或 prompt 只能影响模型想做什么，不能改变运行时允许什么。Claude Agent SDK 的权限
顺序是：

```text
Hooks
  -> Deny rules
  -> Ask rules
  -> Permission mode
  -> Allow rules
  -> canUseTool callback
```

关键借鉴：

- Hooks 先于 allow / mode 执行；如果某个检查必须覆盖所有工具调用，应放在
  PreToolUse hook，而不是 canUseTool callback。
- Ask 规则即使命中 bypass mode 也会进入确认；需要用户交互的工具不会因为 allow 规则
  被静默执行。
- 自动批准的工具不会再进入 canUseTool callback，因此不能把关键安全检查放在可被 allow
  绕过的位置。
- plan mode 中写操作不能自动批准，必须回到确认 callback。

Claude Code auto mode 的工程文章还强调，权限分类要判断“用户是否授权了这个动作”，而不是
动作是否和目标相关；agent 自己推断的目标、批量范围、凭据、生产资源等都应保守阻断。

对 farm-manager 的映射：

- 本项目需要一个等价于 PreToolUse hook 的 `WriteOperationGuard`，在所有 ToolMessage
  执行前运行。
- pending action / pending plan 对应 canUseTool callback，但写安全不能只放在 pending
  入口，因为一旦权限判定为 read，pending 入口就不会被调用。
- 用户没明确授权写入目标、操作类型、批量范围或结算金额时，应创建澄清而不是写 pending。
- PlanDraft 表示 write route 时，应强制进入 pending 或 clarification，不能被 read metadata
  降级。

参考：

- [Claude Code permissions](https://code.claude.com/docs/en/permissions)
- [Claude Agent SDK permissions](https://code.claude.com/docs/en/agent-sdk/permissions)
- [Claude Agent SDK approvals and user input](https://code.claude.com/docs/en/agent-sdk/user-input)
- [Claude Code auto mode engineering note](https://www.anthropic.com/engineering/claude-code-auto-mode)

## 设计原则

1. 运行时强制，不依赖 prompt。Skill 文档可以减少误选，但不能承担写安全边界。
2. Registry-first。operation risk 以 `skills.yaml` / `aliases.yaml` 为事实源，旧白名单只做兼容兜底。
3. Fail closed。无法确定是 read 还是 write 时，只要存在写意图证据，就走 clarification 或 pending，不直接执行。
4. Deny / Ask / Allow 分层。禁用与高风险阻断优先，其次写确认，最后才是读执行。
5. 计划不能降级。PlanDraft、RouterDecision、ToolCall 三者不一致时，以更高风险结果为准。
6. 可观测。每次阻断、澄清、pending 创建和 direct read 都要有 trace，可用于 data flywheel 回放。

## 推荐运行时架构

新增一个逻辑组件，不要求第一版新建文件，可先落在
`backend/app/agent/runtime/tool_metadata.py` 中：

```text
ToolCall
  -> WriteOperationGuard.resolve()
      input:
        tool_name
        raw_args
        normalized_args
        original_user_input
        plan_draft
        router_decision
        runtime_tool_metadata
      output:
        risk_decision
          status: read | ask_pending | clarify | deny
          capability
          operation
          operation_risk
          normalized_args
          reason
          evidence
  -> deny       : 返回工具失败 / 安全阻断 ToolMessage
  -> clarify   : 返回澄清 ToolMessage，不创建 pending
  -> ask_pending: 创建 pending action / pending plan
  -> read       : 执行读工具
```

### 风险决策顺序

```text
1. 工具是否存在、是否禁用
2. Registry alias / canonical capability 解析
3. operation 推断
   3.1 显式 args.operation
   3.2 validated PlanDraft step
   3.3 Router frame params_hint / intent
   3.4 参数特征推断
   3.5 用户原话写意图证据
4. operation risk 解析
5. 冲突处理
   - plan says write + metadata says read -> ask_pending
   - params look write + operation missing -> clarify 或 ask_pending
   - tool selected as read + args contain write fields -> clarify
   - high risk delete / batch / settlement target ambiguous -> clarify
6. 输出 risk_decision
```

### 风险状态语义

| status | 含义 | 后续动作 |
| --- | --- | --- |
| `read` | Registry operation 明确是 read，且没有写入参数污染 | 直接执行 |
| `ask_pending` | 写操作参数足够形成确认 | 创建 pending action / pending plan |
| `clarify` | 存在写意图但关键字段不足或冲突 | 返回澄清，不执行 |
| `deny` | 工具禁用、越权、高风险不可恢复动作缺少授权 | 阻断并记录 trace |

## 修复范围

### 范围内

| 模块 | 修改点 |
| --- | --- |
| `app/agent/runtime/tool_metadata.py` | 增加统一 operation 推断和 risk decision，替代局部硬编码 |
| `app/agent/runtime/tool_executor.py` | 在 `_call_one` 中把 risk decision 放到 pending / read 执行前 |
| `app/agent/runtime/tool_pending.py` | pending 创建使用已解析 operation 和 normalized args |
| `app/skills/metadata.py` | 暴露公共 operation 推断函数，避免 runtime 与 skill metadata 双写 |
| `app/agent/runtime/reflection.py` | 最终回复对 write route 但无 pending / confirmed write result 的情况 fail closed |
| tests | 增加 canonical 多 operation Skill 漏 operation 的回归测试 |

### 范围外

| 范围 | 原因 |
| --- | --- |
| 大规模 Skill 目录搬迁 | 属于 skill-capability-governance 后续阶段 |
| 重写 Router / PlanDraft | 当前只修执行前安全门 |
| 引入外部审批服务 | 本地 pending action / pending plan 足够承载第一版确认 |
| LLM prompt 大改 | prompt 不是安全边界，最多作为补充优化 |

## 详细方案

### Phase 1：统一 operation 推断

目标：同一套逻辑同时服务 metadata、runtime permission、pending、trace。

建议在 `app.skills.metadata` 中暴露公共函数：

```python
def infer_skill_operation_name(
    skill_name: str,
    params: Mapping[str, Any] | None,
    *,
    original_input: str = "",
    plan_draft: Mapping[str, Any] | None = None,
    router_decision: Any | None = None,
) -> OperationInferenceResult:
    ...
```

第一版可不新增 dataclass，先返回 dict，但字段必须稳定：

```text
operation
confidence: explicit | plan_draft | router | params | user_input | unknown
is_ambiguous
missing_fields
evidence
```

需要覆盖的 canonical Skill：

| Skill | read operation | write operation |
| --- | --- | --- |
| `manage_cost` | `query_summary`、`query_debt`、`analyze_cost` | `create_record`、`delete_record`、`settle_debt` |
| `manage_crop_cycle` | `query_cycles`、`query_cycle_info` | `create_cycle`、`update_cycle`、`update_stage`、`delete_cycle` |
| `manage_crop_templates` | `query_templates` | `create_template`、`manage_template` |
| `manage_farm_logs` | `query_logs` | `create_log`、`manage_log` |
| `manage_work_orders` | `query_work_orders` | `create_work_order`、`update_work_order` |
| `manage_workers` | `query_workers` | `manage_worker` |
| `manage_labor_payment` | `query_payables` | `settle_payment`、`manage_wage` |
| `manage_planting_units` | `query_units` | `manage_units` |
| `manage_cost_categories` | `query_categories` | `manage_category` |
| `manage_settings` / `manage_user_settings` | `query_settings` | `update_settings` |

验收：

- `get_skill_call_metadata()` 和 runtime `_permission_decision()` 使用同一个推断入口。
- 不再出现一个模块认为 read、另一个模块认为 write 的同参数分歧。

### Phase 2：新增不可绕过的 WriteOperationGuard

目标：所有 tool call 在执行前必须经过风险门。

推荐顺序：

```text
_call_one
  -> raw_args / normalized_args
  -> risk_decision = resolve_tool_call_risk(...)
  -> disabled / deny
  -> validation
  -> clarify
  -> pending
  -> read invoke
```

注意：

- 不要让 `SkillMetadata(permission_level=READ)` 直接决定 read。
- 不要让旧 `WRITE_SKILLS` 缺项导致 canonical Skill 降级。
- 对 `operation_risk in {"write_confirm", "write_high"}` 一律 `ask_pending` 或 `clarify`。
- 对 write-like 参数但 operation 不可确定，一律 `clarify`。

写意图参数示例：

| Skill | 写意图参数 |
| --- | --- |
| `manage_cost` | `amount`、`category`、`record_type`、`record_subtype`、`counterparty`、`record_id` |
| `manage_crop_cycle` | `crop_name`、`area`、`start_date`、`stage`、`target_stage`、`deleted` |
| `manage_farm_logs` | `operation_type`、`operation_date`、`note`、`photo_urls`、`log_id + action` |
| `manage_work_orders` | `operation_type`、`workers`、`unit_names`、`payable_amount`、`work_order_id + update fields` |

验收：

- canonical Skill 缺 operation 时不会直接执行写入。
- read operation 带写字段污染时不会直接执行。
- PlanDraft 说 write 时，无论 Tool metadata 如何，最终都进入 pending 或 clarification。

### Phase 3：pending 创建消费 risk decision

目标：pending 中保存的是最终确认过的 capability / operation / params，而不是 LLM 原始猜测。

要求：

- pending params 必须包含 resolved operation。
- confirmation_context 必须记录：
  - `resolved_capability`
  - `resolved_operation`
  - `operation_risk`
  - `inference_source`
  - `original_input`
- trace `skill_call` 的 pending 输出必须包含 risk decision evidence。
- pending plan 的每个 step 都要带 operation risk，确认文案展示真实影响范围。

验收：

- 用户确认后执行的参数与确认文案一致。
- trace 能复盘为什么进入 pending，而不是直接执行。

### Phase 4：最终回复 fail-closed

目标：即使工具层异常或模型回复幻觉，也不能对用户声称已写入。

新增判断：

```text
if plan_draft.route_type in {write_pending_action, write_pending_plan}
   and no pending_created
   and no confirmed_write_result:
       block success claim
       return safe fallback
```

还需覆盖：

- selected tool 是 write-like，但返回 ToolMessage 不是 pending marker。
- tool result 是 `NEED_CLARIFY` / validation error，但 final reply 说“已记录”。
- read tool 被污染为写入参数，final reply 说“已更新”。

验收：

- “已记录 / 已创建 / 已保存 / 已更新”只能出现在 confirmed write result 之后。
- pending 创建成功时，最终回复应表达“待确认”，不能表达“已执行”。

### Phase 5：Data Flywheel 与诊断增强

新增或统一质量标签：

| 标签 | 触发条件 |
| --- | --- |
| `pending_missed` | write risk decision 为 ask/clarify，但无 pending lifecycle |
| `unsafe_write_direct_execution` | write operation 出现 success tool result 且无确认 |
| `operation_inference_conflict` | plan/router/args/metadata 对 operation 判断冲突 |
| `write_success_hallucination` | 无 confirmed write result 但 final reply 声称完成 |

诊断输出新增：

```json
{
  "tool_risk_decision": {
    "status": "ask_pending",
    "capability": "manage_cost",
    "operation": "create_record",
    "operation_risk": "write_confirm",
    "inference_source": "params",
    "evidence": {}
  }
}
```

## 回归测试清单

### 必须新增

| 用例 | 期望 |
| --- | --- |
| `manage_cost` 缺 operation，但有 `amount/category` | 创建 pending，不直接执行 |
| `manage_cost` 缺 operation，原话是“今天卖西瓜收入100万” | 创建收入记账 pending，金额不直接落库 |
| `manage_cost` `operation=query_summary` 但带 `amount/category` | clarification，不直接执行 |
| `manage_crop_cycle` 缺 operation，但有 `crop_name/area` | pending 或 clarification，不直接执行 |
| `manage_farm_logs` 缺 operation，但有 `operation_type/note` | pending 或 clarification，不直接执行 |
| `manage_work_orders` 缺 operation，但有 `workers/unit_names/operation_type` | pending，不直接执行 |
| PlanDraft 是 `write_pending_action`，Tool metadata 是 read | pending，不直接执行 |
| PlanDraft 是 write，但 pending 未创建，final reply 说“已记录” | reflection fallback |
| 明确 read operation | 不创建 pending，正常执行 |

### 需要保留

- `manage_labor_payment` 结算与查询的现有参数推断用例。
- `manage_user_settings` 查询 / 更新分流用例。
- legacy alias 写操作 pending 用例。
- pending plan 多步骤确认用例。

## 实施顺序

1. 加 failing tests：先覆盖 `manage_cost`、`manage_crop_cycle`、PlanDraft 降级三类漏拦截。
2. 提取公共 operation 推断入口，让 metadata 和 runtime 共用。
3. 在 `_call_one` 前半段接入 `WriteOperationGuard`，输出结构化 risk decision。
4. 修改 pending 创建使用 risk decision 的 resolved args。
5. 增强 reflection 的 write route fail-closed。
6. 补充 data flywheel 标签与 debug export 字段。
7. 跑目标测试、ruff、复杂度预算和 layer deps。

建议目标测试：

```bash
PYTHONDONTWRITEBYTECODE=1 pytest \
  backend/tests/agent/test_tool_executor_metadata.py \
  backend/tests/agent/test_plan_draft_pending_execution.py \
  backend/tests/agent/test_reflection_runtime_flow.py \
  backend/tests/skills/test_skill_metadata.py \
  -q
```

全量验证按项目规则执行：

```bash
PYTHONDONTWRITEBYTECODE=1 ruff check --no-cache backend/app backend/tests
PYTHONDONTWRITEBYTECODE=1 pytest backend/tests/agent backend/tests/skills -q
bash scripts/check-complexity-budget.sh
bash scripts/check-layer-deps.sh
```

## 风险与取舍

| 风险 | 处理 |
| --- | --- |
| 误把读查询拦成 pending | read operation 明确时允许读；参数污染时澄清 |
| 过多 clarification 影响体验 | 第一版优先安全，后续用 data flywheel 调整推断规则 |
| operation 推断规则继续分散 | 强制 metadata/runtime/pending 共用同一入口 |
| prompt 仍会声称已执行 | reflection 增加 write route fail-closed |
| `WRITE_SKILLS` 与 Registry 长期双源 | 旧白名单只作 fallback，新逻辑以 Registry operation risk 为准 |

## 完成定义

- 所有写 operation 在执行前必经 risk decision。
- `operation_risk=write_confirm/write_high` 不可能直接进入 `_invoke_read_tool_message`。
- canonical 多 operation Skill 缺 operation 时不直接执行写入。
- pending action / pending plan trace 可解释风险来源和确认内容。
- final reply 不再在无 confirmed write result 时声称已执行。
- 新增回归测试覆盖本次问题路径。

