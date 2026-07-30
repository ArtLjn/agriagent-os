## ADDED Requirements

### Requirement: 长期记忆 5 类分层
系统 SHALL 将用户长期记忆分为 5 类：`preference`（偏好）、`habit`（习惯）、`alias`（别名）、`event`（事件）、`fact`（事实）。每条记忆 SHALL 持久化到 `memory_records` 表，含 `farm_id`、`user_id`、`type`、`content`、`importance`（0.0-1.0）、`status`（candidate/confirmed/superseded/archived）、`confidence`、`source`（user_explicit/llm_extracted）、`superseded_by_id`、`created_at`、`confirmed_at`、`last_referenced_at`。

记忆 SHALL 严格绑定到 `farm_id`，禁止跨农场查询。

#### Scenario: 不同类型记忆分流
- **WHEN** LLM 抽取阶段输出多条候选
- **THEN** 每条候选 SHALL 标注正确的 type（如"我喜欢下午浇水"→preference；"老王电话是 138..."→alias）

#### Scenario: 跨农场隔离
- **WHEN** 系统查询某用户的长期记忆
- **THEN** SQL 查询 SHALL 包含 `WHERE farm_id = :farm_id`，禁止跨农场读取

### Requirement: 显式记忆直确认
当用户在对话中明确表达"记一下"、"记住"、"以后都"等触发词，并附带可识别的偏好/事实内容时，系统 SHALL 直接写入 `memory_records`，`source=user_explicit`、`status=confirmed`、`importance=0.8`，跳过候选阶段。

#### Scenario: 用户显式要求记忆
- **WHEN** 用户说"记一下我喜欢下午浇水"
- **THEN** 系统在 Response 节点后异步写入一条 `type=preference, content='喜欢下午浇水', source=user_explicit, status=confirmed, importance=0.8` 的记忆

#### Scenario: 触发词缺失
- **WHEN** 用户说"我喜欢下午浇水"但没有"记一下"等触发词
- **THEN** 系统走 LLM 抽取候选流程，不直接 confirmed

### Requirement: LLM 抽取候选流转
LLM 抽取阶段输出的候选记忆 SHALL 进入候选状态：`status=candidate`、`importance=0.3`、`source=llm_extracted`、`confidence` 记录 LLM 输出置信度。候选 SHALL 通过两条独立路径升级为 confirmed：

1. **显式确认**：用户主动表达"对"、"以后都这样"、"是的"等肯定触发词 → `status=confirmed, importance=0.8`
2. **隐式重复**：同 `type + content 前 50 字符 hash` 的候选累计出现 N=3 次 → 自动 `status=confirmed, importance=0.7`

高置信（confidence ≥ 0.85）+ 类型为 `preference`/`habit`/`alias` 的候选 SHALL 直接以 `importance=0.5` 写入但保持 `status=candidate`，等待用户确认或重复升级。

#### Scenario: 候选默认状态
- **WHEN** LLM 抽取输出一条新候选
- **THEN** 写入 `status=candidate, importance=0.3, source=llm_extracted`

#### Scenario: 用户确认升级
- **WHEN** 候选存在且用户主动确认
- **THEN** 系统更新该记录 `status=confirmed, importance=0.8, confirmed_at=now()`

#### Scenario: 隐式重复升级
- **WHEN** 同类候选（type + 内容前 50 字符 hash 相同）累计达到 3 次
- **THEN** 系统自动将最新一条升级为 `status=confirmed, importance=0.7`，旧候选标记为 `superseded_by_id`

#### Scenario: 高置信直入候选
- **WHEN** LLM 输出 confidence=0.9 的 preference 候选
- **THEN** 写入 `status=candidate, importance=0.5`（不直接 confirmed）

### Requirement: 偏好软覆盖
当用户表达与已有 confirmed 记忆相反的内容（如旧："喜欢下午浇水" / 新："改成上午"）时，系统 SHALL 创建新记忆，并将旧记忆标记为 `superseded_by_id` 指向新记忆，不删除旧记忆。`fact` 类型记忆 SHALL 永久保留，不参与软覆盖。

