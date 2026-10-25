# farm-manager v2

Harness Engineering 实现：业务和 Agent 拆成两个独立项目。Business 在同一端口提供 MySQL-backed REST API 和 MCP（Streamable HTTP），Agent 通过 MCP 调用业务能力。

## 目录结构

```
v2/
├── pyproject.toml          # uv workspace
├── providers.json          # LLM provider 配置（OpenAI 兼容）
├── businesses/
│   └── farm/               # 农场业务项目（自包含）
│       ├── pyproject.toml
│       ├── plugin.yaml     # Agent 插件清单
│       ├── prompts/        # 业务 system prompt
│       ├── skills/         # 16 个业务 skill
│       ├── sql/            # 业务 DDL
│       └── farm_business/  # 业务服务：REST + MCP
│           ├── server.py
│           ├── api/ tools/ services/ migrations/ scripts/
│           └── ...
├── shared/                 # 跨业务共享包（roles、API 响应、地区数据）
├── tests/                  # Agent + 跨边界测试
└── agent/                  # 通用 Agent 内核
    ├── api/ application/ bootstrap/
    ├── domains/harness/    # runtime/context/memory/trace/router/tools
    ├── platforms/          # llm/mcp/persistence
    ├── prompts/            # 平台提示词
    └── tools/              # 通用能力：算术、联网搜索
```

## 业务项目

`agent/` 不包含农场业务资源。业务技能、system prompt 和服务实现都在
`businesses/farm/`，`agent/config.yaml` 通过 `plugins.active` 选择唯一启用的业务：

```yaml
plugins:
  root: "businesses"  # 相对 agri_backend_v2 根目录
  active: "farm"      # 省略时要求恰好一个 plugin.yaml
```

新增业务时创建 `businesses/<name>/`（`plugin.yaml`、`prompts/`、`skills/`、
`<name>_business/`），加入 workspace，切换 `plugins.active` 即可。
当前一次部署只加载一个业务。源码部署会同步整个 `agri_backend_v2/`；
wheel 部署需额外携带 `businesses/`，生产配置或 `PLUGINS__ROOT` /
`PLUGINS__ACTIVE` 需指向实际业务目录。
插件清单、加载链路和空结果策略见 [插件化架构](docs/design/agent-plugin-architecture.md)。

## 设计原则

1. **Vertical Slice + Capability Pin** — pipeline 是主叙事，每个节点对应一个文件
2. **Turn 贯穿** — 所有节点接收同一个 `Turn` 对象，`(Turn) -> Turn` 纯函数
3. **协议兼容优先** — REST 与 MCP 共用同一进程和业务服务，保留 Agent 的 `/mcp` 连接入口

后端 Ruff 目标固定为 Python 3.11，与运行环境和最低支持版本一致，避免继承仓库根目录
的 Python 3.14 目标后生成旧运行环境不支持的异常语法。

## 与旧 backend 的关系

旧 `archive/backend/` 是工业级实现，作为业务参考。v2 是从零开始的最简版本，不复用旧代码，但保留 skill → MCP tool 的改造思路。

## 运行

```bash
cd agri_backend_v2
uv sync                                  # 装齐所有依赖

# Business 必须配置 MySQL 和 JWT 密钥（JWT_SECRET 至少 32 字节）
export DATABASE__URL='mysql+pymysql://USER:PASSWORD@HOST:3306/farm_manager?charset=utf8mb4'
export JWT_SECRET='请替换为随机的高强度密钥'
export AGENT_SERVICE_TOKEN='请替换为 Agent 到 Business 的服务凭证'
export AGENT_DELEGATION_SECRET='请替换为 Agent/Business 委托凭证密钥'

# Terminal 1：启动 business（MCP Server）
uv run --package farm-manager-business python -m farm_business.server

# Terminal 2：启动 agent（FastAPI + SSE）
uv run --package farm-manager-agent python -m agent.bootstrap.app

# 也支持直接执行入口文件
# uv run --package farm-manager-agent python agent/bootstrap/app.py

# 浏览器打开 http://127.0.0.1:8000
```

Business REST 基础路径是 `http://127.0.0.1:9876/api/v2`，MCP 地址保持为 `http://127.0.0.1:9876/mcp`。启动 Business 后，可以使用只读批量验收脚本：

```bash
BUSINESS_PHONE='+8613800000000' \
BUSINESS_PASSWORD='your-password' \
bash agri_backend_v2/businesses/farm/farm_business/scripts/test_rest_api.sh
```

已有 JWT 时可直接设置 `BUSINESS_TOKEN`，脚本不会输出令牌或密码。

## 阅读路线

1. `businesses/farm/farm_business/server.py` → 看 MCP Server 怎么搭
2. `businesses/farm/farm_business/tools/` → 看现有 skill 如何改造为 MCP tool
3. `agent/main.py` → 看入口和 SSE endpoint
4. `agent/react.py` → 看 Turn 如何流转 ReAct loop
5. `agent/context.py` → 看 LLM 上下文怎么拼
6. `agent/hitl.py` → 看闸门怎么拦写操作
7. `agent/memory.py` → 看跨会话状态


### 备忘录数据库迁移

新环境使用 `businesses/farm/sql/farm_manager.sql` 初始化。已有环境在当前目录使用 Business 的实际环境变量执行：

```bash
# 默认只检查，不修改数据库。
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m farm_business.scripts.migrate_memos
# 缺表时只创建 memos；重复执行不会覆盖数据。
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m farm_business.scripts.migrate_memos --apply
```

`deploy/server-sync.sh` 已在服务切换前接入迁移，迁移失败中止发布。已有表结构不兼容时需人工审核修复，不能通过删除表解决；代码回滚保留表与数据。管理端入口为“业务调试 → 提醒 / 备忘录”，也可打开 `/operations?tab=memos`。完整边界与验收见 [备忘录设计](docs/design/memos-and-farm-review.md)。
