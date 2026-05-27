## Context

当前系统以 `farms` 表作为顶层实体，farm_id=1 硬编码贯穿全栈。`farms` 同时承载用户信息（owner_name、display_name）、农场信息（name、location）和 AI 偏好，职责混乱。系统没有认证体系，任何请求都默认访问 farm_id=1。

服务器为 2H 4G（Ubuntu 22.04），SQLite 作为唯一数据库。经评估，MySQL 在 2G 内存机器上会占用 300-500MB，而本系统的写入瓶颈在 LLM API 调用（2-10s/次），数据库仅需 ~2-8 次/秒写入，SQLite WAL 模式完全胜任。

当前已实现 conversation_messages 多轮对话，但缺少用户反馈收集机制，无法为后续 RLHF 自学习提供标注数据。

## Goals / Non-Goals

**Goals:**
- 引入独立用户表，支持手机号 + 密码注册登录
- 预留 OAuth 绑定能力，等营业执照后无缝接入
- farms 回归纯粹的农场实体，通过 user_id 关联用户
- 收集用户对 AI 回复的反馈，建立自学习数据基础
- 增强 conversation_messages 存储 tool call 等元数据
- SQLite 开启 WAL 模式 + 定时备份，保障数据安全
- 消除 farm_id=1 硬编码，从认证链路动态获取

**Non-Goals:**
- 不做短信验证码（等企业认证后接入）
- 不做 OAuth 登录（表结构预留，逻辑不实现）
- 不做多租户权限隔离（当前所有用户为同角色）
- 不迁移到 MySQL/PostgreSQL（SQLite 够用）
- 不做用户间数据隔离之外的 RBAC

## Decisions

### D1: 手机号 + 密码，不做短信验证码

**选择：** 用户注册时输入手机号和密码，后端校验手机号格式、密码强度（≥8 位），bcrypt 哈希存储。

**备选方案：**
- A) 短信验证码 → 需要企业认证 + 阿里云短信服务，个人开发者无法获取
- B) 邮箱注册 → 农业场景用户更熟悉手机号
- C) 用户名 + 密码 → 手机号天然唯一，且方便后续短信通知

**理由：** 最小成本实现认证。手机号格式校验即可防止明显错误输入。

### D2: JWT token 认证 + 统一权限过滤器

**选择：** 登录成功后签发 JWT（payload 含 user_id），前端每次请求通过 Authorization: Bearer <token> 携带。后端通过 FastAPI 依赖链实现三层权限过滤器。

**备选方案：**
- A) Session + Cookie → 需要 Redis/内存存储 session，增加复杂度
- B) API Key → 无过期机制，不适合用户认证
- C) 每个接口手动校验 → 容易遗漏，维护成本高

**理由：** JWT 无状态，依赖链自动注入，新增接口只需加 Depends 即可。

**三层过滤器设计：**

```
Layer 1: get_current_user     — JWT → User，失败 401
Layer 2: get_current_farm     — User → Farm(user_id=user.id)，失败 404
Layer 3a: verify_resource_owner — 资源型接口校验归属，失败 403
Layer 3b: require_admin       — 管理接口校验角色，失败 403
```

**接口分类与依赖：**

| 接口类型 | 依赖链 | 示例 |
|---------|--------|------|
| 公开接口 | 无依赖 | /auth/register, /health |
| 普通业务 | user → farm | /agent/chat, /agent/daily |
| 资源访问 | user → farm → verify_owner | /conversations/{id}/messages |
| 管理接口 | require_admin | /admin/training-data |

**归属校验核心原则：** 所有"按标识（ID/session_id）访问资源"的接口，必须验证该资源属于当前用户的 farm。通过 `verify_resource_owner(resource_farm_id, current_farm)` 统一处理。

### D3: 一对一用户-农场关系

**选择：** 当前阶段一个用户只能有一个农场（users 1:1 farms），farms.user_id UNIQUE。

**备选方案：**
- A) 一对多（一个用户管理多个农场）→ 农业场景暂无此需求，增加前端复杂度
- B) 多对多（用户协作管理农场）→ 需要 role 权限表，过度设计

**理由：** 注册时自动创建默认农场，用户无需理解"农场"概念。未来如需多农场，改 UNIQUE 约束即可。

