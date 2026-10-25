---
status: implemented
last_updated: 2026-10-25
---
# Agent 插件化架构

## 背景

`agent/` 的运行时通过 MCP 与业务服务解耦。农场业务资源统一放在
`businesses/farm/`：`skills/` 放 16 个 Agent 技能声明，`prompts/` 放业务人格，
`farm_business/` 放 REST + MCP 服务实现。

本文定义单业务/部署模型下的项目边界：Agent 内核只负责通用能力，业务资源由
`businesses/<name>/` 提供，每个业务项目自包含技能、提示词和服务实现。

## 目标与非目标

目标：

- 业务技能和业务 system prompt 迁出 `agent/`；
- 核心通过 `plugin.yaml` 发现并加载唯一启用的插件；
- 把 Runtime 中唯一的业务特判改为 `skill.md` 声明式策略；
- 迁移前后技能数量、工具顺序、提示词内容和管理端契约保持不变。

非目标：

- 一个进程同时加载多个业务项目；
- `farm_uid` / `farm_id` 租户字段改名；
- 多 MCP server 注册表；
- wheel 打包与业务模板生成脚本（Phase 2）。

## 分层

```text
┌──────────────────────────────┐
│ Agent Core (agent/)          │
│ Runtime / Context / Memory   │
│ Router / Trace / HITL        │
│ 通用工具：算术、联网搜索      │
└──────────────┬───────────────┘
               │ 读取 plugin.yaml
┌──────────────▼───────────────┐
│ Plugin (businesses/farm/)    │
│ 业务技能声明 + 业务人格提示词 │
└──────────────┬───────────────┘
               │ MCP
┌──────────────▼───────────────┐
│ Business Service (farm_business/) │
│ REST + MCP，业务实现与鉴权    │
└──────────────────────────────┘
```

- **Agent Core** 不认识农场、成本、作物等业务词。
- **Plugin** 只提供资源：`skill.md` 元数据、可选的 `scripts/main.py`、system prompt、插件清单。
- **Business Service** 提供 MCP 工具和 REST API，负责真正的业务逻辑和工具级权限校验。

## 完整目录结构

```text
agri_backend_v2/
├── agent/                                  # 通用 Agent 内核：不含农场业务资源
│   ├── api/                                # HTTP/SSE 路由（薄入口）
│   ├── application/
│   │   └── question_recommendations.py     # 使用统一 skill loader
│   ├── bootstrap/
│   │   └── app.py                          # lifespan 增加插件启动校验
│   ├── config.py                           # plugins 配置节
│   ├── config.example.yaml                 # plugins 配置示例
│   ├── plugins.py                          # plugin.yaml 解析与单插件发现
│   ├── domains/harness/
│   │   ├── context/                        # 上下文构建
│   │   ├── control/                        # HITL 审批
│   │   ├── memory/                         # 短期/长期记忆
│   │   ├── observability/                  # trace
│   │   ├── router/                         # 技能路由
│   │   ├── runtime/
│   │   │   └── engine.py                   # 通用声明式策略执行
│   │   ├── state/
│   │   └── tools/
│   │       ├── base.py                     # Skill 基类
│   │       ├── loader.py                   # 核心 + 插件合并加载
│   │       └── registry.py                 # 技能注册与校验
│   ├── platforms/                          # LLM / MCP / Mongo / Redis
│   ├── prompts/                            # 平台提示词（非业务）
│   │   ├── __init__.py
│   │   ├── memory_*.md
│   │   ├── question_recommendations.md
│   │   └── recent_user_statements.md
│   └── tools/                              # 核心通用能力
│       ├── __init__.py
│       ├── calculate-arithmetic/
│       │   ├── skill.md
│       │   └── scripts/main.py
│       └── web-search/
│           ├── skill.md
│           └── scripts/main.py
├── businesses/
│   └── farm/                               # 农场业务项目（自包含）
│       ├── pyproject.toml                  # farm-manager-business
│       ├── plugin.yaml                     # Agent 插件清单
│       ├── prompts/
│       │   └── system.md                   # 业务人格与规则
│       ├── skills/                         # 16 个业务技能
│       │   ├── farm-review/skill.md
│       │   ├── farm-status/skill.md
│       │   ├── location/skill.md
│       │   ├── manage-cost/skill.md
│       │   ├── manage-crop-cycle/skill.md
│       │   ├── manage-crop-templates/skill.md
│       │   ├── manage-debt/skill.md
│       │   ├── manage-farm-logs/skill.md
│       │   ├── manage-memos/skill.md
│       │   ├── manage-planting-plan/skill.md
│       │   ├── manage-planting-units/skill.md
│       │   ├── manage-user-settings/skill.md
│       │   ├── manage-work-orders/skill.md
│       │   ├── manage-workers/skill.md
│       │   ├── payment-overview/skill.md
│       │   └── weather/
│       │       ├── skill.md
│       │       └── scripts/main.py
│       ├── sql/farm_manager.sql            # 业务 DDL
│       └── farm_business/                  # REST + MCP 服务
│           ├── api/
│           ├── tools/
│           ├── services/
│           ├── migrations/
│           ├── scripts/
│           ├── models.py
│           ├── db.py
│           ├── config.py
│           ├── server.py
│           └── mcp_app.py
├── shared/                                 # 跨业务共享包
│   ├── pyproject.toml
│   └── shared/
│       ├── api_response.py
│       ├── roles.py
│       ├── time.py
│       └── location/regions.json
└── tests/                                  # Agent + 跨边界测试
```

