# v2 `skill.md` 标准

## 目标

`skill.md` 用来告诉模型“有什么业务能力、什么时候用、需要哪些业务信息”。
Business MCP 的聚合接口、`operation` 和内部参数协议由 Agent 适配，禁止暴露给用户。

## MCP 聚合 Skill

Business 可以继续提供一个 `manage_*` MCP 工具，但 Agent 会把每个 operation 展开成
一个单一动作工具。模型看到的是 `query_crop_cycles`、`create_crop_cycle`，不会看到
`manage_crop_cycle(operation=...)`。

```yaml
---
schema_version: 1
name: manage_crop_cycle
kind: mcp
mcp_tool: business.manage_crop_cycle
risk_level: mixed
finalize_after_success: false
description: 管理种植茬口。
triggers: [茬口, 种植]
operations:
  query:
    tool_name: query_crop_cycles
    description: 查询当前农场的种植茬口列表。
    risk_level: read
    parameters: [skip, limit]
    required: []
  create:
    tool_name: create_crop_cycle
    description: 新建一个种植茬口。创建前可先查询作物模板。
    risk_level: write_confirm
    parameters: [name, crop_template_id, start_date]
    required: [name, crop_template_id, start_date]
parameters:
  type: object
  properties:
    operation:
      type: string
      enum: [query, create]
      description: Business MCP 内部字段，不向模型暴露。
    name:
      type: string
      description: 用户可识别的茬口名称
    crop_template_id:
      type: integer
      description: 通过查询作物模板获得的模板 ID
    start_date:
      type: string
      description: 开播日期 YYYY-MM-DD
    skip: {type: integer, description: 分页偏移}
    limit: {type: integer, description: 返回数量}
  required: [operation]
---
```

## 字段约束

- `name`、`mcp_tool` 表示内部 Business 适配关系，不作为模型工具名。
- `finalize_after_success` 默认为 `false`；普通查询即使足以回答单一概览问题，也可能只是复合请求的前置步骤，不能默认设为 `true`。仅用于明确需要结束工具执行的协议边界（例如原子提交完成）；Runtime 会在下一轮撤掉 tools，附带停止执行指令与证据生成最终回答。
- `operations.<op>.tool_name` 是模型实际调用的稳定工具名，使用 snake_case。
- 每个模型工具只代表一个动作，不再要求模型填写 `operation`。
- `description` 使用用户业务语言，不写 MCP、内部枚举或代码流程。
- `parameters` 只列该动作可能使用的参数；`required` 是真正执行前必须具备的业务信息。
- 顶层 `parameters.properties` 复用 Business 参数定义，避免每个 operation 重复写完整 JSON Schema。
- 禁止新增关键词词库、正则 extractor 或 `field_hints`。自然语言理解交给模型，确定性边界交给 schema 和执行校验。

## 选择边界（2026-10-23）

`routing` 可放在聚合 Skill 或 `operations.<op>` 下，支持 `use_when`（适用意图）、
`avoid_when`（不适用意图与替代来源）、`examples`（典型业务表达），值均为非空字符串组成的列表。
操作级同名字段覆盖聚合字段；没有配置时保持原有描述。它们供模型理解语义，不是关键词匹配或路由硬编码。

`Skill.to_openai_tool()` 将这些边界投影到实际工具描述。展开的动作已有自己的描述，仅继承聚合级
`avoid_when` 并补充操作级 routing；聚合级用途和示例不重复复制到每个动作，避免上下文膨胀与读写混淆。
`SkillRegistry.router_catalog()`
同时提供聚合边界及各动作的描述、风险与差异。只写在 Markdown 正文的说明不会自动进入模型，
影响选择的约束应放在这份元数据中，避免主 Agent 与候选路由器看到不同能力定义。

新增能力应同时给出易混淆能力的边界，并加入相近意图回放。个人事项、已发生农事、未来作业单、
天气预警分别来自不同来源，查询结果不得互相替代；某个来源为空也不能推断全部来源为空。

## 空结果策略（2026-10-25）

`operations.<op>.empty_result_policy` 声明同一动作重复返回空集合时的统一响应，
避免 Runtime 为某个业务写死分支。只允许声明在 operation 级，顶层声明会失败。

```yaml
empty_result_policy:
  observation:
    code: system_template_catalog_empty   # snake_case
    message: "..."                         # 非空
    missing: [custom_template.stages]
  next_allowed_action:
    agent_tool_name: prepare_planting_plan # 已注册、exposed、非自身
    arguments: null                        # 必须显式声明；null 或对象
  task_state:
    reason: empty_system_template_catalog  # snake_case
    resume_policy: ask_user
  trace:
    progress_reason: empty_catalog_already_observed
```

Runtime 固定生成 `observation.status=needs_information`、`task_state.status=blocked`、
`blocked_action` 和事件序列；触发条件仍是 `verify.has_empty_observation`（识别
`items/templates/workers/records/results` 中的空列表）。策略只声明“空结果后的响应”，
不声明“什么算空结果”。

`code`、`reason`、`progress_reason` 使用非空 snake_case；`next_allowed_action.arguments`
必须显式存在，省略会被校验拒绝。目标工具必须已注册、对模型暴露且不是当前动作自身。

## 缺参原则

- 可以通过只读工具获得的信息由 Agent 自己查询，例如作物名称对应的模板 ID。
- 只有用户才能决定的信息才追问，例如作物、日期、金额。
- 追问必须使用自然语言，禁止向用户展示 `operation`、字段名、tool 名或 MCP。

## 校验

```bash
PYTHONDONTWRITEBYTECODE=1 python agri_backend_v2/scripts/validate_skill_metadata.py
```

不传目录时默认扫描 `agent/tools` 与所有 `plugins/*/tools`，并跨目录检查公开
`tool_name` 唯一性和空结果策略目标；传入目录时只校验该目录。
