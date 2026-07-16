## Why

DataFlywheel 已完成每日质检和 ReviewIssueChain MVP，但当前实现仍保留旧的 turn-first 标注、sample 级 regression、sample 级 repair pack 出口，导致标注员可以绕过 issue chain 的人工判断和 expected behavior 约束。

现在需要做一次收口修复：让 DataFlywheel 的最终真值、回归草稿和修复包都回到 ReviewIssueChain 主流程，同时保留高级搜索作为查证入口。

## What Changes

- 收紧 DataFlywheel 页面边界：
  - 每日质检成为唯一最终人工审核入口。
  - 高级搜索仅用于 session/request/turn 查询、证据查看、创建或补充候选链。
  - 高级搜索内移除或禁用 turn 级 final label、root cause、expected behavior、regression draft、repair pack 操作。
- 补齐固定标签体系：
  - 新增 `tool_parameter_mismatch` 到后端允许标签、前端类型、筛选项和 IssueChain 审核面板。
  - IssueChain 审核面板使用完整 §6 标签集合，而不是只展示少量 MVP 标签。
- 收口闭环出口：
  - 每日质检右侧审核面板提供从 `chain_id` 生成 regression draft 和 repair pack 的动作。
  - repair pack 默认只允许从 accepted 且 expected behavior 完整的问题链导出。
  - 旧 sample 级 repair pack / regression draft 入口降级为调试兼容入口，默认 UI 不再暴露。
- 改善证据可信呈现：
  - 在 timeline 和审核面板中显式展示 event、trace、tool result、pending lifecycle、db diff、backfilled trace 的缺失状态。
  - 回填 request_id 或回填事件必须显示为 backfilled，不能被误解为真实 trace 缺失。
- 保持不引入新基础设施：继续使用 MySQL 热索引 + JSONL 证据文件 + 现有 admin API。

## Capabilities

### New Capabilities

- `dataflywheel-issue-chain-closure`: DataFlywheel IssueChain 主流程收口能力，约束最终人工判断、regression draft、repair pack 和高级搜索边界都围绕 ReviewIssueChain 执行。

### Modified Capabilities

- `failure-repair-pack-export`: repair pack 导出默认从 accepted ReviewIssueChain 创建，旧 sample 级导出必须作为兼容/调试路径被显式限制。
- `agent-evaluation-foundation`: regression draft 从 ReviewIssueChain 创建时必须带 expected behavior、chain metadata 和 related turns；高级搜索不得直接创建正式回归资产。

## Impact

- **admin-web**：
  - 修改 `admin-web/src/pages/DataFlywheel/` 信息架构和按钮权限。
  - `IssueChainReviewPanel` 增加完整标签、chain case draft、chain repair pack 操作。
  - 高级搜索内 `AnnotationPanel` 相关 final 标注和闭环按钮下线或禁用。
- **backend**：
  - 补齐 `tool_parameter_mismatch` 标签枚举与 API 校验。
  - 对 sample 级 repair/regression API 增加兼容限制或显式 debug 标识。
  - ReviewIssueChain detail 增强 evidence checklist。
- **测试**：
  - 增加后端 API 单测：标签枚举、chain 出口校验、sample 出口限制。
  - 增加前端测试：高级搜索不能保存最终真值；每日质检能从 chain 生成 draft/pack。
- **文档**：
  - 更新 `docs/farm-manager-design-spec/01_正式设计/06_数据飞轮与评测.md` 当前状态和页面边界说明。
