# 03 — Simulation 仿真测试

> 状态：草稿 | 维护：BlockShip | 关联：[01_正式设计/01_Agent平台架构](../01_正式设计/01_Agent平台架构.md)、[02_回归测试集.md](./02_回归测试集.md)

---

## 1. 目的

回归测试只看"最终结果对不对"，但 Agent 是黑盒多步流程，需要更细粒度的仿真：
- 验证 Planner 决策路径
- 验证 Skill 调用顺序
- 验证 Reflector 触发条件
- 验证 PendingAction 流转
- 验证 Context 压缩时机

## 2. 仿真 vs 集成

| 维度 | 集成测试 | 仿真测试 |
| --- | --- | --- |
| LLM | mock | 真 LLM |
| DB | 测试 SQLite | 测试 schema 或影子库 |
| 关注 | API 契约 / 数据正确性 | Agent 行为 / 决策路径 |
| 速度 | 秒级 | 分钟级 |
| 成本 | 低 | 高（LLM token） |
| 频率 | 每个 PR | 合并到 main 前 / 每日 |

## 3. 仿真架构

```
┌─────────────────────────────────────────┐
│         SimulationRunner                │
│                                         │
│  for case in cases:                     │
│    1. 重置测试 DB                       │
│    2. 注入 case.context                 │
│    3. 调 /chat（真 LLM）                │
│    4. 收集 trace events                 │
│    5. 断言 expected                     │
│    6. 写 EvaluationReport               │
└─────────────────────────────────────────┘
```

## 4. Trace 收集

仿真强制开启 `trace_level=full`，收集：

| 事件 | 来源 |
| --- | --- |
| `llm_call` | Runtime LLM 调用 |
| `tool_call` | Executor 触发 Skill |
| `pending_action` | PendingAction 创建 / 确认 / 撤销 |
| `reflector_check` | Reflector 校验 |
| `context_bundle` | ContextBundle 内容快照 |
| `memory_op` | MemoryService 读写 |

Trace 落 `trace_records` 表 + JSONL 文件，供报告渲染。

## 5. 用例格式

```json
{
  "scenario_id": "cost-create-with-debt",
  "description": "记账 + 赊账",
  "seed_data": {
    "farm_id": 1,
    "current_crop_cycle_id": 12,
    "existing_debts": []
  },
  "messages": [
    {"role": "user", "content": "昨天买了200块化肥，老王农资店赊账"}
  ],
  "expected": {
    "skills_called": ["create_cost_record"],
    "skill_order_matters": false,
    "pending_action": {
      "type": "create_cost",
      "auto_confirm": false,
      "payload_contains": {"amount": 200, "category": "化肥"}
    },
    "response_contains": ["已记账", "老王"],
    "reflector_warnings": [],
    "max_tokens_used": 4000,
    "max_latency_ms": 8000
  },
  "llm_config": {
    "provider": "anthropic",
    "model": "claude-sonnet-4-6",
    "temperature": 0
  }
}
```

## 6. 仿真模式

| 模式 | 用途 | 范围 |
| --- | --- | --- |
| `smoke` | PR 快速验证 | 5-10 条核心 |
| `regression` | 合并前 | 全集（80-120 条） |
| `nightly` | 每日回归 | 全集 + 评测 |
| `release` | 发布前 | 全集 + 性能 + 评测 |
| `ab` | A/B 对比（如新 Prompt） | 全集 ×2 |

## 7. 启动命令

```bash
# 基础
poetry run python -m app.simulation.run --suite smoke

# 完整
poetry run python -m app.simulation.run \
  --suite regression \
  --llm-config configs/sim-claude-sonnet.yaml \
  --report-dir backend/simulation/reports/$(date +%Y-%m-%d) \
  --parallel 4

# A/B（对比新旧 Prompt）
poetry run python -m app.simulation.run \
  --suite regression \
  --ab-config configs/ab-prompt-v3.yaml

# 失败用例复跑
poetry run python -m app.simulation.run \
  --rerun-failed backend/simulation/reports/2026-06-19/failures.json
```

## 8. 报告

输出到 `backend/simulation/reports/<run_id>/`：

```
reports/2026-06-19_153020/
├── index.html                # 总览
├── summary.json              # 机器可读
├── cases/
│   ├── cost-create-with-debt.html
│   └── ...
├── traces/                   # Trace 链路
│   ├── case-001.jsonl
│   └── ...
└── failures.json             # 失败列表（可复跑）
```

`summary.json` 包含：

```json
{
  "run_id": "2026-06-19_153020",
  "suite": "regression",
  "total": 90,
  "passed": 87,
  "failed": 3,
  "pass_rate": 0.967,
  "duration_seconds": 742,
  "total_tokens": 1250000,
  "total_cost_usd": 4.5,
  "skills_invoked": ["create_cost_record", "get_cost_summary", ...]
}
```

## 9. 成本控制

- 2C4G 资源受限，必须控制 LLM 成本。
- 单次 `regression` 跑批上限：5 USD / 1.5M tokens。
- 超出则 CI 阻塞，需人工审批（写入 `.simulation-budget-override`）。
- `nightly` 模式仅在 staging 服务器跑，不在 PR 上跑。

## 10. 仿真失败排查

### 10.1 Prompt 变更导致语义偏移

- 看 trace 的 `llm_call` 完整请求 / 响应。
- 评估是否需要更新用例的 `response_contains`。
- 不允许直接删用例，必须留下迁移注释。

### 10.2 真 LLM 不稳定

- 同一用例跑 3 次，若 2 次失败则视为真 bug；若 1 次失败则视为 flaky，加 `@retry`。
- `temperature: 0` 但仍波动的场景，用 `evaluator_llm`（弱模型判定）替代关键词匹配。

### 10.3 数据竞争

- 仿真并发跑时，确保每条用例用独立 farm_id 或独立 schema。
- `--parallel` 上限 4（2C4G）。

## 11. 与 Evaluation 的衔接

仿真跑完后，可顺手触发 Evaluation：

```bash
poetry run python -m app.simulation.run --suite regression \
  && poetry run python -m app.evaluation.run \
    --input backend/simulation/reports/latest \
    --output backend/evaluation/reports/$(date +%Y-%m-%d)
```

详见 [04_Evaluation评测.md](./04_Evaluation评测.md)。

## 12. 相关文档

- [01_测试金字塔与策略.md](./01_测试金字塔与策略.md)
- [02_回归测试集.md](./02_回归测试集.md)
- [04_Evaluation评测.md](./04_Evaluation评测.md)
- [01_正式设计/01_Agent平台架构](../01_正式设计/01_Agent平台架构.md)
