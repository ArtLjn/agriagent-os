---
status: implemented
last_updated: 2026-10-25
---
# 陪伴关怀业务

## 背景

第二个业务插件 `businesses/companion/`，用于验证 Agent 内核与业务资源的可插拔
边界。它不处理农场数据，只提供日常陪伴、情绪倾听和轻量关怀建议。

陪伴业务只包含 Agent 本地技能和 system prompt，不启动独立 Business 服务，
也不新增数据库表。管理员可以在业务中心或侧边栏切换器里把它设为当前业务，
切换在当前 Agent 进程内立即生效。

## 目录

```text
businesses/companion/
├── plugin.yaml
├── pyproject.toml                 # uv workspace 占位，无常驻服务
├── prompts/system.md
└── skills/
    ├── companion-checkin/         # 按时间生成问候
    └── companion-activity/        # 按状态推荐小关怀动作
```

`plugin.yaml`：

```yaml
schema_version: 2
name: companion
display_name: 陪伴助手
description: 日常陪伴、情绪关怀与轻量关怀建议
system_prompt: prompts/system.md
skills_dir: skills
```

## 技能

| Skill | 类型 | 作用 |
|---|---|---|
| `companion_checkin` | local / read | 按当前时段生成一段简短问候和一个开放式问题 |
| `companion_activity` | local / read | 根据 happy / okay / tired / low / anxious 推荐五分钟内可完成的小动作 |

两个技能都只做本地文本生成，不读业务数据库、不调用 MCP、不做情绪诊断。
`companion_activity` 的 `minutes` 限制在 1–30。

## System prompt 边界

`prompts/system.md` 明确：

- 先倾听再回应，每次最多问一个真正关心的问题；
- 不诊断心理疾病、不推荐药物、不替代专业治疗；
- 遇到自伤、伤人或严重危机时，鼓励联系信任的人、当地急救或报警；
- 不索取与陪伴无关的敏感信息。

## 切换方式

```http
PUT /api/v2/admin/businesses/active
{"name": "companion"}
```

- 目标业务先通过清单、技能注册表和 system prompt 校验，失败时不切换；
- 成功后替换进程内 `settings.plugins.manifest` 并清空提示词缓存；
- 新请求立即使用陪伴 system prompt 和两个本地技能，重启后恢复部署配置；
- 农场业务仍拥有 16 个 MCP 技能，切回农场时需要当前 Business 服务可用。

## 管理后台

- 业务中心显示“陪伴关怀”卡片、2 个技能目录和当前启用状态；
- 侧边栏业务切换器可直接切换；
- 业务视角包含“陪伴空间”和“陪伴对话”；
- 陪伴空间把心情记录保存在浏览器 `localStorage`，不写入服务端；
- 陪伴对话复用现有 Agent 聊天组件，切换为陪伴文案并隐藏农事标签、报告和茬口
  选择；system prompt 已切换为陪伴人格；
- 助手设置按业务隔离，陪伴业务默认“陪伴助手”，称呼、表达方式、自定义指令等
  与农场业务互不覆盖；长期记忆和记忆读写开关仍为全局共享。

## 验证

- `tests/test_companion_business.py`：清单、技能加载、问候输出、参数校验；
- `tests/test_admin_businesses_api.py`：管理员切换、未知业务 404、权限；
- 前端 `src/pages/Companion/index.test.tsx`：心情记录、恢复、进入对话；
- 全量后端与前端测试通过。

## 非目标

- 独立 Business REST/MCP 服务或数据库持久化；
- 心理诊断、治疗建议、药物建议；
- 多用户共享心情数据（当前只保存在设备本地）；
- 多业务同时加载。