### D4: 合并 advice_records + report_records → agent_records

**选择：** 合并为 `agent_records`（id, farm_id, user_id, conversation_id, record_type, content, meta JSON, created_at），record_type 区分 chat/daily/report。

**备选方案：**
- A) 保持两张表 → 结构雷同，维护成本高
- B) 只保留 advice_records，加 report 类型 → 表名不直观

**理由：** 统一管理所有 AI 输出记录，方便按 user_id 查询用户历史。meta JSON 留扩展空间。

### D5: feedback_records 独立表，关联 conversation_message

**选择：** `feedback_records`（id, user_id, conversation_message_id, rating, correction, created_at），rating 为枚举（good/bad）。

**理由：** 与 conversation_messages 解耦，一条消息可以有多次反馈（未来可能），独立查询效率高。

### D6: conversation_messages.meta JSON 字段

**选择：** 新增 `meta Text` 字段，存储 JSON 格式的元数据：tool_calls（LLM 决定调用的工具）、token_usage（本轮 token 消耗）、latency_ms（响应延迟）。

**理由：** 这些字段的 schema 未来会演进（加 embedding、加 sentiment 等），SQLite 的 json_extract() 可以对 JSON 内部字段建索引，灵活性接近 MongoDB。

### D7: 主键策略 — users/farms 用 UUID，业务表保留自增 ID

**选择：** `users` 和 `farms` 表用 UUID v4 作为主键（String(36)），防止 ID 枚举攻击和跨租户猜测。其他业务表（crop_cycles、cost_records 等）保留 Integer 自增主键，通过 farm_id FK 隔离。

**备选方案：**
- A) 全部用 UUID → 聚集索引效率低（SQLite B-tree 插入随机），日志类表无必要
- B) 全部用自增 ID → 多租户场景下用户可通过 /farms/2 猜测其他农场
- C) 外部暴露 UUID，内部用自增 ID → 双主键维护成本高

**理由：** 只有"外部可访问的顶层实体"需要 UUID 防枚举。内部业务表通过 farm_id FK 已经隔离，自增 ID 效率更高。conversation.session_id 已经是 UUID。

### D8: trace_records 分环境策略

**选择：** config.yaml 新增 `trace.mode`（dev/prod），prod 阶段保留 trace 但降低精度。input_data/output_data 截断到 200 字符，保留天数延长到 90 天。

**dev 模式：** 全量记录，input/output 完整保存，7 天自动清理。
**prod 模式：** 摘要记录，input/output 截断 200 字符，90 天自动清理。

**保留 trace 在 prod 的理由：**
- Skill 调用成功率监控（天气接口挂了能发现）
- LLM 响应延迟趋势（API 变慢能发现）
- Token 成本追踪（token_daily_stats 的数据来源）
- 用户反馈"答错了"时可回溯定位
- 错误告警（skill 失败率突增）

**存储估算：** prod 截断后每条 trace ≈ 500 字节，4 用户一年 ≈ 44 MB，完全可控。

### D9: SQLite WAL 模式 + 备份脚本

**选择：** 连接时执行 PRAGMA 配置，cron 每小时热备。

```sql
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA foreign_keys=ON;
PRAGMA busy_timeout=5000;
```

**理由：** WAL 模式下读写不互阻塞，synchronous=NORMAL 在 WAL 模式下安全且高性能，busy_timeout=5000ms 防止偶发写锁超时。

## Risks / Trade-offs

- **[迁移风险]** 现有数据需要迁移（farms(1) 的 owner_name → users 表），需要离线迁移脚本。→ 迁移脚本加 dry-run 模式，先验证再执行
- **[JWT 无刷新机制]** token 过期后用户需重新登录。→ token 有效期设 7 天，后续加 refresh token
- **[farm_id=1 清除范围大]** graph.py、tool_node、多个 service 都有硬编码，遗漏会导致跨租户数据泄漏。→ 全局 grep farm_id=1 逐一修复，测试覆盖
- **[SQLite 单写瓶颈]** 50+ 并发用户时写入可能排队。→ 当前用户规模远未触及，达到 100 DAU 时再评估 MySQL
- **[OAuth 预留成本]** user_oauth 表先建不用，增加迁移复杂度。→ 表结构极简（5 个字段），维护成本可忽略
