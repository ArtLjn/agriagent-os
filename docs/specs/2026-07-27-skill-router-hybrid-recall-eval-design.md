# Skill Router 混合召回与评测闭环设计

> 状态：设计中 | 日期：2026-07-27 | 关联：`backend/app/agent/router/*`、`backend/app/ops/skill_route_cases.json`、`docs/farm-manager-design-spec/01_正式设计/02_Skill引擎与契约.md`

## 1. 背景

当前 Skill Router 已经从中心化规则演进到 `SkillRegistry` 驱动的 `CandidateRetriever`。这套轻量召回依赖 registry metadata、示例、标签、legacy alias 和 anti examples 进行字符串命中打分，适合第一阶段减少工具暴露数量。

现在主要瓶颈不是最终排序，而是第一阶段候选召回不稳定：如果 BM25 或轻量词法打分直接裁剪到 top5，正确 operation 经常没有进入候选池，后续 embedding 或 LLM tool selection 就没有机会纠正。

典型失败模式：

```text
用户输入：我有哪些欠款
期望：manage_cost.query_debt
错误现象：泛查询示例“有哪些...”把 farm-status、分类、模板、地块、工人等读工具推到前面，
         query_debt 只命中“欠款”一个强领域词，可能被挤出 top5。
```

因此新策略必须把“候选召回”和“最终 top5 排序”拆开：BM25 不再作为 top5 硬筛选器，而是和 embedding、规则强召回共同产生候选并集，再由混合重排输出最终候选。

## 2. 目标

1. 正确 operation 必须尽量进入候选池，避免被第一阶段截断。
2. 最终仍只向 LLM 暴露少量 tool，保持 schema budget 和响应速度。
3. 使用测试集驱动优化，每次调整算法、同义词、metadata 或阈值都要跑回归。
4. embedding 是召回和重排信号，不是安全边界；写确认、权限、operation 校验仍由 policy 和 runtime guard 执行。
5. 外部 embedding 服务异常时自动降级到 BM25 + 规则召回，Agent 不因 embedding 不可用而整体失败。

## 3. 非目标

- 不引入向量数据库；Skill/operation 数量小，第一版可在进程内缓存 operation embedding。
- 不让 embedding 结果绕过 `RouterPolicy`、pending action、operation registry validation。
- 不把 Basic Auth 密码、API Key 或服务私密地址写进测试快照、trace 明文和公开文档。
- 不通过继续堆 Python 特定 skill if/else 修复召回；业务表达优先沉淀到 registry metadata 和测试集。

## 4. 总体架构

```text
User Message
  ↓
QueryNormalizer
  - 分词、字符 n-gram、同义词扩展、低信号泛词标记
  ↓
OperationDocumentBuilder
  - 从 SkillRegistry 构建 operation 粒度文档
  - capability、operation、description、examples、tags、legacy_aliases、anti_examples 分字段保留
  ↓
MultiSourceRecall
  ├─ StrongRuleRecall：强领域词、operation alias、风险意图保底召回
  ├─ BM25Recall：字段加权 BM25，召回 top20/top30，不直接裁剪 top5
  └─ EmbeddingRecall：query 与 operation 文档语义相似召回 top20/top30
  ↓
CandidateUnion
  - 三路结果取并集，保留每一路 evidence
  ↓
HybridReranker
  - 融合 BM25、embedding、规则、registry prior、anti example penalty
  ↓
TopKSelector
  - 输出 top5 operation candidates
  - 同 skill 多 operation 做去重和保留
  ↓
RouterPolicy
  - read/write 风险裁剪、schema budget、澄清、fallback
  ↓
LLM Tool Selection
  ↓
Runtime Guard
  - operation 合法性、写确认、缺参、权限和执行前校验
```

核心原则：**多路召回取并集，混合重排出 top5**。任何单一路径都不能作为唯一硬筛。

## 5. Operation 文档建模

索引粒度必须是 operation，不是 skill。原因是一个 skill 内部可能包含多个语义相近但操作不同的能力，例如：

| Skill | Operation | 典型输入 |
| --- | --- | --- |
| `manage_cost` | `query_summary` | 这个月花了多少钱 |
| `manage_cost` | `query_debt` | 我有哪些欠款 |
| `manage_cost` | `analyze_cost` | 最近三个月成本趋势 |
| `manage_cost` | `settle_debt` | 把老王农资店的账结清 |

每条 operation 文档包含以下字段：

| 字段 | 来源 | 用途 |
| --- | --- | --- |
| `skill_name` | capability name | 最终 tool 绑定 |
| `operation_name` | registry operation | operation 精确命中 |
| `domain` | registry domain | registry prior 和业务域解释 |
| `capability_description` | capability description | embedding 语义背景 |
| `operation_description` | operation description | operation 级 BM25 和 embedding 主体 |
| `examples` | capability examples + operation examples | 用户表达召回 |
| `tags` | capability tags | 强领域词召回 |
| `legacy_aliases` | operation legacy_aliases | 兼容召回 |
| `anti_examples` | capability anti_examples | 降权和冲突解释 |
| `risk` | operation risk | policy 裁剪 |

