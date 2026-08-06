# farm-manager v2

最简 Harness Engineering 实现：业务和 Agent 拆成两个独立项目，通过 MCP（Streamable HTTP）通信。

## 目录结构

```
v2/
├── pyproject.toml          # uv workspace
├── providers.json          # LLM provider 配置（OpenAI 兼容）
├── business/               # MCP Server 子项目
│   ├── server.py           # FastMCP 实例入口
│   ├── tools/              # MCP tool 定义（每个 domain 一个文件）
│   ├── services/           # 业务逻辑（操作 data/ JSON）
│   └── data/               # JSON 文件持久化
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
3. **最简实现优先** — 单文件 < 200 行，JSON 持久化，零额外依赖

## 与旧 backend 的关系

旧 `archive/backend/` 是工业级实现，作为业务参考。v2 是从零开始的最简版本，不复用旧代码，但保留 skill → MCP tool 的改造思路。

## 运行

```bash
cd v2
uv sync                                  # 装齐所有依赖

# Terminal 1：启动 business（MCP Server）
uv run --package farm-manager-business python -m business.server

# Terminal 2：启动 agent（FastAPI + SSE）
uv run --package farm-manager-agent python -m agent.main

# 浏览器打开 http://127.0.0.1:8000
```

## 阅读路线

1. `business/server.py` → 看 MCP Server 怎么搭
2. `business/tools/` → 看现有 skill 如何改造为 MCP tool
3. `agent/main.py` → 看入口和 SSE endpoint
4. `agent/react.py` → 看 Turn 如何流转 ReAct loop
5. `agent/context.py` → 看 LLM 上下文怎么拼
6. `agent/hitl.py` → 看闸门怎么拦写操作
7. `agent/memory.py` → 看跨会话状态
