# 04 — Evaluation 评测

> 状态：草稿 | 维护：BlockShip | 关联：[01_正式设计/06_数据飞轮与评测](../01_正式设计/06_数据飞轮与评测.md)、权威 [../../../docs/architecture/agent-data-flywheel-industrial-roadmap.md](../../../docs/architecture/agent-data-flywheel-industrial-roadmap.md)

---

## 1. 目的

仿真只问"行为对不对"，评测量化"质量有多好"：
- 准确率（Skill 调用是否正确）
- 完整性（必要信息是否覆盖）
- 安全性（Reflector 触发率 / Prompt 注入拦截率）
- 效率（Token 成本 / 延迟）
- 用户感受（人设一致性 / 语气）

## 2. 评测指标

### 2.1 任务级

| 指标 | 计算 |
| --- | --- |
| `skill_precision` | 正确 Skill 调用 / 全部 Skill 调用 |
| `skill_recall` | 应调用 Skill 中被正确触发的比例 |
| `pending_action_accuracy` | PendingAction payload 正确率 |
| `task_completion_rate` | 用户意图最终被满足的比例 |

### 2.2 质量级

| 指标 | 计算 |
| --- | --- |
| `hallucination_rate` | Reflector 标记幻觉的比例 |
| `fact_consistency` | LLM judge 评分（0-1） |
| `persona_consistency` | 人设匹配度（关键词 / LLM judge） |
| `response_relevance` | 与用户意图相关度 |

### 2.3 效率级

| 指标 | 计算 |
| --- | --- |
| `avg_tokens_per_turn` | 平均每轮 Token 消耗 |
| `avg_latency_ms` | 平均首 Token 延迟 |
| `p95_latency_ms` | P95 延迟 |
| `cost_per_conversation_usd` | 单次对话成本 |

### 2.4 安全级

| 指标 | 计算 |
| --- | --- |
| `prompt_injection_block_rate` | 注入测试集拦截率 |
| `cross_farm_leak_rate` | 越权数据泄漏率（必须为 0） |
| `pending_action_bypass_rate` | 写操作绕过确认的比例（必须为 0） |

## 3. 评测集

### 3.1 标注集

来自 DataFlywheel 标注（详见 [01_正式设计/06_数据飞轮与评测](../01_正式设计/06_数据飞轮与评测.md)）：

- `eval_core`：100 条核心样本，长期固定（不参与训练）。
- `eval_recent`：最近 30 天真实样本（去 PII），每周刷新。
- `eval_adversarial`：50 条对抗样本（注入 / 越权 / 歧义）。

### 3.2 评测集版本

```text
backend/evaluation/datasets/
├── eval_core/v1.jsonl
├── eval_recent/2026-W25.jsonl
└── eval_adversarial/v1.jsonl
```

每次发布前记录使用的 dataset 版本到 EvaluationReport。

## 4. 评测流程

```
1. 加载 dataset
2. 对每条样本：
   a. 重置 env（不污染 prod 数据）
   b. 跑 /chat
   c. 收集 trace + 响应
3. 跑 LLM judge（用更强模型评分）
4. 跑规则校验（关键词 / 字段匹配）
5. 聚合指标
6. 写 EvaluationReport
7. 与上一版对比，标 delta
```

## 5. LLM Judge

- 评判模型：Claude Sonnet 4.6（与生产同）或更强。
- 评分维度：`fact_consistency` / `persona_consistency` / `response_relevance`。
- Prompt 模板：`backend/evaluation/prompts/judge_v1.md`。
- 输出：JSON `{score: 0-1, reason: "..."}`。

**禁止**用 GPT-4 / 国内非授权模型做 judge（合规 + 一致性）。

## 6. 启动命令

```bash
# 标准评测
poetry run python -m app.evaluation.run \
  --dataset eval_core \
  --report-dir backend/evaluation/reports/$(date +%Y-%m-%d)

# 多版本对比
poetry run python -m app.evaluation.run \
  --dataset eval_core \
  --baseline backend/evaluation/reports/2026-06-12 \
  --compare prompt-v3

# 仅对抗集
poetry run python -m app.evaluation.run \
  --dataset eval_adversarial \
  --focus security
```

## 7. 报告格式

```json
{
  "report_id": "2026-06-19_eval_core_v1",
  "dataset": "eval_core/v1",
  "model": "claude-sonnet-4-6",
  "timestamp": "2026-06-19T15:30:00Z",
  "metrics": {
    "skill_precision": 0.94,
    "skill_recall": 0.89,
    "task_completion_rate": 0.92,
    "hallucination_rate": 0.03,
    "fact_consistency": 0.91,
    "persona_consistency": 0.95,
    "avg_tokens_per_turn": 1840,
    "p95_latency_ms": 7800,
    "cost_per_conversation_usd": 0.012,
    "prompt_injection_block_rate": 1.0
  },
  "delta_vs_baseline": {
    "skill_precision": +0.02,
    "hallucination_rate": -0.01,
    "cost_per_conversation_usd": -0.002
  },
  "failed_samples": [
    {"sample_id": "s-042", "reason": "wrong skill called"}
  ],
  "judge_examples": [
    {"sample_id": "s-017", "score": 0.6, "reason": "未提及具体金额单位"}
  ]
}
```

## 8. 发布门禁

每次发布前必须满足：

| 指标 | 门禁 |
| --- | --- |
| `task_completion_rate` | ≥ 0.90 |
| `hallucination_rate` | ≤ 0.05 |
| `prompt_injection_block_rate` | = 1.0 |
| `cross_farm_leak_rate` | = 0 |
| `pending_action_bypass_rate` | = 0 |
| `cost_per_conversation_usd` | ≤ 0.02 |
| `p95_latency_ms` | ≤ 8000 |

任一不达标 → 阻塞发布。

## 9. 评测节奏

| 频率 | 范围 |
| --- | --- |
| 每个 PR | smoke（10 条核心，低成本） |
| 合并到 main | eval_core 全集 |
| 每周 | eval_recent + eval_adversarial |
| 发布前 | 全集 + baseline 对比 |
| Prompt/Skill 大改 | 全集 + 留 baseline |

## 10. 评测结果回流

- 评测发现的 bad case → 进入 DataFlywheel `repair_candidates`。
- 评测发现的 good case → 进入 Prompt 示例库（few-shot）。
- 评测报告 → 写入 `docs/design/evaluation-history.md` 供回溯。

## 11. 评测反模式

- 用同一模型既生成又评分（自我评分偏差）。
- 评测集与训练集混用（数据泄漏）。
- 只看聚合指标，不看具体 bad case。
- 改 Prompt 后没留 baseline，无法对比。
- 把"LLM judge 评分"当成绝对真理（必须配合规则校验）。

## 12. 相关文档

- [01_测试金字塔与策略.md](./01_测试金字塔与策略.md)
- [02_回归测试集.md](./02_回归测试集.md)
- [03_Simulation仿真测试.md](./03_Simulation仿真测试.md)
- [01_正式设计/06_数据飞轮与评测](../01_正式设计/06_数据飞轮与评测.md)
- 权威：[../../../docs/architecture/agent-data-flywheel-industrial-roadmap.md](../../../docs/architecture/agent-data-flywheel-industrial-roadmap.md)
