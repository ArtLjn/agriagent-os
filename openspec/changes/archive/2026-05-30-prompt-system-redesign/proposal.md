## Why

当前 `base.j2` 是一个 65 行的单体 prompt，混合了语言规则、角色定义、回复格式、12 条硬编码工具触发规则、农场状态查询指引。工具路由与 `tool_selector.py`（三层过滤）和 `Tool.description`（自动注入）完全重复；三个段落都标注"最高优先级"互相矛盾。Spike 验证已确认：移除全部 12 条工具触发规则后，所有 70 个 prompt/tool/agent 测试通过。现在需要系统性重构 prompt 架构，消除冗余、建立可组合的 snippet 机制。

## What Changes

- **BREAKING**: `base.j2` 拆分为可组合的 snippet 片段，原有单体文件不再直接使用
- 移除 `base.j2` 中的 12 条工具触发规则（Spike 已验证安全）和冗余的农场状态查询段
- 移除三个互相矛盾的"最高优先级"标注，改为 Priority Stack 模式（Safety > Accuracy > Format > Style）
- 新增 `prompts/snippets/` 目录，存放可复用的 prompt 片段（角色定义、语言规则、工具调用护栏等）
- 新增 `PromptComposer` 类，按场景组合 snippet 渲染最终 system prompt
- `cost_parse.j2`、`crop_template_parse.j2`、`cycle_parse.j2` 中重复的语言规则块改为引用 snippet
- 保留 `PromptRegistry` 和 `PromptRenderer`，在其上层增加 Composer 层
- 更新 `test_context_engineering_e2e.py` 中已完成的 Spike 验证测试

## Capabilities

### New Capabilities
- `composable-prompt`: 可组合的 prompt snippet 架构，支持按场景组装 system prompt，snippet 自动去重
- `prompt-priority-stack`: Priority Stack 模式替代多个"最高优先级"标注，明确 Safety > Accuracy > Format > Style 层级

### Modified Capabilities
- `prompt-management`: 更新 spec 以反映 snippet 组合机制，原 base.j2 单体模板拆分为 snippets
- `prompt-template-management`: 模板变量注入机制不变，但渲染流程增加 Composer 组合步骤

## Impact

- `backend/prompts/` — 新增 snippets/ 目录，重构 base.j2，改造各 .j2 模板消除重复
- `backend/app/agent/prompt_composer.py` — 新增 Composer 类
- `backend/app/agent/advisor.py` — 调用方式从 `render_prompt` 改为 `composer.compose`
- `backend/tests/test_context_engineering_e2e.py` — 测试已通过 Spike 更新
- `backend/tests/test_prompt_registry.py` — 可能需适配 Composer 层