BM25 建议使用字段加权：

```text
operation_name / legacy_aliases: 3.0
tags: 2.5
operation_description: 2.0
examples: 1.5
capability_description: 1.0
domain: 0.5
anti_examples: 单独计算 penalty，不进入正向 BM25
```

低信号泛词，例如“查询、查看、看看、有哪些、多少、现在、这个月、今天、列表、show、list、what、which”，只能作为辅助信号，不能单独把候选推入最终 top5。

## 6. 多路召回策略

### 6.1 StrongRuleRecall

强规则不是旧式中心 if/else，而是从 registry 派生的保底召回：

- 用户输入命中 operation `legacy_aliases`、operation name 或高权重 tag 时，该 operation 进入候选池。
- 用户输入命中强领域词时，对应 operation 至少进入候选池，不保证最终 top1。
- 用户输入命中 anti example 时，对冲突 operation 加 penalty。

第一批强领域词可以从失败测试集反推：

| 词 | 保底候选 |
| --- | --- |
| 欠款、赊账、未结清、还欠 | `manage_cost.query_debt` |
| 花了多少钱、支出、收入、账单、流水 | `manage_cost.query_summary` |
| 趋势、同比、环比、分析 | `manage_cost.analyze_cost` |
| 地块、棚、种植单元 | `manage_planting_units.query_units` |
| 茬口、种植周期 | `manage_crop_cycle.query_cycles` / `query_cycle_info` |
| 工人、员工、人员 | `manage_workers.query_workers` |
| 工资、人工费、应付、补付 | `manage_labor_payment.query_payables` |
| 天气、下雨、打药适合吗 | `weather.query_forecast` |

这些映射应逐步沉淀到 `skills.yaml` 的 tags、examples、operation description 或独立 routing hints，而不是长期散落在 Python 代码里。

### 6.2 BM25Recall

BM25 负责词法召回，不负责最终裁剪。推荐参数：

```text
bm25_limit = min(30, operation_count)
bm25_min_score = 0.0
bm25_output = top30
```

BM25 输出必须保留：

- 原始分数
- 命中字段
- 命中 token
- 是否只命中低信号泛词

如果候选只命中低信号泛词，允许进入候选并集，但 rerank 时降权。

### 6.3 EmbeddingRecall

embedding 负责语义召回，尤其覆盖短句、口语表达和同义改写。

第一版不接向量数据库，原因是 operation 数量有限。启动或 registry 变更时为 operation 文档计算 embedding，存入进程内缓存；查询时只计算 query embedding，并对全量 operation 文档做余弦相似度。

推荐参数：

```text
embedding_limit = min(30, operation_count)
embedding_timeout_ms = 800
embedding_cache_key = provider + model + registry_version + operation_doc_hash
```

embedding 配置只允许从配置系统和环境变量读取。文档、测试样例、trace 中禁止出现认证密码。trace 只能记录 provider、model、endpoint host、耗时、是否降级和错误 code。

## 7. 混合重排

候选并集进入 reranker 后统一归一化和打分。

推荐第一版公式：

```text
hybrid_score =
  0.35 * bm25_norm
+ 0.35 * embedding_norm
+ 0.20 * lexical_intent_score
+ 0.10 * registry_prior
- anti_example_penalty
- low_signal_only_penalty
```

字段说明：

| 分数 | 含义 |
| --- | --- |
| `bm25_norm` | BM25 分数在候选并集内归一化 |
| `embedding_norm` | cosine similarity 映射到 0 到 1 |
| `lexical_intent_score` | tag、operation alias、领域强词和同义词命中 |
| `registry_prior` | active capability、risk 与 coarse intent 一致、domain 命中 |
| `anti_example_penalty` | 命中 anti_examples 或冲突域表达时降权 |
| `low_signal_only_penalty` | 只命中“有哪些/多少/查询”等泛词时降权 |

选择阈值：

```text
candidate_pool_min = 12
final_top_k = 5
accept_top1_margin = 0.08
clarify_if_top2_close_and_cross_domain = true
```

如果 top1 与 top2 分差很小且跨业务域，例如财务欠款 vs 工人工资，应输出可解释 evidence，让 policy 或 LLM 追问，而不是强行执行写操作。

## 8. 测试集测试 + 优化循环

路由优化采用固定循环，不凭感觉调权重。

