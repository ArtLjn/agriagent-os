## Context

`add-running-summary-compaction` 只解决同一 session 内的多轮失忆：把窗口外历史压成 `conversations.summary` 并在下一轮注入。它不会解决跨 session 的用户偏好、习惯、别名、事件和事实沉淀。

当前 `backend/app/memory/long_term/` 仍为空实现，用户每次都要重复说明"我喜欢下午浇水"、"记账用万元"、"老王就是王师傅"这类长期信息。长期记忆需要独立数据模型、确认/候选流转、注入策略和归档规则，复杂度高于 running summary，因此从 P0 摘要提案中拆出，作为后续独立 change。

## Goals / Non-Goals

**Goals**：

- 新增 `memory_records` 表，持久化 5 类长期记忆：preference / habit / alias / event / fact
- 支持用户显式记忆直接 confirmed
- 支持 LLM 抽取候选，candidate 经用户确认或重复出现升级为 confirmed
- 支持偏好软覆盖、低重要性候选自动归档
- MemorySelector 查询并注入 `memory_long_term` ContextBlock
- 保证长期记忆按 `farm_id` 隔离

**Non-Goals**：

- 不修改 running summary 生成逻辑
- 不引入 Redis、向量库、embedding 检索
- 不做复杂相似度合并，第一版用 SQL 排序和内容 hash
- 不让 LLM 抽取结果直接覆盖人工事实
- 不删除历史记忆，归档和覆盖均保留审计痕迹

## Decisions

### D1：5 类记忆，不做类型合并

**选择**：固定 5 类 `preference / habit / alias / event / fact`，与 [04_Memory工程 § 4](../../../farm-manager-design-spec/01_正式设计/04_Memory工程.md) 一致。

**理由**：
- 类型决定流转规则（fact 永久，preference 可覆盖）
- 合并类型会让 archive / superseded 逻辑混乱

### D2：显式说 vs 隐式抽分流

**选择**：
- 显式：用户说"记一下"、"记住"等触发词 → LLM 不参与判断，直接 `source=user_explicit, importance=0.8, status=confirmed`
- 隐式：LLM 在抽取阶段输出 → `source=llm_extracted, importance=0.3, status=candidate`

**理由**：
- 显式用户意图明确，无需候选阶段
- 隐式抽取可能误判，需要候选校验
- `source` 字段便于追溯和后续治理

### D3：candidate→confirmed 双轨触发

**选择**：升级路径有两条并行：
1. 用户显式确认（"对"、"以后都这样"）→ confirmed (0.8)
2. 同类候选重复 N=3 次 → 自动 confirmed (0.7)

**理由**：
- 显式确认置信度高
- 隐式重复说明习惯稳定，应升级
- 两条独立触发，互不阻塞

**Alternatives**：
- 只允许显式确认（rejected：用户不会每次确认，导致候选队列堆积）
- 只看重复次数（rejected：误抽会因重复升级为 confirmed）

### D4：不做 embedding 相似检索，SQL where 够用

**选择**：长期记忆注入只按 `farm_id + status + importance + last_referenced_at` 排序取前 5 条，不做向量相似。

**理由**：
- 用户偏好是结构化事实（"我喜欢下午浇水"），与当前对话的关联交给 LLM 判断即可
- 当前用户量 < 10，每户 memory_records < 100，SQL 排序足够快
- 引入 embedding 等于引入向量库，违背 [brainstorming spec § 5](../../../docs/superpowers/specs/2026-06-19-knowledge-and-memory-architecture-design.md) "Qdrant 暂缓"决策

### D5：长期记忆独立触发，不与摘要强绑定

**选择**：长期记忆抽取复用 Response 节点后的异步时机，但作为独立 MemoryService 方法与 feature flag 控制，不要求与 summary 合并为同一次 LLM 调用。

**理由**：
- 摘要已经作为 P0 独立上线，长期记忆不应阻塞摘要能力
- 长期记忆可独立灰度、独立关闭、独立观测
- 如果后续成本压力明显，再评估把 summary 与 observations 合并为一次 LLM 调用

## Risks / Trade-offs

| Risk | Mitigation |
| --- | --- |
| LLM 抽取出错误偏好污染上下文 | candidate 阶段低 importance，仅 confirmed 后高优先级注入；保留 source 与 confidence |
| 候选队列无限堆积 | 90 天未引用且 importance < 0.5 自动 archive |
| 同类候选"重复 N 次"识别难 | 第一版用 type + 内容前 50 字符 hash；后续按 trace 数据优化 |
| 显式触发词覆盖不全 | 第一版固定列表（"记一下"、"记住"、"以后都"），按 bad case 补充 |
| 跨农场泄露记忆 | 所有查询强制 `WHERE farm_id=:farm_id`，单测覆盖隔离 |
| 长期记忆挤占短期上下文 | `memory_long_term` priority 低于 `conversation_summary` 和最近窗口，预算紧张时优先丢弃长期记忆 |

## Migration Plan

### 部署步骤

1. 合并 PR → CI 跑 memory / selector / advisor flow 测试
2. 部署 staging，feature flag `ai.enable_long_term_memory=false`
3. staging 开启 feature flag，人工构造显式记忆和隐式重复场景
4. 抽检 trace：抽取准确率 ≥ 70%，跨农场隔离无异常
5. 生产先给 5 个内测农户开启 1 周，再评估全量

### Rollback

- 关闭 `ai.enable_long_term_memory`
- `memory_records` 表可保留，不参与查询时不影响主流程
- 若需要回滚 schema，执行对应 Alembic downgrade

## Open Questions

1. 显式触发词第一版列表是否需要区分普通"记账"与"记住偏好"？
2. candidate 自动升级阈值 N=3 是否过高？备选 2 / 4。
3. `memory_long_term` 默认注入 LIMIT 5 是否足够？备选 3 / 8。
4. 是否需要 admin 页面展示和删除长期记忆？第一版倾向只做后端能力，UI 后置。
