## Why

`safe_parse_json()` 依赖 Markdown 代码块提取 + 手动括号修复，无法处理 LLM 在 JSON 前后添加自然语言的情况（如 "好的，以下是结果：{...}"）。日志中已有 14 次 `AI 返回数据校验失败` + 7 次 `JSON 解析失败`，都是因为 LLM 返回了非 JSON 文本。

LangChain 的 `with_structured_output()` 通过 Function Calling 强制模型输出符合 Pydantic schema 的结构化 JSON，从根本上消除解析失败。

## What Changes

- `/crops/templates/parse`、`/cycles/parse`、`/costs/parse` 三个解析端点从 `get_llm() → ainvoke → safe_parse_json → model_validate` 改为 `get_llm().with_structured_output(Schema) → ainvoke` 直接获得 Pydantic 对象
- 删除三个端点中的 `safe_parse_json` 调用和 `ValueError` catch
- 保留 `safe_parse_json` 和 `json_repair.py`（每日建议等其他场景仍在用）
- 各端点 prompt 模板去掉 "只返回 JSON" 等格式约束说明（不再需要）

## Capabilities

### New Capabilities

- `structured-output-parsing`: 使用 LangChain `with_structured_output()` 替代手动 JSON 解析，确保 LLM 输出结构化数据

### Modified Capabilities

（无已有 spec 需要修改）

## Impact

- **代码**: `backend/app/api/crop.py`、`backend/app/api/cycle.py`、`backend/app/api/cost.py` — 解析逻辑简化
- **Prompt**: `crop_template_parse.j2`、`cycle_parse.j2`、`cost_parse.j2` — 去掉 JSON 格式约束
- **依赖**: 依赖 `langchain_openai.ChatOpenAI.with_structured_output()`，要求 LLM provider 支持 Function Calling / tool_choice
- **API 行为**: 无 breaking change，接口契约不变（请求/响应 schema 不变）
- **每日建议不走此方案**: `agent_service.py` 的建议解析走 LangGraph Agent 图，不适合改
