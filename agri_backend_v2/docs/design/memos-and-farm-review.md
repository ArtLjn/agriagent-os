---
status: implemented
last_updated: 2026-10-25
---
# 备忘录与经营盘点

## 范围

用户说“提醒”在本需求中指备忘录。支持创建、标题/正文搜索、编辑、置顶、归档和恢复；不包含定时触发、重复日程、通知发送或后台调度。备忘录与 Agent 长期偏好记忆、正式农事记录相互独立。

## 业务与协议边界

- `businesses/farm/farm_business/models.py` 的 `Memo` 映射 `memos` 表。
- `businesses/farm/farm_business/services/memo_service.py` 统一处理内容校验、身份过滤、幂等创建和编辑。
- `businesses/farm/farm_business/api/memos.py` 暴露 `/api/v2/memos` 的 GET、POST 与 `/{memo_id}` PATCH。
- `businesses/farm/farm_business/tools/memos.py` 通过 MCP 提供相同能力，Agent 从 `businesses/farm/skills/manage-memos/skill.md` 自动加载四个单动作工具。
- `businesses/farm/farm_business/tools/farm_review.py` 提供两个只读聚合工具：`get_farm_review` 和 `get_payment_overview`，各自有独立 skill。
- 新文件分别属于业务服务、REST/MCP 外部协议和 Agent 技能边界；不增加通用仓库、任务队列或调度抽象。

## 权限与一致性

REST 通过 `require_permission` 注入主体，MCP 复用现有鉴权与权限策略。所有备忘录查询和编辑同时约束 farm_id、user_id；两个字段不能由客户端覆盖。只读需要 farm:read，写入需要 farm:write；Agent 写操作使用 write_confirm 审批。

创建要求 client_request_id，Agent 自行生成，不让用户填写。用户/农场/请求键具有数据库唯一约束；相同请求重试返回同一记录，不同正文复用键返回 idempotency_conflict。并发插入使用保存点与唯一约束兜底，更新行使用事务锁。

标题最多 200 字，正文最多 10000 字，空白拒绝；分页最多 100 条。搜索按字面包含匹配，转义百分号和下划线。默认排除归档，置顶优先，其次按更新时间和 ID 倒序。归档可恢复，不物理删除。时间统一存 UTC，接口返回 ISO 8601 偏移。

## 实用技能

- 备忘录：“帮我记一下下次买 20 个滴灌接头”“找一下采购笔记”“把这条置顶”“归档这条备忘录”。
- 农事回顾：“总结最近一周做了什么”。按北京时间、含今天在内的 1–90 天统计；分类数量取全量记录，明细最多 20 条。没有日志不等于没有作业。
- 待结款盘点：“还有哪些钱没结”。应收赊账、应付赊账、未付工资分开呈现，排除已删除和已结清赊账，不自动结算，不将工资重复计入成本。

## Tools 封装入口和调用方式

这些技能采用项目已有的声明式 MCP 封装。`businesses/farm/skills/<目录>/skill.md` 是运行配置和使用说明，实际执行方法在 `agent/domains/harness/tools/base.py` 的 `OperationSkill.execute` / `McpSkill.execute`；不需要为每个工具再添加只做转发的 `scripts/main.py`。只有技能需要额外业务编排时才添加脚本。

| Agent 工具名 | Agent 定义 | Business 可执行方法 |
|---|---|---|
| `query_memos` | `businesses/farm/skills/manage-memos/skill.md` | `businesses/farm/farm_business/tools/memos.py::manage_memos(operation="query")` |
| `create_memo` | 同上 | `manage_memos(operation="create")` |
| `update_memo` | 同上 | `manage_memos(operation="update")` |
| `archive_memo` | 同上 | `manage_memos(operation="archive")` |
| `get_farm_review` | `businesses/farm/skills/farm-review/skill.md` | `businesses/farm/farm_business/tools/farm_review.py::get_farm_review` |
| `get_payment_overview` | `businesses/farm/skills/payment-overview/skill.md` | `businesses/farm/farm_business/tools/farm_review.py::get_payment_overview` |

实际调用链：`SkillLoader → SkillRegistry → Runtime 风险审批 → Skill.execute → SkillContext.call_mcp_tool → BusinessClient → Business MCP 方法 → 业务服务/数据库`。`businesses/farm/farm_business/server.py` 导入两个 tools 模块完成 MCP 注册；Agent 的目录加载器自动发现三个技能目录。Router 选择 `manage_memos` 后会展开四个操作，模型不需要填写内部 `operation`，身份也不能由模型覆盖。

下面是在运行时已有 `registry` 与 `ctx` 时的调用示例。`ctx` 由 Runtime 创建并持有已鉴权的 BusinessClient。写入前必须先走 Runtime 的审批流程，不能从 API 绕过审批直接调用 `execute`；工具执行本身不弹审批。

