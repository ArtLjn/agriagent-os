## 1. 依赖安装与数据库加固

- [ ] 1.1 安装 `PyJWT`、`passlib[bcrypt]` 依赖，更新 requirements.txt
- [ ] 1.2 修改 `database.py`，连接时执行 PRAGMA（WAL、foreign_keys=ON、busy_timeout=5000）
- [ ] 1.3 编写 `scripts/backup.sh` SQLite 在线热备脚本，crontab 配置每小时执行
- [ ] 1.4 测试：验证 WAL 模式生效，外键约束生效

## 2. 用户模型与认证

- [ ] 2.1 创建 `app/models/user.py`（User 模型：uuid 主键、phone、password_hash、nickname、avatar_url、role、status）+ UserOAuth 模型（预留）
- [ ] 2.2 创建 `app/schemas/auth.py`（RegisterRequest、LoginRequest、UserResponse、TokenResponse）
- [ ] 2.3 创建 `app/core/security.py`（JWT 签发/验证、bcrypt 哈希/校验）
- [ ] 2.4 创建 `app/services/auth_service.py`（register、login、verify_token）
- [ ] 2.5 创建 `app/api/auth.py`（POST /auth/register、POST /auth/login、GET /auth/me、PUT /auth/me）
- [ ] 2.6 修改 `app/api/deps.py`：实现三层权限依赖链
  - Layer 1: `get_current_user` — 从 JWT 解析 user_id → 查询 User → 校验 status=="active"
  - Layer 2: `get_current_farm` — User → Farm(user_id=user.id) 查询
  - Layer 3a: `verify_resource_owner(resource_farm_id, current_farm)` — 资源归属校验
  - Layer 3b: `require_admin` — 角色校验（user.role == "admin"）
- [ ] 2.7 测试：注册、登录、token 校验、重复手机号、密码错误、token 过期、用户禁用
- [ ] 2.8 测试：三层依赖链 — 无 token 401、token 过期 401、用户禁用 401、无农场 404、资源不属于当前用户 403、非管理员访问管理接口 403

## 3. farms 表重构

- [ ] 3.1 修改 `app/models/farm.py`：删除 owner_name/display_name，新增 user_id FK（UNIQUE），主键改为 UUID
- [ ] 3.2 更新 `app/models/__init__.py` 导出
- [ ] 3.3 修改 `conftest.py` clean_db fixture：创建 User 后创建 Farm（user_id 关联）
- [ ] 3.4 修改所有现有测试：适配新的 User + Farm 初始化模式
- [ ] 3.5 编写数据迁移脚本 `scripts/migrate_v2.py`：将 farms(1) 的 owner_name → users 表，生成 UUID，关联 user_id

## 4. conversation_messages 增强

- [ ] 4.1 修改 `app/models/conversation.py`：conversations 新增 user_id 字段，conversation_messages 新增 meta Text 字段（JSON）
- [ ] 4.2 修改 `conversation_service.py`：save_message 时支持传入 meta JSON
- [ ] 4.3 修改 `agent_service.py`：保存 assistant 消息时附带 meta（token_usage、latency_ms）
- [ ] 4.4 修改 `app/api/agent.py`：会话相关接口使用 `verify_resource_owner` 校验 conversation 归属当前 farm
- [ ] 4.5 测试：meta 字段存取验证，conversation 关联 user_id，跨用户访问会话返回 403

## 5. feedback_records 新增

- [ ] 5.1 创建 `app/models/feedback.py`（FeedbackRecord：user_id、conversation_message_id、rating、correction）
- [ ] 5.2 创建 `app/schemas/feedback.py`（FeedbackRequest、FeedbackResponse）
- [ ] 5.3 创建 `app/services/feedback_service.py`（submit_feedback、get_feedback_stats）
- [ ] 5.4 创建 `app/api/feedback.py`（POST /agent/feedback、GET /agent/feedback/stats）
  - POST /agent/feedback 使用 `verify_resource_owner` 校验 message 归属当前 farm
- [ ] 5.5 创建 `GET /admin/training-data` 接口：使用 `require_admin` 依赖，导出带评价的 JSONL 训练数据
- [ ] 5.6 测试：正面/负面评价、重复评价覆盖、权限校验（非管理员 403）、跨用户反馈 403、JSONL 导出格式

## 6. agent_records 合并

- [ ] 6.1 创建 `app/models/agent_record.py`（AgentRecord：合并 advice_records + report_records，新增 user_id、conversation_id、meta）
- [ ] 6.2 修改 `agent_service.py`：所有写 advice/report 的地方改用 AgentRecord
- [ ] 6.3 修改 `api/agent.py`：历史查询接口适配 AgentRecord
- [ ] 6.4 删除 `app/models/agent.py`（AdviceRecord、ReportRecord）
- [ ] 6.5 编写迁移脚本：将 advice_records 和 report_records 数据迁移到 agent_records
- [ ] 6.6 测试：历史查询、日报缓存、报告生成功能正常

## 7. trace_records 增强

- [ ] 7.1 修改 `app/models/trace.py`：新增 conversation_message_id 字段（可空 FK）
- [ ] 7.2 修改 `trace_collector.py`：record 方法支持传入 conversation_message_id
- [ ] 7.3 测试：trace 与对话链关联验证

## 8. 全局消除 farm_id 硬编码

- [ ] 8.1 修改 `app/agents/graph.py`：`_llm_node` 和 `_parallel_tool_node` 从 state["farm_id"] 读取（不再硬编码 1）
- [ ] 8.2 修改 `app/agents/advisor.py`：invoke_advisor/stream_advisor 传递 farm_id 到 graph state
- [ ] 8.3 修改 `app/services/farm_context_service.py`：build_summary 使用动态 farm_id，display_name 改为从 users.nickname 获取
- [ ] 8.4 修改 `app/services/quota_service.py`：check_quota 使用动态 farm_id
- [ ] 8.5 全局搜索 `farm_id=1` 和 `Farm.id == 1`，逐一修复
- [ ] 8.6 确认所有接口使用 `Depends(get_current_farm)` 注入 farm 对象，不直接查 farm_id=1
- [ ] 8.7 测试：确认所有接口使用认证用户的 farm_id，多用户隔离验证

## 9. 删除废弃表

- [ ] 9.1 确认 `agent_traces` 表无代码引用
- [ ] 9.2 在迁移脚本中 DROP TABLE agent_traces

## 10. 端到端验证

- [ ] 10.1 测试：注册新用户 → 登录 → 聊天 → 查看历史 → 提交反馈 → 导出训练数据
- [ ] 10.2 测试：多用户隔离（用户 A 看不到用户 B 的数据，访问对方资源返回 403）
- [ ] 10.3 测试：迁移脚本 dry-run 验证现有数据无损
- [ ] 10.4 运行全量测试 + ruff lint
