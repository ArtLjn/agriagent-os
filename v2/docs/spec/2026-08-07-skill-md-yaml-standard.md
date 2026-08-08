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
- `finalize_after_success` 默认为 `false`；仅当一次成功调用的结果已经足以回答该 Skill 的典型用户请求时设为 `true`。Runtime 会在下一轮撤掉 tools，只生成最终回答。
- `operations.<op>.tool_name` 是模型实际调用的稳定工具名，使用 snake_case。
- 每个模型工具只代表一个动作，不再要求模型填写 `operation`。
- `description` 使用用户业务语言，不写 MCP、内部枚举或代码流程。
- `parameters` 只列该动作可能使用的参数；`required` 是真正执行前必须具备的业务信息。
- 顶层 `parameters.properties` 复用 Business 参数定义，避免每个 operation 重复写完整 JSON Schema。
- 禁止新增关键词词库、正则 extractor 或 `field_hints`。自然语言理解交给模型，确定性边界交给 schema 和执行校验。

## 缺参原则

- 可以通过只读工具获得的信息由 Agent 自己查询，例如作物名称对应的模板 ID。
- 只有用户才能决定的信息才追问，例如作物、日期、金额。
- 追问必须使用自然语言，禁止向用户展示 `operation`、字段名、tool 名或 MCP。

## 校验

```bash
PYTHONDONTWRITEBYTECODE=1 python v2/scripts/validate_skill_metadata.py
```