```text
1. 收集失败输入
   - 来自 Admin 预览、trace、人工反馈、回归测试失败
   - 脱敏后写入 skill_route_cases.json

2. 标注期望 route
   - expected: skill + operation
   - acceptable: 允许等价或兼容候选
   - tags: 域、读写、风险、回归来源

3. 跑离线评测
   - 输出 recall@1、recall@5、operation_hit@5
   - 输出每条失败的三路召回证据和混合分数

4. 诊断失败类型
   - strong_rule_miss：强领域词没有保底召回
   - bm25_miss：BM25 未召回
   - embedding_miss：embedding 未召回
   - rerank_wrong：候选进池但排序错误
   - metadata_gap：registry examples/tags/description 不足
   - ambiguous_case：样本本身多义，需要 acceptable 或澄清策略

5. 选择最小优化动作
   - metadata_gap：优先补 skills.yaml examples/tags/operation description
   - strong_rule_miss：补 routing hint 或强 tag 映射
   - rerank_wrong：调整权重、低信号词 penalty 或 anti_examples
   - embedding_miss：检查 operation doc 构造和 embedding 服务
   - ambiguous_case：更新 acceptable 或澄清规则

6. 重跑全量测试集
   - 新 case 必须命中
   - 旧 case 不得回退

7. 固化结果
   - 更新 regression case
   - 更新 trace evidence 字段
   - 必要时更新设计文档和正式契约文档
```

建议评测命令保持简单：

```bash
cd backend
PYTHONPATH=. .venv/bin/python -m app.ops.skill_route_eval app/ops/skill_route_cases.json --top-k 5
```

评测目标分阶段推进：

| 阶段 | 数据集规模 | 目标 |
| --- | --- | --- |
| Phase 1 | 现有 6 到 30 条核心业务样本 | `operation_hit@5 = 100%` |
| Phase 2 | 30 到 100 条真实失败样本 | `recall@1 >= 85%`，`operation_hit@5 >= 98%` |
| Phase 3 | 100 条以上多轮和混合表达样本 | 按业务域统计，不允许高风险写误召回 |

## 9. 失败诊断输出

评测报告需要从“只看 top5”升级为“看候选如何产生”。每个 case 至少输出：

```json
{
  "case_id": "debt_query_001",
  "message": "我有哪些欠款",
  "expected": "manage_cost.query_debt",
  "top_k": ["manage_cost.query_debt", "manage_cost.query_summary"],
  "recall_sources": {
    "strong_rule": ["manage_cost.query_debt"],
    "bm25": ["get_farm_status.query_status", "manage_cost_categories.query_categories"],
    "embedding": ["manage_cost.query_debt", "manage_cost.query_summary"]
  },
  "scores": {
    "manage_cost.query_debt": {
      "hybrid": 0.82,
      "bm25": 0.31,
      "embedding": 0.77,
      "lexical": 1.0,
      "penalty": 0.0
    }
  },
  "diagnosis": "bm25_miss_recovered_by_strong_rule_and_embedding"
}
```

这类 evidence 后续也应进入 Admin 预览，方便人工快速判断是样本问题、metadata 问题还是算法权重问题。

## 10. 降级和安全策略

| 场景 | 行为 |
| --- | --- |
| embedding 服务超时 | 记录 `embedding_timeout`，使用 StrongRuleRecall + BM25Recall |
| embedding 返回维度不一致 | 丢弃 embedding 分数，触发配置告警 |
| Basic Auth 认证失败 | 不重试明文凭证，记录 `embedding_auth_failed` |
| 候选池为空 | 返回无候选，让 RouterPolicy 走 fallback 或澄清 |
| top2 跨域且分差小 | 优先澄清或同时暴露 read 候选，不直接写 |
| 写操作被召回 | 仍必须经过 write_confirm / write_high policy |

embedding 相关日志只允许包含：

- provider
- model
- endpoint host
- timeout_ms
- latency_ms
- error_code
- fallback_mode

禁止记录：

- username
- password
- Authorization header
- query 原文中的敏感信息未脱敏版本

## 11. 实施边界建议

第一轮实现不需要重写整个 Router。建议按以下边界推进：

1. 新增 operation document builder，复用 `SkillRegistry`。
2. 新增 BM25 scorer，先在内存中运行。
3. 新增 embedding client 和 operation embedding cache。
4. 新增 hybrid retriever，保留现有 `CandidateRetriever` 接口或以兼容适配层替换。
5. 扩展 `skill_route_eval.py` 输出三路 evidence 和诊断类型。
6. 将 `SkillRouter._retrieved_frames()` 从 capability 级召回改成 operation 级候选，再聚合到 tool。

与现有代码的关键差异：

- 旧方案：`CandidateRetriever.retrieve(message, catalog.candidates())`，主要是 skill/capability 粒度。
- 新方案：`HybridOperationRetriever.retrieve(message, operation_documents)`，先选 operation，再映射到 selected tool。

## 12. 验收标准

实现完成后必须满足：

1. `backend/app/ops/skill_route_cases.json` 全量 `operation_hit@5 = 100%`。
2. `debt_query_001` 中 `manage_cost.query_debt` 必须通过 strong rule 或 embedding 进入候选池。
3. embedding 服务不可用时，评测仍可运行，并明确标记 fallback。
4. trace 和评测输出不包含认证密码。
5. 写操作样本不会因为 embedding 相似而绕过 pending confirmation。
6. 新增或修改 routing metadata 后，必须跑 skill route regression。

