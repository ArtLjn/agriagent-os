# farm-manager v2 设计文档

> 起点：从零重写。旧 `archive/backend/` 仅作业务参考，不复用代码。
> MVP 目标：业务和 Agent 拆为两个独立项目，通过 MCP（Streamable HTTP）通信。

## 1. 整体架构

```
┌──────────────────────────┐         ┌──────────────────────────┐
│  agent (FastAPI + SSE)   │         │  business (MCP Server)   │
│                          │  MCP    │                          │
│  ┌────────────────────┐  │  HTTP   │  ┌────────────────────┐  │
│  │ Web UI (index.html)│  │ ◀─────▶ │  │ FastMCP Server     │  │
│  └────────────────────┘  │         │  │  tools/farm.py     │  │
│  ┌────────────────────┐  │         │  │  tools/weather.py   │  │
│  │ react.py (ReAct)   │  │         │  │  tools/logs.py     │  │
│  │  turn 贯穿         │  │         │  │  tools/cycle.py    │  │
│  └────────────────────┘  │         │  │  tools/...          │  │
│  ┌────────────────────┐  │         │  └────────────────────┘  │
│  │ skills/            │  │         │  ┌────────────────────┐  │
│  │  ├─ mcp skills/    │──┼─────────┼─▶│  services/         │  │
│  │  │   (调 business) │  │         │  │  farm_service      │  │
│  │  └─ local skills/  │  │         │  │  log_service       │  │
│  │      (本地执行)    │  │         │  │  ...               │  │
│  └────────────────────┘  │         │  └────────────────────┘  │
│  ┌────────────────────┐  │         │  ┌────────────────────┐  │
│  │ memory (JSON)      │  │         │  │ data/ (JSON)       │  │
│  └────────────────────┘  │         │  └────────────────────┘  │
└──────────────────────────┘         └──────────────────────────┘
```

## 2. 设计原则

1. **Vertical Slice + Capability Pin** — pipeline 是主叙事，每个节点对应一个文件
2. **Turn 贯穿** — 所有节点接收同一个 `Turn` 对象，`(Turn) -> Turn` 纯函数
3. **Skill = Tool** — agent 侧不再叫 "skill catalog/router"，统一叫 tool；MCP tool 和 local tool 都是 tool
4. **业务封在 business** — agent 不持有 DB 句柄、不写业务逻辑
5. **最简实现优先** — 单文件 < 200 行，JSON 持久化，零额外依赖

## 3. Skill 标准格式

每个 skill 是一个目录，包含：

```
skills/<skill-name>/
├── skill.md           # 元数据 + 使用说明（LLM 阅读的描述）
└── scripts/
    ├── __init__.py
    └── main.py        # Skill 类实现，统一接口
```

### 3.1 skill.md 格式

```markdown
---
name: <skill_name>                    # snake_case 唯一标识
kind: mcp | local                    # mcp=调业务, local=本地执行
mcp_tool: business.<tool_name>       # kind=mcp 时填写，指向 business MCP tool
risk_level: read | write_confirm | write_high   # HITL 风险等级
description: <一句话描述>
triggers:                            # 触发关键词（仅作文档参考，LLM 自主决策）
  - 关键词1
  - 关键词2
parameters:                          # OpenAI tool schema
  type: object
  properties:
    param1:
      type: string
      description: 参数说明
  required: [param1]
---

# <skill_name>

<详细说明，给 LLM 看的"何时使用/不要使用/参数推断/示例">
```

### 3.2 scripts/main.py 格式

```python
"""<skill_name> skill 实现。"""
from __future__ import annotations
from typing import Any
from agent.skills.base import Skill, SkillResult


class <Name>Skill(Skill):
    """<一句话>"""

    @property
    def name(self) -> str:
        return "<skill_name>"

    @property
    def description(self) -> str:
        return "<描述>"

    @property
    def risk_level(self) -> str:
        return "read"  # 或 write_confirm / write_high

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {...},
            "required": [...],
        }

    async def execute(self, params: dict[str, Any], ctx) -> SkillResult:
        """执行 skill。

        - kind=mcp: 通过 ctx.business_client 调用业务侧 MCP tool
        - kind=local: 直接执行本地逻辑
        """
        # MCP 示例：
        result = await ctx.business_client.call_tool("<mcp_tool_name>", params)
        return SkillResult(data=result)

        # Local 示例：
        # return SkillResult(data={"result": 42})
```

