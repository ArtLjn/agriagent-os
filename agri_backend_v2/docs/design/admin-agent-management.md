---
status: implemented
last_updated: 2026-10-23
---
# Agent 管理页与运行监控

导航拆为业务运营、业务调试、Agent 开发、运行监控、系统管理。Prompt 管理位于 Agent 开发，Token 看板位于运行监控。仿真入口关闭，旧 `/dev/simulation` 地址跳转 Playground。数据飞轮页面暂时关闭，菜单移除，旧 `/dev/data-flywheel` 地址跳转链路追踪。

## 提示词管理

`agent/api/admin_prompts.py` 通过 ADMIN_DEBUG 权限依赖提供列表与重新加载接口，前端使用 `/api/agent/admin/prompts` 代理至 Agent `/api/v2/admin/prompts`。

列表内容来自运行时模板缓存，版本为 SHA-256 内容指纹，标明系统实际使用的 system 模板及源文件。页面支持搜索、全文预览和重新加载。源文件通过版本控制维护，不提供在线编辑和任意路径读写。重新加载只作用于当前进程及随后创建的上下文，多进程部署应统一发布并重启所有实例。

## Token 统计

`agent/api/admin_tokens.py` 负责管理员权限、日期验证、响应契约；`agent/platforms/persistence/mongo/token_stats.py` 隔离 Mongo 聚合。新增文件分别由 bootstrap 和管理接口调用，避免将查询逻辑继续塞入超过 1000 行的 Trace store 或无关 Skill 接口。

- 查询 `/admin/stats/tokens`、`/daily`、`/hourly`，前端均通过 Agent 代理。
- 按北京时间自然日划分，将起止时间转换为 UTC 闭开区间；最多 93 天，数据库执行最多 15 秒。Agent 启动时创建节点类型与时间复合索引，避免全表扫描。
- 只汇总 `llm_call` 节点的真实 `token_usage`，不重复累计父节点摘要。请求数表示带 usage 的 LLM 调用次数，不等于用户消息数。
- 支持用户、模型过滤与日期/小时/用户/模型维度展示；缺失 usage 的调用不估算、不计入。
- 数据源为已持久化 Trace，受 Trace 保留期和写入延迟影响，不作为供应商计费账单。Mongo 未启用或查询失败返回结构化 503，成功但无记录返回零。
- 周/月配额上限来自 Business 用户配置，用量分别查询 Agent 的本周、本月统计，替代 Business 旧接口固定的零用量。仅用于看板展示，不修改请求准入或配额拦截逻辑。

## 验证

后端覆盖未登录、普通用户拒绝、模板缓存与重载、北京时间边界、统计聚合、过滤、范围限制、空数据与存储不可用。前端覆盖导航分类、提示词搜索/预览/重试/重载、API 代理路径和 Token 部分失败展示。
