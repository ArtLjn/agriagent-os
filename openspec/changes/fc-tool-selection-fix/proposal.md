## Why

FC 迁移后，qwen3.6-flash 的 tool selection 能力不足，导致明确的 skill 请求（如"我的余额"、"帮我创建春茬种植西瓜"）直接文本回复而不触发 tool call，skills=[]。迁移前 skillify 预路由通过关键词匹配能可靠命中这些场景，迁移后出现功能性回归。

## What Changes

- 优化所有 Python Skill 的 `description` 字段，覆盖更多口语化触发词和用户意图描述
- 在 system prompt（`base.j2`）的工具调用规则中注入可用工具名称与用途映射表
- 优化 `description` 格式，从小模型角度提炼关键信息（意图→动作→参数）

## Capabilities

### New Capabilities

- `tool-selection-optimization`: 优化 tool description 和 system prompt，提升小模型（qwen3.6-flash 等）的 Function Calling tool selection 准确率

### Modified Capabilities

- `llm-tool-calling`: tool description 格式从"功能说明+触发词列表"优化为"意图场景描述"格式，system prompt 新增可用工具映射表

## Impact

- `backend/app/agent/skills/*/scripts/main.py` — 所有 Python Skill 的 `description` 属性
- `backend/prompts/base.j2` — system prompt 工具调用规则部分
- `backend/tests/skills/` — 各 skill 的 description 测试需同步更新
