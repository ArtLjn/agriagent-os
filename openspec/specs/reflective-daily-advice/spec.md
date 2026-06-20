# reflective-daily-advice Specification

## Purpose
TBD - created by archiving change design-reflective-daily-advice. Update Purpose after archive.
## Requirements

### Requirement: 今日建议生成必须运行反思校验
今日建议生成服务 SHALL 在 LLM 生成草稿后运行今日建议专用 Reflection 校验，并根据 `ReflectionDecision` 决定通过、重试或兜底。

#### Scenario: 草稿通过校验
- **WHEN** LLM 返回合法 v2 JSON，所有 item 都来自候选集合且内容完整
- **THEN** Reflection 返回 `PASS`，服务返回该结构并写入缓存

#### Scenario: 草稿可修复
- **WHEN** LLM 返回合法 JSON 但存在详情过短、steps 不足或 evidence 不完整
- **THEN** Reflection 返回 `RETRY_GENERATION`，服务使用错误列表生成修复提示并重试

#### Scenario: 草稿不可接受
- **WHEN** LLM 返回候选外建议、禁止内容或无法解析的结构
- **THEN** Reflection 返回 `RETRY_GENERATION` 或 `FALLBACK_RESPONSE`，服务不得直接返回该草稿

### Requirement: 今日建议必须执行代码硬校验
今日建议服务 MUST 在 Reflection 质量审查前执行代码硬校验，硬校验失败 SHALL 产生结构化 issue 并阻断草稿返回。

#### Scenario: 候选 ID 不存在
- **WHEN** LLM item 引用了不存在于 selected candidates 的 `id`
- **THEN** 校验失败，issue code 为 `candidate_id_not_allowed`

#### Scenario: 禁止内容出现
- **WHEN** 草稿文本包含无到期日欠款、未结人工、欠薪或未授权工人欠款建议
- **THEN** 校验失败，issue code 为 `forbidden_daily_advice_topic`

#### Scenario: 内容太空
- **WHEN** item 缺少 detail description，或 `compact.subtitle` 少于 15 个中文字符，或 `steps` 少于 2 条
- **THEN** 校验失败，issue code 为 `daily_advice_content_too_thin`

#### Scenario: 优先级越权
- **WHEN** LLM 将候选 priority 从 2 提升为 1
- **THEN** 校验失败，issue code 为 `priority_escalation_not_allowed`

### Requirement: 今日建议 retry 必须有限且不改变信源
今日建议服务 SHALL 最多执行 2 次 LLM 修复重试，重试时 MUST 使用同一批 selected candidates 和 candidate fingerprint。

#### Scenario: 第一次重试成功
- **WHEN** 首次草稿未通过校验，但第一次修复返回通过
- **THEN** 服务返回修复后的结构，缓存 meta 中 `generation_mode` 为 `repaired` 且 `retry_count` 为 1

#### Scenario: 重试耗尽
- **WHEN** 初次生成和 2 次修复重试都未通过校验
- **THEN** 服务使用规则 fallback 生成完整建议结构，缓存 meta 中 `generation_mode` 为 `fallback`

### Requirement: 今日建议必须有规则兜底
今日建议服务 SHALL 能够不依赖 LLM，仅基于 selected candidates 生成可展示的 v2 响应。

#### Scenario: LLM 返回空字符串
- **WHEN** LLM 返回空字符串或 quota/error 文本
- **THEN** 服务不得缓存该原始文本，并 SHALL 返回规则 fallback 响应

#### Scenario: 没有候选信号
- **WHEN** selected candidates 为空
- **THEN** 服务返回 `empty` 模式响应，说明今日暂无高优先级事项，并提供基础巡田/记录步骤

### Requirement: Reflection 结果必须进入 trace 和缓存元数据
今日建议服务 SHALL 将 Reflection 决策、issue code、retry 次数和生成模式写入 trace，并在缓存 meta 中保留可诊断摘要。

#### Scenario: 反思发现问题后修复成功
- **WHEN** Reflection 第一次返回 `RETRY_GENERATION`，第二次返回 `PASS`
- **THEN** trace 中记录两次 reflection_check，缓存 meta 记录最终 `reflection_decision=pass` 和首次 validation errors

#### Scenario: 规则兜底
- **WHEN** 服务进入 fallback
- **THEN** 缓存 meta 记录 `generation_mode=fallback`、`retry_count` 和导致 fallback 的 issue code 列表

