# 兼容入口清单

本文记录架构迁移期间保留的旧入口、保留理由和后续删除条件。

## Agent

| 旧入口 | 新入口 | 保留理由 | 删除条件 |
| --- | --- | --- | --- |
| `app.agent.graph` | `app.agent.runtime` | 保持既有测试和外部调用兼容 | 下游全部迁移到 `app.agent.runtime` 后删除 |
| `app.agent.prompt_registry` | `app.prompt.registry` | Prompt 工程化迁移兼容 | Prompt 相关 import 全部切换后删除 |
| `app.agent.prompt_renderer` | `app.prompt.renderer` | Prompt 工程化迁移兼容 | Prompt 相关 import 全部切换后删除 |
| `app.agent.prompt_composer` | `app.prompt.composer` | Prompt 工程化迁移兼容 | Prompt 相关 import 全部切换后删除 |
| `app.agent.prompt_cache` | `app.prompt.cache` | Prompt 工程化迁移兼容 | Runtime 与 API 全部改用 `app.prompt` 后删除 |

## Auth

| 旧入口 | 新入口 | 保留理由 | 删除条件 |
| --- | --- | --- | --- |
| `app.core.security` | `app.modules.auth.password`、`app.modules.auth.tokens` | 保持历史安全工具 import 兼容 | 业务代码和测试全部迁移到 `app.modules.auth` 后删除 |
| `app.api.deps` | `app.modules.auth.dependencies`、`app.modules.farm.dependencies` | 保持 FastAPI 依赖 import 兼容 | API 路由全部迁移到模块依赖后删除 |
| `app.services.auth_service` | `app.modules.auth.service` | 保持服务层历史 import 兼容 | 调用方全部改用 Auth 模块后删除 |
| `app.api.auth` | `app.modules.auth.router` | 保持路由注册路径兼容 | Bootstrap 路由注册确认只使用模块 router 后删除 |

## 维护规则

- 新增兼容入口必须在本文件登记。
- 兼容入口只允许 re-export 或薄适配，不允许继续承载业务逻辑。
- 每次完成一个迁移阶段后，应检查本文件是否可删除对应旧入口。
