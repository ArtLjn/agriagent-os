## Why

当前 DataFlywheel 工作台以全量 turn 和日志详情为主，标注员点击样本后只能看到单轮回复、工具摘要和零散调试字段，难以结合 session 上下文判断问题，也不知道下一步该补证据、写 expected、生成回归还是导出修复包。

Farm Manager 的真实坏例经常跨多轮发生，例如「查询欠款 → 批量结算工资 → 确认执行」组成一条问题链。飞轮工作台需要从“turn 表格日志浏览器”升级为“每日质检待办 + session 上下文 + 问题链审核”的闭环工具。

## What Changes

- 新增 **Daily Review Inbox** 作为 DataFlywheel 默认首页：按风险 session 分组展示每日最该处理的质检任务，而不是默认平铺全部 turn。
- 新增 **ReviewIssueChain** 概念：一个 session 内围绕某个风险点形成的相关 turn 集合，包含 trigger/context/result turns、诊断摘要、证据 checklist、人工 expected behavior、状态机和闭环出口。
- 重构 DataFlywheel 信息架构：
  - `每日质检`：风险 Session Inbox + Session Timeline + 问题链审核面板。
  - `高级搜索`：承载原全量 session / 全部 turn / request_id 查询。
  - `修复包`：保留 repair pack 列表与状态管理。
  - `数据集/评测`：承载 dataset、simulation、evaluation 趋势入口。
- 将原 `问题候选` 从独立主 Tab 降级为 Daily Review Inbox 的候选来源。
- 将原 `Session 复盘` 变成每日质检中间主工作区，默认展示完整 session timeline 并高亮当前问题链。
- 将原 `Turn 审核` 变成问题链审核面板或单 turn 展开详情，不再要求用户先从 turn 表格进入。
- 审核面板改为判断流程优先：诊断摘要 → 证据 checklist → 人工判断 → expected behavior → regression / repair pack 出口。
- MVP 使用虚拟问题链：围绕候选 turn 自动取前 1-3 轮、后 1-2 轮，并支持人工增删相关 turn；V2 再由 Context Analyzer 生成语义任务链。

## Capabilities

### New Capabilities

- `dataflywheel-review-workbench`: DataFlywheel 每日质检工作台，包括风险 Session Inbox、ReviewIssueChain 问题链、Session Timeline 高亮、判断流程优先审核面板、问题链状态机和页面入口重构。

### Modified Capabilities

- `agent-evaluation-foundation`: 标注与 case draft 需要支持以 `ReviewIssueChain` 作为审核目标和回归来源，人工结论必须包含 expected behavior 后才能生成 regression draft。
- `failure-repair-pack-export`: repair pack 导出需要支持从问题链生成，包含相关 turn 证据、expected behavior、缺失证据状态和 chain-level fix target。

## Impact

- **前端**：
  - `admin-web/src/pages/DataFlywheel/` 页面信息架构重构。
  - 新增或拆分 `DailyReviewInbox`、`ReviewIssueChainTimeline`、`IssueChainReviewPanel`、`AdvancedSearch` 等组件。
  - 原样本队列、问题候选、Session 复盘、Turn 审核入口需要迁移或降级。
- **后端 API**：
  - 新增/调整 DataFlywheel review inbox API，按 session 聚合风险链。
  - 新增/调整 issue chain detail API，返回 trigger/context/result turns、证据 checklist、状态和人工审核字段。
  - case draft / repair pack API 支持 `chain_id` 或虚拟链 payload。
- **数据模型**：
  - MVP 可用虚拟链，不强制新增复杂表。
  - 持久化阶段需要支持 `ReviewIssueChain`、chain-level label / expected / status。
- **评测与修复闭环**：
  - regression draft 必须消费 expected behavior。
  - repair pack 需要包含问题链相关 turn 和证据完整性信息。
- **文档**：
  - 与 `docs/farm-manager-design-spec/01_正式设计/06_数据飞轮与评测.md` 第 10 节保持一致。
