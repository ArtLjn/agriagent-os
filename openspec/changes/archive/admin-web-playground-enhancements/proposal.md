## Why

admin-web 的链路追踪（Trace Monitor）和 Chat Playground 是日常调试 Agent 行为的核心工具，但当前存在三个体验痛点：
1. Skill 执行节点的输出数据以原始 JSON 展示，关键字段（如 `reply_preview`）被淹没在转义字符中，可读性差；
2. Trace 列表缺少一键复制耗时分析的能力，手动汇总各节点耗时效率低下；
3. Chat Playground 无法模拟特定用户身份进行测试，难以验证用户上下文注入的效果。

## What Changes

1. **Skill 输出格式化**：在 Trace 节点详情 Drawer 中，对 `skill_call` 类型节点的 `output_data` 增加结构化渲染——提取并高亮 `reply_preview` 字段，折叠其余原始 JSON，支持一键复制格式化内容。
2. **复制详细耗时按钮**：在 Trace 列表的每条记录头部（展开/收起行）增加一个「复制耗时」按钮，点击后将该 trace 的各类型节点耗时（skill 耗时、llm 耗时、路由耗时等）汇总为 Markdown 表格格式写入剪贴板。
3. **Playground 用户选择器**：在 Chat Playground 的配置栏增加用户下拉选择框，调用 `/api/admin/users` 获取用户列表，选中后发送消息时携带 `user_id` 参数，使 Agent 按该用户的农场上下文和偏好进行回复。

## Capabilities

### New Capabilities
- `trace-skill-output-formatter`: Trace 节点详情中 Skill 输出的结构化格式化渲染
- `trace-copy-timing-report`: Trace 列表一键复制耗时分析报告
- `playground-user-selector`: Chat Playground 用户身份模拟选择器

### Modified Capabilities
- (none — 本次为纯前端体验增强，不改动现有 API 契约)

## Impact

- **admin-web**: `pages/TraceMonitor/index.tsx`、`components/GanttTimeline/index.tsx`、`pages/Playground/index.tsx`、`api/admin.ts`
- **backend**: `api/agent.py`（`agent_chat_stream` 增加可选 `user_id` 参数）
- **依赖**: 新增前端 `antd` 组件使用（`Select`、`Dropdown` 等），无新 npm 包引入
