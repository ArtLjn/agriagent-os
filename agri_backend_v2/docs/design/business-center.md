---
status: implemented
last_updated: 2026-10-25
---
# 管理后台业务中心

## 背景

Agent 已按 `businesses/<name>/` 加载业务技能和 system prompt，但管理后台仍是
单一农场信息架构：没有业务概念，农事页面与平台页面混排，新增业务没有统一的
发现和入口。

本次在管理后台增加“业务层”：侧边栏业务切换器、统一业务中心页面，以及按业务
收纳的导航。一个 Agent 进程仍只加载一个业务插件，但管理员可以在当前进程内
切换插件；重启后恢复部署配置。

## 关键决策

- **切换业务 = 切换运行时插件**。切换器调用管理员接口，目标业务通过清单、
  技能和 system prompt 校验后，替换进程内 `settings.plugins.manifest` 并清空
  提示词缓存，新请求立即使用新业务；不重启进程。重启后回到 `PLUGINS__ACTIVE`。
- **只读预览兜底**。刷新后如果本地保存的视角不是当前启用业务，业务页面仍
  禁用并回到业务中心，直到用户主动切换；接口不可用时状态记为“状态未知”，
  沿用注册视图导航。
- **前端视图显式注册**。业务导航、首页和路由归属由
  `agri_admin_web/src/businesses/registry.ts` 提供；后端已有但前端未注册的业务
  在业务中心显示“管理端视图未接入”。
- **业务清单来自运行进程**。`active` 只读 `settings.plugins.active`，不在列表
  请求时重新发现插件，避免磁盘状态覆盖进程已加载的清单。
- **运行时切换只切换 Agent 资源**。Business 服务地址和 MCP 工具仍由部署配置
  决定；陪伴业务只含本地技能，因此不依赖 Business 服务。含 MCP 技能的业务
  切换后必须确保当前运行的 Business 服务匹配该业务。

## 后端接口

```http
GET /api/v2/admin/businesses
Authorization: Bearer <admin token>
```

需要 `admin:debug`。响应：

```json
{
  "active": "farm",
  "total": 1,
  "items": [
    {
      "name": "farm",
      "display_name": "农场助理",
      "description": "农场经营管理助手",
      "skill_count": 16,
      "error_code": null
    }
  ]
}
```

- `name` 始终取目录名，与前端 registry 的 `name` 对应。
- `skill_count` 是业务技能目录数，不是最终展开的 Agent Skill 数。
- 单个清单非法时 `display_name` / `description` 为 `null`、`skill_count=0`，
  `error_code` 返回稳定错误码；不返回异常文本或绝对路径。
- 业务根目录缺失或不可读返回 503 `business_catalog_unavailable`。

切换接口：

```http
PUT /api/v2/admin/businesses/active
Authorization: Bearer <admin token>
Content-Type: application/json

{"name": "companion"}
```

切换前会加载目标业务的清单、全部技能和 system prompt；任一失败返回 4xx，
原业务保持不变。成功后返回 `active`、`display_name`、`skill_count`，并清空
提示词缓存。该切换只存在于当前进程，重启恢复部署配置。

实现位置：

- `agent/plugins.py`：`list_plugins()` / `PluginScan`；
- `agent/api/admin_businesses.py`：管理端路由；
- `agent/bootstrap/app.py`：管理端模块注册。

## 前端结构

```text
agri_admin_web/src/
├── api/businesses.ts                 # 业务清单与运行时切换接口
├── businesses/
│   ├── registry.ts                   # 业务视图、首页、路由归属、业务菜单
│   ├── businessContext.ts            # context、默认值、本地存储
│   └── BusinessProvider.tsx          # 清单加载、视角与切换状态
├── components/BusinessSwitcher.tsx   # 品牌区下方切换器
├── pages/BusinessCenter/             # 业务中心页面与样式
└── pages/Companion/                  # 陪伴空间页面
```

侧边栏结构：

- 业务切换器；
- 当前业务分组（农场业务或陪伴关怀）；
- 平台管理（业务中心、用户管理、助手设置）；
- Agent 开发、运行监控、系统管理。