### 3.3 Skill 分类

| kind | 含义 | 示例 | 调用方式 |
|------|------|------|---------|
| `mcp` | 业务能力，封在 business server | farm-status, weather, manage-* | `ctx.business_client.call_tool(...)` |
| `local` | 纯计算或第三方能力，agent 本地执行 | calculate-arithmetic, web-search | 直接函数调用 |

LLM 看来 mcp 和 local 都是 tool，只是底层实现不同。`skill_loader` 合并两类为统一的 OpenAI tools schema。

## 4. 旧 skill → v2 迁移映射

14 个旧 skill 按 kind 分两类：

### 4.1 业务 skill（kind=mcp，迁到 business MCP）

| 旧 skill | v2 business tool | v2 agent skill | risk | 备注 |
|---------|-----------------|---------------|------|------|
| farm-status | `get_farm_status` | skills/farm-status | read | ✅ 已实现 |
| weather | `get_weather` | skills/weather | read | ✅ 已实现 |
| manage-farm-logs (query) | `query_farm_logs` | skills/query-farm-logs | read | ✅ 已实现 |
| manage-farm-logs (create) | `create_farm_log` | skills/create-farm-log | write_confirm | ✅ 已实现 |
| manage-farm-logs (delete) | `delete_farm_log` | skills/delete-farm-log | write_high | ✅ 已实现 |
| manage-crop-cycle | `create_cycle` / `query_cycles` / `update_cycle` / `delete_cycle` / `update_cycle_stage` | skills/manage-crop-cycle | mixed | 拆为多个 tool，cycle_id 必填参数 |
| manage-crop-templates | `list_crop_templates` / `create_crop_template` | skills/manage-crop-templates | mixed | 模板是 read-mostly |
| manage-planting-units | `query_planting_units` / `create_planting_unit` / `update_planting_unit` | skills/manage-planting-units | mixed | 地块/棚管理 |
| manage-workers | `query_workers` / `create_worker` / `update_worker` | skills/manage-workers | mixed | 工人档案 |
| manage-work-orders | `create_work_order` / `query_work_orders` / `update_work_order` | skills/manage-work-orders | mixed | 作业单（核心业务） |
| manage-labor-payment | `record_wage` / `query_unpaid_wages` / `settle_wages` | skills/manage-labor-payment | write_high | 涉及钱，HITL 必加 |
| manage-cost | `create_cost_record` / `query_cost_summary` / `analyze_cost_trend` / `delete_cost_record` | skills/manage-cost | mixed | 财务记账 |
| manage-cost-categories | `list_cost_categories` / `create_cost_category` | skills/manage-cost-categories | mixed | 财务分类 |
| manage-user-settings | `get_user_setting` / `update_user_setting` | skills/manage-user-settings | write_confirm | 用户偏好 |

### 4.2 本地 skill（kind=local，agent 侧直接执行）

| 旧 skill | v2 agent skill | risk | 备注 |
|---------|---------------|------|------|
| calculate-arithmetic | skills/calculate-arithmetic | read | Decimal 安全求值，不走网络 |
| web_search | skills/web-search | read | 第三方搜索 API，agent 本地调 |

### 4.3 不迁移的旧概念

- `app/skills/registry/` (skills.yaml, aliases.yaml, governance.py, loader.py) — 全部废弃。MCP tool 自描述，LLM 自主路由
- `app/skills/metadata.py` (permission/risk/cache 元数据) — 简化为 skill.md 的 `risk_level` 字段
- `app/skills/context.py` (require_farm_context) — 不需要，业务侧 tool 自己持有 farm 上下文
- `app/skills/contracts.py` (SkillResult/Schema) — 简化为 `SkillResult(data: dict)` 一个数据类
- `app/agent/router/` (catalog/classifier/policy/tool_selector) — 全部废弃。ReAct loop 让 LLM 通过 tool description 自主选择

