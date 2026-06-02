## Context

当前 admin-web 的链路追踪（Trace Monitor）和 Chat Playground 已具备基础功能：
- **Trace Monitor**: 以列表形式展示请求链路，每条记录可展开查看 Gantt 时间线，点击节点弹出 Drawer 展示输入/输出数据。
- **Chat Playground**: 左侧会话列表 + 右侧聊天区域，支持 SSE 流式对话和 Trace 回放。

痛点：
1. Skill 节点的 `output_data` 是纯 JSON 字符串（含转义字符），`reply_preview` 等关键信息可读性差；
2. Trace 列表头部只有总耗时，没有分类汇总（skill/llm/routing 分别耗时），调试时需要手动加总；
3. Playground 始终匿名发消息，无法测试「用户 A 的农场上下文」与「用户 B 的农场上下文」的差异行为。

## Goals / Non-Goals

**Goals:**
- 提升 Skill 输出数据的可读性（结构化渲染 + 一键复制格式化内容）
- 提供一键复制 Trace 耗时分析的能力（按节点类型分类汇总）
- 支持在 Playground 中选择用户身份进行对话测试

**Non-Goals:**
- 不修改 Trace 数据存储格式或后端链路记录逻辑
- 不引入新的 npm 依赖包
- 不改变现有 API 认证流程（JWT Bearer）

## Decisions

### Decision 1: Skill 输出格式化采用「提取 + 折叠」模式

**方案**: 在 `TraceMonitor` 和 `Playground` 的节点详情 Drawer 中，对 `skill_call` 类型节点的 `output_data` 做结构化解析——提取 `reply_preview` 字段作为首屏高亮展示，其余字段折叠在 `<details>` 组件中。

**替代方案**: 在后端返回时直接格式化。不选此方案的原因是：
- 前端格式化零后端改动，风险最小；
- 不同 Skill 的输出结构可能不同，前端可灵活适配；
- 保留原始 JSON 供需要时查看。

### Decision 2: 耗时分析在前端基于 timeline 数据实时计算

**方案**: 点击「复制耗时」时，遍历该 trace 的 `timeline.rounds[].nodes[]`，按 `node_type` 分组累加 `duration_ms`，生成 Markdown 表格后写入剪贴板。

**替代方案**: 后端新增汇总接口。不选此方案的原因是：
- timeline 数据已在展开时加载到前端，无需额外请求；
- 纯计算逻辑简单，前端处理足够；
- 避免为调试工具增加后端负担。

### Decision 3: Playground 用户选择通过 `user_id` query param 传递

**方案**: `agent_chat_stream` 接口增加可选 `user_id` 参数，前端选中用户后通过 query param 或 body 字段传递。Agent 侧根据 `user_id` 加载对应用户上下文。

**替代方案**: 通过 Header 传递模拟用户。不选此方案的原因是：
- query param / body 与现有参数传递方式一致；
- Header 传递容易被中间件误处理；
- 与现有 `session_id` 参数风格统一。

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|---------|
| Skill 输出结构不统一导致格式化失败 | 增加 try/catch，解析失败时回退到原始 JSON 展示 |
| 用户列表接口未暴露给 admin-web | 检查 `admin_users.py` 的 `list_users` 是否已有对应前端 API 封装，如无则补充 |
| Playground 指定用户后可能影响会话持久化逻辑 | `user_id` 设为可选参数，不传时保持现有匿名行为，确保向后兼容 |
| 剪贴板 API 在部分浏览器受限 | 使用 `navigator.clipboard.writeText`，失败时通过 `message.error` 提示用户 |

## Migration Plan

无需迁移。本次为纯新增功能，所有改动均为增量：
1. 前端组件增强（无破坏性变更）
2. 后端接口增加可选参数（向后兼容）
3. 无数据库迁移

## Open Questions

- `agent_chat_stream` 当前是否已支持 `user_id` 参数？如不支持，需在后端增加该参数的解析和上下文注入逻辑。
- `list_users` 接口是否已在 admin-web 的 API 层暴露？如没有，需补充对应的 TypeScript 类型和请求函数。