### 核心工具与业务工具的划分

| 目录 | 归属 | 工具 |
|---|---|---|
| `agent/tools/` | 核心 | `calculate_arithmetic`、`web_search` |
| `businesses/farm/skills/` | 农场业务项目 | 其余 16 个业务技能 |

这两个核心工具的 `skill.md` 只使用通用场景描述，不包含农业或具体业务词汇；
业务示例和业务实体由业务项目自己的技能或提示词提供。新业务复用 Agent 时，
只需要新增 `businesses/<name>/`，不需要复制这两个通用工具。

## plugin.yaml

```yaml
schema_version: 2
name: farm
display_name: 农场助理
description: 农场经营管理助手
system_prompt: prompts/system.md
skills_dir: skills
```

| 字段 | 必填 | 规则 |
|---|---|---|
| `schema_version` | 是 | 必须为 2 |
| `name` | 是 | 必须与业务目录名一致 |
| `display_name` | 是 | 管理端与日志展示名 |
| `description` | 否 | 业务说明 |
| `system_prompt` | 是 | 相对业务项目目录，不得逃逸，必须是已存在的文件 |
| `skills_dir` | 是 | 相对业务项目目录，不得逃逸，必须存在且至少包含一个技能目录 |

未知字段一律拒绝。清单解析集中在 `agent/plugins.py`，只依赖 `pathlib` 与 `yaml`，不 import loader 或 prompts，避免循环依赖。

MCP 地址不放进插件清单：它属于运行环境配置，继续由 `agent/config.yaml` 的 `business_mcp` 管理。等未来支持多 MCP server 时再引入 `mcp_servers`。

## 配置与加载

```yaml
plugins:
  root: "businesses" # 相对 agri_backend_v2 根目录，不依赖进程 CWD
  active: "farm"     # 可省略；省略时要求恰好一个 plugin.yaml
```

环境变量：`PLUGINS__ROOT`、`PLUGINS__ACTIVE`。

### 技能加载

- `SkillLoader(directory)` 保持单目录语义，`SkillRegistry.from_directory` 行为不变。
- 组合入口 `load_registry()` / `load_all()` / `load_aggregate_skills()` 默认加载 `agent/tools` + 业务 `skills_dir`。
- 两个目录下的技能目录合并后统一按目录名排序，保持现有 59 个展开技能、58 个 exposed 工具及工具顺序。
- 任一技能目录加载失败都抛 `SkillLoadError`，不再静默跳过。
- 插件技能数为 0 单独报错，避免被核心通用技能掩盖。
- 同名目录、同名 skill 明确报错。
- 自定义 `scripts/main.py` 按文件路径加载，并按 resolved path 缓存模块；插件脚本只支持绝对 import。

### 系统提示词

