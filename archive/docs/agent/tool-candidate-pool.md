# Tool 候选池治理说明

---
last_updated: 2026-07-21
status: active
---

## 目标

Tool 候选池只解决一个问题：在只读或查询型请求里，基于 Skill Registry 元数据缩小本轮暴露给模型的工具范围。

它不是安全边界，也不是新的业务意图分类器。写入确认、读写隔离、高风险澄清、未知 operation 拦截和执行前权限检查仍由 `RouterPolicy`、runtime metadata 和 tool executor 负责。

## 当前实现

候选池入口是 `backend/app/agent/router/candidate_retriever.py`。

数据来源只允许使用 `SkillCatalog` 中已经归一化的 metadata：

- `tags`
- `examples`
- `anti_examples`
- `intents`
- capability / operation 标识

`SkillRouter` 只在规则分类器没有产生明确 frame，且用户输入包含查询型提示时调用候选池。这样可以避免裸规划意向和不完整写意图被候选池误当成只读查询。

## 设计边界

允许做：

- 给 registry 增加能代表真实用户表达的正例和反例。
- 调整通用打分权重，例如 examples、tags、anti_examples 的相对权重。
- 增加跨语言的通用词归一化，但必须是工具无关的词义映射。
- 增加 eval case，覆盖中英文、多轮纠偏、无工具、写入缺参。

禁止做：

- 在 `CandidateRetriever` 中写 `if tool == "xxx"` 这种 skill 特定逻辑。
- 用候选池绕过 `RouterPolicy` 的读写 mismatch 检查。
- 让候选池直接选择 write operation。
- 为单个用户句子无限追加 Python 关键词规则。
- 把 pending action 或 pending plan 状态放进候选池。

## 正确流程

```text
用户输入
  ↓
RuleIntentClassifier
  - 高置信读写意图
  - 写入缺参澄清
  - 明显无工具保护
  ↓
CandidateRetriever
  - 仅在无明确 frame 且像查询请求时启用
  - 基于 registry metadata 打分
  ↓
RouterPolicy
  - schema budget
  - read/write mismatch
  - disabled skill
  - high-risk clarify
  ↓
LLM tool binding
  ↓
Runtime guard
  - operation risk
  - pending confirmation
  - missing target rejection
```

## 测试要求

修改候选池或 registry examples 时，至少运行：

```bash
PYTHONDONTWRITEBYTECODE=1 pytest backend/tests/agent/router/test_candidate_retriever.py backend/tests/agent/router/test_router_governance_eval.py backend/tests/test_tool_selector.py -q
PYTHONDONTWRITEBYTECODE=1 pytest backend/tests/agent/test_runtime_router_binding.py backend/tests/agent/test_tool_executor_metadata.py backend/tests/agent/test_tool_choice_required.py -q
```

如果改动影响写入、多轮上下文或 pending 行为，还要增加对应多轮回归测试，证明模型即使命中候选工具，也不能跳过确认或执行未知 operation。
