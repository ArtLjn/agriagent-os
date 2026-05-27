## Why

当前 farms 表同时承担用户、农场、AI 偏好三重职责，没有独立的用户认证体系，所有数据硬编码 farm_id=1。系统无法支持多用户登录，也无法建立用户画像为后续自学习（RLHF）提供数据基础。同时，数据库缺少 WAL 模式和备份策略，生产环境数据安全无保障。

## What Changes

- **新增 `users` 表**：手机号 + 密码注册登录，含 nickname、avatar、role 等用户画像字段
- **新增 `user_oauth` 表**：预留 OAuth 绑定能力（微信/支付宝），等营业执照认证后启用
- **新增 `feedback_records` 表**：用户对 AI 回复的评价（👍/👎/修正回答），为 RLHF 自学习提供标注数据
- **重构 `farms` 表**：删除 owner_name/display_name，新增 user_id FK 指向 users，farms 回归纯粹的"农场"实体
- **增强 `conversation_messages` 表**：新增 `meta` JSON 字段，存储 tool_calls、token_usage 等可变数据
- **增强 `trace_records` 表**：新增 conversation_message_id FK，打通 trace 与对话链
- **合并 `advice_records` + `report_records` → `agent_records`**：结构雷同，统一管理
- **删除 `agent_traces` 表**：代码中无引用，疑似废弃
- **SQLite WAL 模式**：配置 PRAGMA journal_mode=WAL + busy_timeout，确保并发安全
- **定时备份脚本**：在线热备 + 7 天滚动保留
- **全局消除 farm_id=1 硬编码**：graph.py、tool_node 等处从 state 读取 farm_id

## Capabilities

### New Capabilities
- `user-auth`: 用户注册/登录（手机号+密码），JWT token 签发与校验，预留 OAuth 绑定
- `user-profile`: 用户画像管理（昵称、头像、角色），AI 称呼偏好
- `feedback-collection`: AI 回复评价收集（好/坏/修正），为 RLHF 提供标注数据
- `database-hardening`: SQLite WAL 模式配置、外键约束、定时备份脚本

### Modified Capabilities
- `farm-context-injection`: display_name 从 farms 表迁移到 users 表，通过 user_id → users.nickname 获取
- `prompt-template-management`: `<user_context>` 段的 display_name 来源从 Farm 改为 User

## Impact

- **数据库**：新增 3 张表（users、user_oauth、feedback_records），重构 2 张表（farms、conversation_messages），合并 2 张表（→ agent_records），删除 1 张表（agent_traces），增强 1 张表（trace_records）
- **API**：新增注册/登录/用户信息接口；现有接口的 `get_current_farm` 依赖链改为 `get_current_user → get_user_farm`
- **认证**：所有业务接口需从 JWT token 解析 user_id，再通过 user_id 找到 farm_id
- **Agent 层**：graph.py 的 `_llm_node` 和 `_parallel_tool_node` 需从 state 读取 farm_id，消除硬编码
- **迁移**：需要数据迁移脚本将现有 farms(1) 的 owner_name/display_name 迁移到 users 表
- **依赖**：新增 `PyJWT`（或 `python-jose`）+ `passlib[bcrypt]` 依赖