- 平台提示词继续放 `agent/prompts/`。
- `render_system_prompt()` 从插件清单声明的路径读取 `system.md`。
- 提示词缓存按 resolved path 区分，`reload()` 清空全部缓存。
- `list_prompts()` 仍包含 `system`；`inspect_prompts()` 中 system 为 active，`source` 显示 `businesses/farm/prompts/system.md`；核心提示词 source 不变。
- `health.memory_build` 只覆盖 `memory_*.md` 等平台记忆文件，不包含业务 system prompt。

### 启动校验

`agent/bootstrap/app.py` 的 `lifespan` 在启动 worker 前完成：

1. 加载一次统一 registry；
2. 确认插件技能数大于 0；
3. 读取一次 system prompt。

插件目录缺失、清单非法、技能加载失败、system prompt 缺失都在进程启动时失败。

## 空结果策略

Runtime 中唯一硬编码的业务特判是：同一个 `system_templates` 查询第二次返回空目录时，阻止重复查询并引导模型改用 `prepare_planting_plan`。该行为改为 operation 级声明式配置。

```yaml
operations:
  system_templates:
    # ... 现有字段
    empty_result_policy:
      observation:
        code: system_template_catalog_empty
        message: "系统作物模板目录当前为空，请不要再次查询该目录。..."
        missing: [custom_template.stages]
      next_allowed_action:
        agent_tool_name: prepare_planting_plan
        arguments: null
      task_state:
        reason: empty_system_template_catalog
        resume_policy: ask_user
      trace:
        progress_reason: empty_catalog_already_observed
```

运行时由通用 emitter 生成：

- 结果为 `status=needs_information`，`code/message/missing` 来自策略；
- `next_action` 由 `next_allowed_action` 投影；
- `task_state` 固定五个键：`status=blocked`、`reason`、`resume_policy`、`blocked_action`（当前调用参数生成）、`next_allowed_action`；
- 只发出一个 `observation`，不产生 `tool_started`，Turn 保持 `running`；
- trace 记录 `progress=blocked` 和策略中的 `progress_reason`。

以下值由 Runtime 固定，不允许策略配置：`observation.status`、`task_state.status`、`blocked_action`、trace 的 `status`。

校验规则：

- 只允许 operation 级声明，顶层声明报错；
- 封闭 schema，未知字段拒绝；
- `code` / `reason` / `progress_reason` 非空 snake_case，`message` 非空，`missing` 为字符串列表；
- `next_allowed_action.agent_tool_name` 必须已注册、`exposed=True`、不是当前 skill；
- `arguments` 键必须显式存在，值只能是 `null` 或 object；
- `resume_policy` 只允许 `ask_user`；
- 目标必须使用 Agent 工具名（`prepare_planting_plan`），不是 MCP 工具名或聚合 skill 名。

**边界**：本次只声明化“空结果后的响应”，不声明化“什么算空结果”。触发条件仍由 `verify.has_empty_observation` 判定，它识别 `items/templates/workers/records/results` 中的空列表。

## 兼容性

迁移必须保持以下行为不变：

- 59 个展开技能、58 个 exposed 工具、18 个聚合技能及工具顺序；
- `system_templates` 的 observation、task_state、事件序列和文案逐字段不变；
- `prepare_planting_plan` 暴露、`commit_planting_plan` 隐藏，`approval_followup` 链路不变；
- system prompt 内容字节不变，`health.memory_build` 不变；
- `BUSINESS_MCP_URL` / `BUSINESS_MCP__URL` / `login.py` 的 MCP 地址行为不变；
- `/admin/skills` 与 `/admin/prompts` 的响应结构不变（仅 system 的 source 值变化）。

## 部署注意

- `deploy/server-sync.sh` 已把 `businesses` 纳入备份/回滚清单，并保留对旧
  `business`、`plugins` 目录和旧 `business/config.yaml` 的迁移兼容。
- `agent/pyproject.toml` 的 hatch wheel 只打包 `agent`，顶层 `businesses/` 不会进入 wheel；源码部署可用，wheel 部署需额外配置。
- `agent/config.yaml` 被 gitignore，生产环境需要补 `plugins` 节，或设置 `PLUGINS__ROOT` / `PLUGINS__ACTIVE`。