业务中心使用五态：

| 状态 | 含义 |
|---|---|
| 当前启用 | 清单有效，且等于进程 `active` |
| 已安装未启用 | 清单有效，但不是当前进程启用的业务 |
| 清单异常 | 目录存在，但清单校验失败，带 `error_code` |
| 视图未接入 | 后端已安装，前端 registry 未注册导航 |
| 状态未知 | 接口失败或前端视角在运行时清单中缺失 |

当前视角持久化到 `localStorage` 的 `tianzhanggui-business-view`；只保存用户
主动选择，推导出的默认值不写回。Provider 在 `BrowserRouter` 内只挂载一次，
未登录时不请求清单。

## Prompt 管理与业务视角

Prompt 管理页是平台页面，但内容跟随当前业务视角：

- 平台提示词来自 `agent/prompts/*.md`，所有业务共享，标记为“平台内置”；
- system prompt 来自当前查看业务的 `prompts/system.md`，标记为“业务 · <name>”；
- `GET /api/v2/admin/prompts?business=<name>` 允许管理员只读预览任意已安装业务
  的 system prompt，响应顶层返回 `business` 与 `active_business`；
- 只有 `business` 等于当前启用业务时，“重新加载模板”才可用；预览非启用业务时
  按钮禁用，页面提示当前进程实际使用的业务；
- 重载只清空当前 Agent 进程的模板缓存，对新建上下文生效，不改变磁盘文件。

切换 system prompt 有两条路径：业务中心/切换器调用运行时切换接口（当前进程
立即生效，重启恢复部署配置），或修改 `PLUGINS__ACTIVE` 并重启 Agent。运行时
改盘不会写入任何配置文件。

## 个性化设置隔离边界

助手设置按业务隔离，长期记忆保持全局：

| 字段 | 作用域 | 默认值 |
|---|---|---|
| `nickname`、`assistant_name`、`reply_style`、`detail_level`、`display_format`、`custom_instructions`、`loading_greeting_enabled`、`execution_detail_level` | 按业务 | 用户默认值；`assistant_name` 取 `plugin.yaml` 的 `assistant_name` |
| `auto_learn_enabled`、`use_saved_memories` | 全局 | 用户级记忆开关 |
| 长期记忆 | 全局 | 按用户和历史农场范围共享 |

`GET/PATCH /api/v2/me/personalization?business=<name>` 读写指定业务的助手设置；
省略 `business` 时使用当前启用业务。陪伴业务默认使用“陪伴助手”，农场业务
默认使用“田掌柜”，风格、称呼等设置互不覆盖。长期记忆和记忆读写开关仍按
用户级共享，不按业务拆分。

## 新增业务

1. 后端创建 `businesses/<name>/`，提供 `plugin.yaml`、`prompts/system.md`
   和至少一个 `skills/<skill>/skill.md`；
2. 部署时设置 `PLUGINS__ACTIVE=<name>`。本地同时存在多个业务目录时也必须
   配置 `plugins.active` 或环境变量，否则 `discover_plugin` 会因歧义拒绝启动；
   运行时可以通过业务中心临时切换，无需修改配置文件；
3. 在 `agri_admin_web/src/businesses/registry.ts` 注册该业务的导航、首页和
   `routePrefixes`。

一次部署仍只启用一个业务；未注册前端视图不会影响 Agent 运行。含 MCP 技能的
业务需要匹配的 Business 服务；纯本地技能业务（如陪伴关怀）不需要。

## 验证

- `uv run --package farm-manager-agent python -m pytest -q`；
- `npm test`、`npm run lint`、`npm run build`；
- 农场业务保持 59 个展开技能 / 58 个 exposed 工具；陪伴业务为 2 个本地技能 +
  2 个核心工具。

## 非目标

- 一个进程同时加载多个业务；
- 运行时切换 Business 服务地址或 MCP 工具；
- 业务脚手架 `_template` / `new_business.sh`；
- 管理后台 URL 按业务命名空间重写；
- 多标签页视角同步。
