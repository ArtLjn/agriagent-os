## Context

Data Flywheel 已经具备 turn 样本列表、人工标签、LLM 预标注、issue candidates 和 case draft。当前断点在于：失败样本虽然能标注和生成回归草稿，但缺少一个面向 coding agent 的导出物，导致 vibecoding 拿到的是零散 bad 数据，而不是可执行的修复任务。

本设计把 Data Flywheel 的失败样本加工为 repair pack。repair pack 是一个稳定目录结构，包含任务 manifest、失败案例 JSONL、脱敏 debug evidence、regression draft 和 README。它的目的不是训练模型，而是让 vibecoding 按 `fix_target` 逐步修复 Agent 行为。

约束：

- 不改变在线聊天热路径。
- 不引入新的重型 LLMOps 平台或队列。
- 导出物必须可读、可审查、可复制给 coding agent。
- 真实会话证据必须脱敏，保留来源引用。
- 一次导出应聚焦一个问题簇，避免把不同修复目标混在一起。

## Goals / Non-Goals

**Goals:**

- 从已标注失败样本生成可由 vibecoding 消费的 repair pack。
- 将标签、预标注、issue candidates 和 case draft 派生为 `fix_target`、优先级、建议修复动作和验证命令。
- 支持按标签、修复目标、回归准备状态和数量导出代表样本。
- 让 repair pack 能进入 Simulation / Evaluation 回归流程。
- 修复完成后能将相关 label 标记为 resolved，并保留来源关联。

**Non-Goals:**

- 不做自动代码修复。
- 不把 bad reply 直接作为 SFT 数据。
- 不在本变更中建设完整 dataset 版本管理。
- 不要求引入 DB-backed simulation cases；可先输出 regression draft。
- 不让导出操作扫描全量 JSONL；样本列表仍使用 MySQL 索引，详情按 turn 读取事件片段。

## Decisions

### Decision 1: Repair pack 使用目录包而不是单个 JSONL

选择目录结构：

```text
repair-packs/<pack_id>/
  manifest.json
  cases.jsonl
  README.md
  debug/
    <sample_id>.json
  regression-drafts/
    <case_id>.json
```

原因：

- vibecoding 更容易按 README 和 manifest 理解修复目标。
- debug evidence 和 regression draft 通常较大，拆文件更便于审查。
- cases.jsonl 保持批量处理友好，manifest 保持任务级元数据清晰。

备选方案是只导出 JSONL，但会把任务目标、证据和回归断言混在一起，后续扩展困难。

### Decision 2: 修复目标从标签规则派生，允许人工覆盖

首版规则：

| 标签 | fix_target |
| --- | --- |
| `sensitive_info_leak` | `guardrail` |
| `pending_missed` | `pending_plan` |
| `disabled_worker_used` | `tool_guardrail` |
| `missing_wage` | `domain_policy` |
| `tool_error_ignored` / `hallucinated_execution` | `tool_result_state` |
| `wrong_tool_selection` | `router` |
| `bad_reply` / `off_topic` | `prompt_or_sft` |

当一个样本有多个标签时，按优先级选择主 `fix_target`，并在 case item 保留全部标签和次级建议。管理员可以在导出前覆盖 `fix_target`。

原因：

- bad label 是缺陷索引，不足以直接指导修复。
- 规则派生足够轻量，符合当前小服务器约束。
- 人工覆盖能避免复杂标签组合被误路由。

### Decision 3: Repair pack metadata 可先落 DB，也可先文件导出

推荐新增轻量表 `agent_repair_packs` 保存：

- `pack_id`
- `farm_id`
- `fix_target`
- `labels`
- `source_sample_ids`
- `status`
- `export_path`
- `created_by`
- `created_at`
- `updated_at`

不强制新增 case item 表。每个 sample 与 label/case draft 的细粒度关系可以由 `manifest.json` 和现有表追溯。

原因：

- UI 需要展示历史导出包和状态。
- 不需要为 MVP 设计复杂 dataset schema。
- 文件导出失败时可以记录 failed 状态，便于重试。

### Decision 4: 导出证据必须脱敏并保留引用

debug evidence 输出前执行脱敏：

- 密钥、token、`.env`、provider credentials。
- 手机号、精确地址等可识别个人信息。
- 超大 payload 使用摘要、hash 和 source reference。

同时保留：

- `sample_id`
- `session_id`
- `turn_id`
- `request_id`
- `event_file`
- `event_seq_start`
- `event_seq_end`

原因：

- vibecoding 需要证据定位问题，但不应接触敏感配置。
- source reference 可以在本地管理员环境中继续追溯完整证据。

### Decision 5: Repair pack 不直接写入最终测试集

导出包内只放 regression draft。管理员或 vibecoding 修复时先将 draft 转为测试或评测用例，再运行验证。

原因：

- 当前 simulation case 存储可能仍依赖文件，部署环境可写性不稳定。
- 失败样本生成的断言需要人工确认，避免低质量断言污染稳定回归集。

### Decision 6: Verification commands 由 fix_target 和项目默认测试共同生成

manifest 中包含建议验证命令：

- 通用 Data Flywheel 服务/API 测试。
- 与 `fix_target` 对应的 router、pending、skill 或 guardrail 测试。
- 可选 Simulation/Evaluation 命令。

原因：

- vibecoding 需要明确完成标准。
- 不同修复目标的验证范围不同，全部跑全量测试成本高。

## Risks / Trade-offs

- 修复路由规则过粗 → 在 manifest 中保留人工覆盖字段和完整标签，首版优先覆盖高频标签。
- 导出包证据不足 → 每个 case 必须包含 debug JSON、issue assertions 和 source reference；缺失事件片段要在 manifest warnings 中展示。
- 导出敏感信息 → 导出前统一走脱敏函数，测试覆盖密钥、token、手机号、地址等模式。
- vibecoding 误改无关模块 → README 明确只围绕 `fix_target` 最小修改，manifest 提供 entry files 和 verification commands。
- regression draft 断言质量弱 → repair pack 标记 `regression_ready=false`，要求先补测试/断言再修代码。
- 大量样本导出过慢 → 限制单包样本数量，列表查询走 MySQL，详情按样本读取事件片段。
