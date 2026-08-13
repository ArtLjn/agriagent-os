# farm-manager v2

Harness Engineering 实现：业务和 Agent 拆成两个独立项目。Business 在同一端口提供 MySQL-backed REST API 和 MCP（Streamable HTTP），Agent 通过 MCP 调用业务能力。

## 目录结构

```
v2/
├── pyproject.toml          # uv workspace
├── providers.json          # LLM provider 配置（OpenAI 兼容）
├── business/               # MCP Server 子项目
│   ├── server.py           # FastAPI + FastMCP 双协议入口
│   ├── api/                # REST API（/api/v2）
│   ├── tools/              # MCP tool 定义（每个 domain 一个文件）
│   ├── services/           # 业务逻辑
│   └── scripts/            # 本地验收脚本
└── agent/                  # MCP Client 子项目
    ├── main.py             # FastAPI + /chat SSE + /approve
    ├── react.py            # ReAct loop 核心（Turn 贯穿）
    ├── context.py          # LLM messages 组装
    ├── hitl.py             # 写操作闸门
    ├── memory.py           # 短期 + JSON 长期记忆
    ├── sse.py              # SSE 事件 + middleware chain
    ├── llm.py              # LLM 客户端
    └── static/index.html   # 单文件 Web UI
```

## 设计原则

1. **Vertical Slice + Capability Pin** — pipeline 是主叙事，每个节点对应一个文件
2. **Turn 贯穿** — 所有节点接收同一个 `Turn` 对象，`(Turn) -> Turn` 纯函数
3. **协议兼容优先** — REST 与 MCP 共用同一进程和业务服务，保留 Agent 的 `/mcp` 连接入口

## 与旧 backend 的关系

旧 `archive/backend/` 是工业级实现，作为业务参考。v2 是从零开始的最简版本，不复用旧代码，但保留 skill → MCP tool 的改造思路。

## 运行

```bash
cd v2
uv sync                                  # 装齐所有依赖

# Business 必须配置 MySQL 和 JWT 密钥（JWT_SECRET 至少 32 字节）
export DATABASE__URL='mysql+pymysql://USER:PASSWORD@HOST:3306/farm_manager?charset=utf8mb4'
export JWT_SECRET='请替换为随机的高强度密钥'
export AGENT_SERVICE_TOKEN='请替换为 Agent 到 Business 的服务凭证'
export AGENT_DELEGATION_SECRET='请替换为 Agent/Business 委托凭证密钥'

# Terminal 1：启动 business（MCP Server）
uv run --package farm-manager-business python -m business.server

# Terminal 2：启动 agent（FastAPI + SSE）
uv run --package farm-manager-agent python -m agent.main

# 浏览器打开 http://127.0.0.1:8000
```

Business REST 基础路径是 `http://127.0.0.1:9876/api/v2`，MCP 地址保持为 `http://127.0.0.1:9876/mcp`。启动 Business 后，可以使用只读批量验收脚本：

```bash
BUSINESS_PHONE='+8613800000000' \
BUSINESS_PASSWORD='your-password' \
bash v2/business/scripts/test_rest_api.sh
```

已有 JWT 时可直接设置 `BUSINESS_TOKEN`，脚本不会输出令牌或密码。

## 阅读路线

1. `business/server.py` → 看 MCP Server 怎么搭
2. `business/tools/` → 看现有 skill 如何改造为 MCP tool
3. `agent/main.py` → 看入口和 SSE endpoint
4. `agent/react.py` → 看 Turn 如何流转 ReAct loop
5. `agent/context.py` → 看 LLM 上下文怎么拼
6. `agent/hitl.py` → 看闸门怎么拦写操作
7. `agent/memory.py` → 看跨会话状态
