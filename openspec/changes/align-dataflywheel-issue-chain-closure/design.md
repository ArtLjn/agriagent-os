## Context

DataFlywheel 当前已有两条实现线：

- 新线：`DailyReviewWorkbench`、`ReviewIssueChain` API、chain-derived regression draft、chain-derived repair pack。
- 旧线：高级搜索内的 sample/turn 标注、sample-derived regression draft、sample-derived repair pack。

设计文档要求最终人工真值、expected behavior、regression draft 和 repair pack 都以 `ReviewIssueChain` 为主对象。当前实现的问题不是能力缺失，而是入口未收口：标注员仍能从高级搜索或 turn 审核绕过问题链，生成缺少 chain 证据和 expected behavior 的资产。

## Goals / Non-Goals

**Goals:**

- 让每日质检成为唯一最终人工审核入口。
- 让高级搜索只负责查证、抽检、创建或补充候选链。
- 让 regression draft 和 repair pack 默认只能从 accepted ReviewIssueChain 创建。
- 补齐 `tool_parameter_mismatch` 标签和 IssueChain 审核标签集合。
- 显式展示回填事件、trace 缺失、db diff 缺失等证据状态。

**Non-Goals:**

- 不在本 change 内实现完整 DatasetVersion / EvalRun 页面。
- 不实现完整 Context Analyzer v1 的语义抽取，只为后续候选链提供入口和证据状态。
- 不引入 Kafka、ClickHouse、向量库或新的异步基础设施。
- 不删除底层 sample API；只收紧默认 UI 和正式资产路径，避免破坏现有调试脚本。

## Decisions

### 1. UI 先收口，API 保留兼容但加限制

高级搜索中的旧 `AnnotationPanel` 能保存 turn 标签、采纳 AI 预判、生成 regression draft 和 repair pack。直接删除 API 风险较高，因为测试和调试脚本可能仍使用 sample 级接口。

决策：

- UI 层默认移除高级搜索中的最终标注和闭环按钮。
- sample 级 repair/regression API 保留，但响应和文档标记为 compatibility/debug path。
- 正式按钮只调用 `/review-issue-chains/{chain_id}/case-draft` 和 `/review-issue-chains/{chain_id}/repair-pack`。

替代方案：

- 直接删除 sample API。风险是破坏现有 repair pack 测试和历史调试流程。
- 保留所有入口并只靠文档约束。风险是标注员继续走旧路径。

### 2. IssueChain 审核面板承担最终真值

IssueChain 审核面板已有 accepted/rejected/needs_evidence/not_actionable 表单，但标签集合不完整，也没有闭环按钮。

决策：

- `IssueChainReviewPanel` 使用全量固定标签集合。
- accepted 保存继续要求 `final_labels`、`root_cause`、`expected_behavior`。
- 面板内新增“生成回归草稿”和“导出修复包”，按 chain 状态启用/禁用。
- 禁用原因必须可见，例如未 accepted、缺 expected behavior、needs_evidence。

### 3. 标签枚举以设计文档为准

当前后端 `ALLOWED_LABELS` 缺 `tool_parameter_mismatch`，前端类型也缺该标签。该标签是批量意图收窄和参数作用域错配的核心标签。

决策：

- 后端 `ALLOWED_LABELS`、前端 `DataFlywheelLabel`、筛选选项、IssueChain 审核选项全部补齐。
- 暂不重命名已有 `bulk_intent_narrowed_to_single_entity` 候选类型；它作为 candidate type，可映射到 final label `tool_parameter_mismatch`。

### 4. 证据状态从“有/无事件”升级为 checklist

当前 checklist 只有 event、chat、router、tool_or_pending，无法表达 trace/db diff/backfilled。

决策：

- IssueChain detail 返回至少以下 evidence key：`event_log`、`chat_messages`、`router_decision`、`tool_result`、`pending_lifecycle`、`trace`、`db_diff`、`backfilled_event`。
- `backfilled_event` 不是错误，但必须展示，避免把回填 request_id 当作真实 trace。
- 缺 `db_diff` 可先标记为 `needs_human`，不阻塞 accepted，但阻塞自动 repair-ready。

## Risks / Trade-offs

- **旧 API 仍可被脚本调用** → 在 UI 收口同时对正式导出路径加 chain 校验，并在 API 文档和响应中标记 compatibility。
- **标注员短期找不到 turn 标注入口** → 高级搜索提供“创建候选链/补充到候选链/打开每日质检”动作，避免查证能力丢失。
- **证据状态比真实采集能力更细** → 对暂未采集的 db diff 使用 `needs_human`，明确不是 present。
- **已有测试依赖旧按钮** → 同步更新前端测试断言，保留 sample API 单测但改名为 compatibility/debug。

## Migration Plan

1. 先补齐标签枚举，保证后端和前端都接受 `tool_parameter_mismatch`。
2. 增强 ReviewIssueChain detail evidence checklist。
3. 在 Daily Review 审核面板接入 chain case draft 和 chain repair pack。
4. 收紧高级搜索 UI，移除最终标注和正式资产按钮。
5. 为旧 sample API 增加兼容说明和测试覆盖。
6. 更新设计文档当前状态，运行 DataFlywheel 后端和前端测试。
