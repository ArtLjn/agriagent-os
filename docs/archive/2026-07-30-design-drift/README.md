# 2026-07-30 设计偏离文档归档

本目录归档与当前 AgriAgentOS 设计事实明显偏离的历史文档。归档只表示它们不再作为当前实现、当前设计或新开发入口的参考；如需追溯历史决策，可继续阅读原文。

## 归档清单

| 原路径 | 归档原因 |
| --- | --- |
| `docs/database/table-analysis.md` | 记录旧 SQLite 快照表结构，当前数据库事实源已迁移到 MySQL / MongoDB 相关设计与 runbook。 |
| `docs/superpowers/plans/2026-05-23-farm-manager-phase3-react-native.md` | 以 React Native 客户端为目标，当前移动端已切换为 Flutter。 |
| `docs/superpowers/plans/2026-05-27-mobile-ui-redesign.md` | 基于 React Native 0.74、React Navigation 和 RN 动画体系，已偏离当前 Flutter 移动端技术栈。 |
| `docs/superpowers/plans/2026-05-24-farm-manager-admin.md` | 早期 PC 管理端实施计划，包含旧 `app.core` / `app.api` / `app.models` / `app.services` 分层入口，已不符合当前后端边界。 |
| `docs/superpowers/plans/2026-05-26-admin-trace-system.md` | 早期 Trace 方案依赖旧 `app.core`、`app.models`、`app.api`、SQLite 写入路径，已偏离当前 Trace / DataFlywheel / Agent 平台边界。 |
| `docs/ui/app-system-ui-design/` | 旧移动端 UI 原型，仍使用旧项目命名和旧助理命名，且不是当前 README 展示用的稳定截图资产。 |
| `docs/architecture/evolution-roadmap.md` | 旧系统演进路线图仍以 React Native、SQLite 兼容和旧后端分层为主，当前路线图已收敛到正式设计文档的项目管理章节。 |

## 当前优先参考

- 根项目入口：[../../../README.md](../../../README.md)
- 设计文档：[../../farm-manager-design-spec/README.md](../../farm-manager-design-spec/README.md)
- 当前路线图：[../../farm-manager-design-spec/06_项目管理/01_里程碑与路线图.md](../../farm-manager-design-spec/06_项目管理/01_里程碑与路线图.md)
- 后端架构：[../../architecture/backend-architecture.md](../../architecture/backend-architecture.md)
- Agent 开发标准：[../../agent/agent-development-standard.md](../../agent/agent-development-standard.md)
- 稳定截图资产：[../../assets/screenshots/](../../assets/screenshots/)