## 5. 模块边界

### 5.1 v2/business/

```
business/
├── server.py          # FastMCP 入口，启动 HTTP transport
├── mcp.py            # 共享 FastMCP 实例
├── tools/            # MCP tool 定义（薄壳，调用 services）
│   ├── farm.py
│   ├── weather.py
│   ├── logs.py
│   ├── cycle.py      # crop cycle 管理
│   ├── work_order.py
│   ├── worker.py
│   ├── wage.py
│   ├── cost.py
│   └── ...
├── services/         # 业务逻辑（操作 data/ JSON）
│   ├── farm_service.py
│   ├── log_service.py
│   ├── cycle_service.py
│   └── ...
└── data/             # JSON 持久化
    ├── farm.json
    ├── logs.json
    ├── cycles.json
    └── ...
```

### 5.2 v2/agent/

```
agent/
├── main.py            # FastAPI: /chat SSE + /approve + /reset
├── react.py           # ReAct loop（Turn 贯穿）
├── turn.py            # Turn 数据结构
├── context.py         # LLM messages 组装
├── hitl.py            # 写操作闸门
├── memory.py          # 短期 + 长期记忆（JSON）
├── sse.py             # SSE 事件类型
├── llm.py             # OpenAI 兼容客户端
├── mcp_client.py      # BusinessClient async wrapper
├── skill_loader.py    # 加载 skills/，组装 LLM tools schema
├── skills/
│   ├── base.py        # Skill 基类 + SkillResult
│   ├── context.py     # SkillContext（business_client + turn）
│   ├── farm-status/
│   │   ├── skill.md
│   │   └── scripts/main.py
│   ├── weather/
│   │   ├── skill.md
│   │   └── scripts/main.py
│   ├── ...（共 16 个 skill 目录）
│   └── calculate-arithmetic/  # local skill
│       ├── skill.md
│       └── scripts/main.py
└── static/
    └── index.html     # Web UI
```

## 6. Skill 调用流程

```
用户消息
    ↓
react.py 启动 Turn
    ↓
skill_loader.load_all() → 返回 [{name, schema, kind, instance}]
    ↓
context.mcp_tools_to_openai(skills) → 组装 LLM tools schema
    ↓
LLM chat(messages, tools) → 返回 tool_calls
    ↓
对每个 tool_call:
    ├─ hitl.gate(skill) → 如写操作，等用户批准
    ├─ skill.execute(params, ctx)
    │    ├─ kind=mcp → ctx.business_client.call_tool(...)
    │    └─ kind=local → 直接函数调用
    └─ 把结果 append 到 turn.messages
    ↓
循环直到 LLM 给出 final_answer
```

## 7. HITL 风险等级

- `read` — 不闸门，直接执行
- `write_confirm` — 闸门一次（创建类操作，如 create_farm_log）
- `write_high` — 闸门 + 二次确认（删除类、涉及钱的操作，如 delete_farm_log, settle_wages）

风险等级写在 skill.md front matter 的 `risk_level` 字段，由 `skill_loader` 解析，`hitl.py` 在执行前检查。

## 8. 与旧 backend 的关系

- `archive/backend/` 保留作为业务参考，不复用代码
- 旧 skill 的业务逻辑（services 部分）参考迁移到 v2/business/services/
- 旧 skill.md 的描述文本可参考改写
- 旧 schema/registry/metadata 抽象全部废弃

## 9. 运行

```bash
cd v2
uv sync                                  # 装齐所有依赖

# Terminal 1：business MCP server
uv run --package farm-manager-business python -m business.server

# Terminal 2：agent FastAPI
uv run --package farm-manager-agent python -m agent.main

# 浏览器打开 http://127.0.0.1:8000
```

## 10. 实施顺序

1. ✅ v2 骨架 + 4 个核心 MCP tool + ReAct + HITL + Web UI（已完成）
2. ⏳ skill 标准格式重构（把现有 mcp_client 调用拆到 skills/）
3. ⏳ 补齐 8 个业务 MCP tool + 对应 skill
4. ⏳ 2 个 local skill（calculator + web-search）
5. ⏳ 端到端验证全部 16 个 skill
