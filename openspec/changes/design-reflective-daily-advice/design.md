## Context

今日建议已有候选信号管线、候选排序、缓存和基础结构化响应：后端从天气、作业单、茬口阶段、财务等来源生成 `DailyAdviceCandidate`，再让 LLM 改写为 `preview + items`。移动端首页已经展示三条 AI 今日建议，详情页设计包含判断依据、执行步骤、关联事项和底部动作，但当前接口没有稳定提供这些字段，导致页面需要静态占位或从短文案推断。

项目新增了 `backend/app/agent/reflector/`，它提供 `ReflectionDecision`、`ReflectionResult`、规则检查、policy 和 trace 记录。今日建议生成正好需要一个质量门：LLM 可以负责表达，但不能决定信源、优先级和候选范围。

## Goals / Non-Goals

**Goals:**
- 单个今日建议接口同时支撑 App 首页和建议详情页，App 首屏只请求一次。
- 每条建议包含 `compact` 首页缩略字段和 `detail` 详情字段。
- 规则层决定候选、来源、优先级、禁止项和 fallback；LLM 只补全文案与步骤表达。
- 通过代码硬校验和 Reflection 质量审查避免空建议、废话建议、候选外建议和污染建议。
- 支持有限 retry，并保证 retry 失败时仍返回可展示、可解释、可追溯的 fallback。
- 保留 `advice` 和旧 `items[].title/detail/priority/icon` 兼容输出。

**Non-Goals:**
- 不新增单条详情接口；详情页直接使用同一份今日建议响应。
- 不让 LLM 调用工具重新获取信源；今日建议信源只来自规则层候选管线。
- 不在本次变更解决所有首页经营态势评分算法，只定义接口结构和基本聚合语义。
- 不移除旧字段和旧缓存兼容，避免一次性破坏 admin-web 与旧移动端。

## Decisions

### Decision 1: 一个接口返回首页和详情完整结构

继续使用 `GET /agent/daily` 和 `POST /agent/daily/refresh`，响应升级为 v2 结构。响应包含 `overview`、`items[]`、`advice`、`created_at`、`generation` 等字段，每个 item 同时带：

- `compact`: 首页 AI 今日建议列表使用，包含标题、短说明、图标和颜色。
- `detail`: 建议详情页使用，包含描述、hero badges、evidence、steps、related、actions。

替代方案是新增 `GET /agent/daily/items/{id}`，但这会让 App 首页点击详情时二次请求，且缓存一致性更复杂。当前交互是点首页箭头进入同一个建议详情页面，单接口更符合体验目标。

### Decision 2: 规则候选是事实源，LLM 只做结构化文案补全

`DailyAdviceCandidate` 仍是事实源，包含候选 ID、类别、priority、due_date、source_type、source_id、reason。生成 v2 响应时，后端先用候选构建确定性 skeleton，再让 LLM 补全文案字段，如 `compact.title`、`compact.subtitle`、`detail.description`、`detail.steps`。

后端不接受 LLM 新增 candidate id，不接受 LLM 修改 `category/source_type/source_id/priority`。这样可以避免“未结人工”“无到期日欠款”等候选外内容再次进入今日建议。

### Decision 3: 代码硬校验先于 Reflection 质量审查

今日建议有两类校验：

- 硬校验：JSON schema、必填字段、items 非空、candidate id 存在、priority 不越权、禁止词、最小长度、steps/evidence 完整性。
- 质量审查：文案是否太泛、步骤是否可执行、依据是否解释清楚、首页标题是否像行动建议。

硬校验必须由代码执行，失败时直接产生 `ReflectionResult`，决策为 `RETRY_GENERATION` 或 `FALLBACK_RESPONSE`。Reflection 框架负责聚合检查结果、输出 trace、提供 retry/fallback 决策和修复说明。这样不会把不可违反的业务约束交给模型主观判断。

### Decision 4: 有限 retry 后规则兜底

生成流程最多允许 2 次修复重试：

1. 用 v2 prompt 生成草稿。
2. 后端硬校验 + Reflection 质量审查。
3. 若可修复，带错误列表和 `repair_instruction` 重试。
4. 仍失败则用规则层 skeleton 渲染 fallback。

retry 不重新收集信源，不改变候选排序，只修复结构和文案。fallback 使用候选的 `title_hint/detail_hint/reason`、类别默认 steps、类别默认 actions 和来源关联信息生成完整结构，保证接口不返回空结构。

### Decision 5: 缓存按 schema 版本和候选指纹管理

缓存内容保存完整 v2 JSON。`AgentRecord.meta` 记录：

- `schema_version`: `daily_advice_v2`
- `candidate_fingerprint`
- `generation_mode`: `llm`、`repaired`、`fallback`、`empty`
- `retry_count`
- `reflection_decision`
- `validation_errors`

读取缓存时必须校验 schema version 和 candidate fingerprint。旧缓存或污染缓存可以继续解析为旧字段，但不能阻止 v2 重新生成。

### Decision 6: 移动端用同一 ViewModel 传递详情

移动端 `DailyAdvice` 模型解析完整 v2 响应，首页只读取 `items[].compact`；点击任一箭头进入详情页时传入同一条 `DailyAdviceItem` 或其索引，不二次请求。若旧响应没有 `compact/detail`，移动端用旧 `title/detail` 生成最小兼容展示。

## Risks / Trade-offs

- [Risk] 响应体变大，首页请求包含详情字段。→ Mitigation: items 限制最多 3-5 条，详情字段控制长度，避免返回 raw prompt 和大段来源快照。
- [Risk] LLM retry 增加延迟。→ Mitigation: 最多 2 次；硬失败快速 fallback；缓存命中不调用 LLM。
- [Risk] Reflection 检查异常影响接口可用性。→ Mitigation: 今日建议只读生成路径按“fail to fallback”处理，不让异常抛给用户。
- [Risk] 旧前端依赖 `items[].title/detail/icon`。→ Mitigation: 后端保留旧字段，映射自 `compact`。
- [Risk] 规则 fallback 文案不如 LLM 自然。→ Mitigation: fallback 以可用和可信为优先，后续通过类别模板逐步优化。
- [Risk] 详情页关联事项可能再次混入经营状态噪音。→ Mitigation: `related` 只允许由候选 source 或明确风险摘要生成，未结人工只能作为资金概览卡展示，不进入今日建议 related，除非存在有到期日的应付事项候选。
