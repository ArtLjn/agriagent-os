## Context

三个解析端点（crop/cycle/cost）共享同一个模式：

```
get_llm() → ainvoke([HumanMessage]) → reply.content → safe_parse_json(reply) → Pydantic.model_validate(data)
```

`safe_parse_json` 依赖 Markdown 代码块提取，如果 LLM 不用代码块包裹 JSON，解析失败。日志中有 21 次相关失败记录。

LangChain 的 `with_structured_output(Schema)` 通过 Function Calling / tool_choice 机制，让 LLM 直接返回符合 Pydantic schema 的结构化对象，跳过手动 JSON 解析。

Spike 验证：`ChatOpenAI.with_structured_output` 方法存在，3 个 Pydantic schema（CropTemplateParseResponse、CycleParseResponse、CostParseResult）均可正确转换为 JSON Schema。

## Goals / Non-Goals

**Goals:**

- 三个解析端点（crop/cycle/cost）使用 `with_structured_output` 替代 `safe_parse_json`
- 彻底消除 "AI 返回格式异常" 类错误
- 简化代码：删除 JSON 解析 + Pydantic 校验两步逻辑

**Non-Goals:**

- 不改动每日建议解析（走 Agent 图，不适合用 structured output）
- 不删除 `json_repair.py`（其他场景仍在使用）
- 不改动 `get_llm()` 本身的逻辑

## Decisions

### Decision 1: 用 `method="function_calling"` 而非 `method="json_mode"`

**选择**: `llm.with_structured_output(Schema, method="function_calling")`

**备选**: `method="json_mode"` — 只约束 JSON 格式不约束 schema

**理由**: `function_calling` 通过 tool_choice 强制模型输出完全匹配 schema 的参数，约束力最强。`json_mode` 只保证返回合法 JSON，仍需手动校验字段。需要 provider 支持 Function Calling。

### Decision 2: 保留 `safe_parse_json` 作为 fallback

**选择**: 如果 `with_structured_output` 抛异常（如 provider 不支持 tool_choice），回退到当前逻辑

**备选**: 直接替换，不保留 fallback

**理由**: 当前 providers.json 中有 ollama/nvidia/dashscope 三个 provider，不同 provider/model 对 tool_choice 的支持程度不同。保留 fallback 确保不会因 provider 能力限制导致功能完全不可用。

### Decision 3: Prompt 模板保留，但去掉 JSON 格式约束

**选择**: 保留 Jinja2 模板中的业务指令，去掉 "只返回 JSON 对象" 等 JSON 格式说明

**理由**: `with_structured_output` 底层通过 Function Calling 注入 schema，prompt 中不需要再描述 JSON 格式。但业务指令（如 "解析作物名称、品种、生长阶段"）仍需保留以指导 LLM 提取正确信息。

## Risks / Trade-offs

- **[Risk] 部分 provider 不支持 tool_choice]** → 通过 fallback 到 `safe_parse_json` 缓解。可以加 error 日志区分两条路径
- **[Risk] `stages` 字段类型 `list[GrowthStageCreate]` 是嵌套 Pydantic model]** → `with_structured_output` 支持嵌套 schema，spike 已验证 `list[dict]` 可转换。需确认嵌套 Pydantic model 也支持
- **[Trade-off] 增加了一次 Function Calling 的 token 开销]** → tool_choice 会在请求中附加 schema 定义，增加 input token。但消除了因格式错误导致的重试，总体更省