#### Scenario: 偏好被覆盖
- **WHEN** 用户已有 `type=preference, content='喜欢下午浇水', status=confirmed`，新表达"改成上午浇水"
- **THEN** 系统写入新记忆，旧记忆 `status=superseded, superseded_by_id=新记忆.id`

#### Scenario: 事实不被覆盖
- **WHEN** 用户已有 `type=fact, content='去年亏损 3 万', status=confirmed`，新表达不同内容
- **THEN** 系统不覆盖旧 fact，新内容作为独立记忆写入

### Requirement: 长期记忆注入
ContextBuilder SHALL 通过 MemorySelector 查询当前农场的长期记忆注入 ContextBundle：

```sql
SELECT * FROM memory_records
WHERE farm_id = :farm_id
  AND status IN ('confirmed', 'candidate')
  AND importance >= 0.3
ORDER BY importance DESC, last_referenced_at DESC
LIMIT 5
```

注入的 block SHALL 标记 `key=memory_long_term`、`priority` 介于 conversation_summary 与 retrieval 之间。`last_referenced_at` SHALL 在被注入时更新为当前时间。

#### Scenario: 注入高优先级记忆
- **WHEN** 用户农场有 3 条 confirmed（importance=0.8）+ 5 条 candidate（importance=0.3）记忆
- **THEN** MemorySelector 注入 confirmed 在前、candidate 在后的前 5 条

#### Scenario: 无记忆时不注入
- **WHEN** 用户农场无符合条件记忆
- **THEN** ContextBundle 不包含 `memory_long_term` block，不产生空 block

### Requirement: 自动归档
系统 SHALL 通过定时任务（每日凌晨）扫描 `memory_records`，将满足以下条件的记忆标记为 `status=archived`：
- `importance < 0.5`
- `last_referenced_at` 距今 > 90 天

archived 记忆 SHALL 不再被 MemorySelector 注入，但 SHALL 保留在表中不删除（合规审计）。

#### Scenario: 长期未引用低重要性记忆归档
- **WHEN** 某条 candidate 记录 `importance=0.3, last_referenced_at=100 天前`
- **THEN** 定时任务将其 `status` 改为 `archived`

#### Scenario: 高重要性记忆不归档
- **WHEN** 某条 confirmed 记录 `importance=0.8, last_referenced_at=365 天前`
- **THEN** 不被归档，仍可被注入

### Requirement: 长期记忆抽取失败降级
LLM 抽取调用失败 / 超时 / 输出格式不合法时，系统 SHALL 跳过本次抽取，不写入候选，不抛错。失败次数 SHALL 通过熔断器累计，超阈值后短时间内跳过抽取。

#### Scenario: LLM 抽取超时
- **WHEN** 抽取 LLM 调用 30s 超时
- **THEN** 系统记录 trace `observations_skipped{reason=timeout}`，不写候选；主流程不受影响

#### Scenario: 输出 JSON 不合法
- **WHEN** LLM 输出无法解析为 `[{type, content, confidence}]` 数组
- **THEN** 系统跳过本次，记录 `observations_skipped{reason=invalid_output}`

### Requirement: 长期记忆与短期记忆边界
长期记忆 SHALL 与短期记忆（最近窗口、会话摘要）独立存储与查询，互不污染。MemorySelector SHALL 同时产出 `memory.short_term`（来自 short_term_memory_policy）与 `memory.long_term`（来自本 capability）两个 block，分别注入。

#### Scenario: 短期与长期同时注入
- **WHEN** 用户既有最近窗口消息，又有 confirmed 偏好
- **THEN** ContextBundle 同时包含 `short_term_recent`、`short_term_summary`（如有）、`memory_long_term` 多个 block，分别有独立 key 与 priority