```python
from uuid import uuid4

# 生成一次后随待审批动作保存；重试直接复用原 arguments。
arguments = {
    "title": "采购清单",
    "content": "下次买 20 个滴灌接头",
    "client_request_id": uuid4().hex,
}
# 以下发生在 Runtime 批准该动作之后。
result = await registry.require("create_memo").execute(arguments, ctx)
if result.ok:
    memo_id = result.data["id"]

query = await registry.require("query_memos").execute({"keyword": "滴灌接头"}, ctx)
review = await registry.require("get_farm_review").execute({"days": 7}, ctx)
payments = await registry.require("get_payment_overview").execute({}, ctx)
```

编辑至少提供标题、正文、置顶状态中的一项；`pinned=false` 是有效修改。归档与恢复使用同一个工具，分别传 `archived=true` / `false`。完整参数、返回字段与错误处理见各技能文件的“工具使用方法”。

## 发布和回滚

1. 在 `agri_backend_v2` 下使用 Business 实际运行环境执行 `python -B -m farm_business.scripts.migrate_memos` 只读检查；缺表时执行 `python -B -m farm_business.scripts.migrate_memos --apply`。脚本仅执行 `businesses/farm/farm_business/migrations/20261023_memos_up.sql`，已有表只校验列、主键、幂等唯一约束、列表索引和关联外键，不覆盖数据。结构不兼容时中止，由管理员审核修复。
2. `deploy/server-sync.sh` 在服务切换前自动执行该专项增量迁移，沿用配置及 `.env` 环境覆盖，失败时回滚代码并停止切换。MySQL 命名锁串行化重复部署；DDL 自动提交，代码回滚不删除新增表。新库初始化基线 `businesses/farm/sql/farm_manager.sql` 同步包含相同 DDL。
3. 重启 Agent 使新增 skill 被目录加载器发现。
4. 应用启动不自动迁移，迁移属于发布步骤。2026-10-23 已在本地与线上共用的 farm_manager 数据库补建缺失表，重复执行与结构校验通过；服务器旧代码仍需正常发布，建表不等于前后端已更新。
5. 回滚先停止相关流量并备份备忘录，撤回服务版本；down SQL 会删除表，仅在确认后执行。

## 验证

`tests/test_memos.py` 覆盖数据库持久化、重复请求、跨用户/农场隔离、搜索转义、置顶归档恢复、输入边界、REST 权限、MCP 分发、skill 风险等级，以及回顾全量计数与收付款方向隔离。SQLite 测试不替代生产 MySQL 并发锁和迁移验收。

接入回归从真实 SkillRegistry 加载技能，经 SkillContext、BusinessClient 和进程内 FastMCP 传输执行到数据库，覆盖创建重放、编辑、归档恢复、业务错误传播和两个盘点工具。测试仅替换鉴权主体与数据库，不调用外部模型，也不验证线上 HTTP 传输；缺参测试验证在 MCP 调用前阻止无效写入。

接口文档见 `../reference/api-spec.yaml`，包含本次备忘录与 Agent 管理接口；其余端点以运行服务 `/openapi.json` 为准。

## 管理端与错误处理

侧栏“业务调试 → 提醒 / 备忘录”（`/memos`）和业务调试中心的同名页签（`/operations?tab=memos`）共用 `pages/Memos/index.tsx` 的 MemoPanel。面板提供搜索、分页、新建、编辑、置顶、归档、恢复和错误重试。只读取当前登录用户，Playground 模拟用户不会与管理员记录混在一起。创建网络失败保留输入和请求键；换筛选取消旧请求，避免迟到响应覆盖当前结果。

`src/api/memos.ts` 封装 REST 请求和类型；新页面独立于已超长的 Operations 文件，并由独立路由与页签共同使用。`businesses/farm/farm_business/scripts/migrate_memos.py` 是发布脚本和运维 CLI 共用的数据库迁移边界，不属于请求时业务逻辑，禁止应用启动自动建表。

REST 数据库异常返回 503，MCP 返回带 error/code/message/meta 的失败结果。缺表为 `memo_schema_not_ready`，其他存储失败为 `memo_storage_unavailable`；用户能看到修复提示，响应和业务日志均不包含 SQL、绑定参数或备忘录正文。

新增验证：缺表下 REST 三个端点和 MCP 四种操作均不会报告成功；模拟 MySQL 1146 和断连异常检查脱敏；迁移覆盖缺表、重复执行、结构不完整、锁超时和失败释放锁。前端覆盖筛选、幂等重试、编辑、置顶、归档恢复、分页收缩和迟到响应。
