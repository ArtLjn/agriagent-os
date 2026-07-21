# Agent Tool Candidate Pool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将当前中心化中文硬编码 `rules.py/select_tools` 演进为 registry 驱动的轻量候选池，提升中英文和多轮表达下的 skill 召回稳定性，同时保持 runtime 写安全 fail-closed。

**Architecture:** 不引入新向量库、不引入 embedding 服务、不重写 Agent 主链路。第一版复用 `backend/app/skills/registry/skills.yaml` 中已有的 `description/examples/anti_examples/tags/operations`，新增一个轻量 `CandidateRetriever` 做候选打分；`SkillRouter` 继续负责 policy、预算和读写隔离；`tool_metadata.py` 继续作为执行前安全边界。

**Tech Stack:** Python 3.11、pytest、PyYAML、现有 `SkillRegistry` / `SkillCatalog` / `RouterPolicy`。

---

## 背景和判断

当前 `backend/app/agent/router/rules.py` 同时承担了三类职责：

1. 业务语义召回，例如“人工费”“工资”“茬口”“作业单”。
2. 高置信读写冲突处理，例如人工工资查询不要走财务欠款。
3. 兼容期 tool 预筛选，例如旧 `create_*` / `get_*` 入口。

这种实现短期有效，但长期有明显问题：

- 中心正则会不断增长，新增 skill 或新增表达都要改 Python 代码。
- 中文规则天然覆盖不了英文和混合表达。
- 业务语义、路由召回、风险控制混在一起，容易误以为候选池是安全边界。
- 规则命中失败时只能依赖 fallback，缺少可解释的召回分数和证据。

正确姿态是：候选池只负责“给模型看什么”，runtime guard 负责“允许模型做什么”。本计划只改候选池，不削弱写确认、权限、未知 operation 拦截和缺目标拦截。

## 非目标

- 不做 embedding 检索。
- 不引入外部搜索、RAG、向量库或新服务。
- 不删除 `rules.py`。
- 不迁移 skill 目录。
- 不改变 pending action / pending plan 的安全语义。
- 不让 LLM 路由结果直接绕过 policy 或 runtime guard。

## 目标姿态

```text
User Message
  ↓
RuleIntentClassifier
  - 保留高置信状态/风险/澄清规则
  ↓
CandidateRetriever
  - 从 SkillCatalog / SkillRegistry 的 metadata 召回候选
  - 用 examples、anti_examples、tags、description 打分
  - 支持中文、英文和混合关键词
  ↓
RouterPolicy
  - schema budget
  - read/write mismatch
  - high-risk clarify
  - disabled skill
  ↓
LLM Tool Selection
  ↓
Runtime Guard
  - operation registry validation
  - write_confirm / write_high pending
  - missing target rejection
```

## 文件结构

### 新增

- `backend/app/agent/router/candidate_retriever.py`
  - 负责从 `ToolCandidate` 列表中按用户输入打分并返回候选名称。
  - 不读取数据库，不调用 LLM，不产生副作用。

- `backend/tests/agent/router/test_candidate_retriever.py`
  - 覆盖中英文召回、anti-example 降权、读写风险不过度暴露。

### 修改

- `backend/app/agent/router/models.py`
  - 为 `DisclosureBudget` 增加 `max_retrieved_tools_default`，默认 3。

- `backend/app/agent/router/service.py`
  - 当规则分类没有明确候选时，调用 `CandidateRetriever` 生成 `model_choice_read` 或候选 frames。

- `backend/app/agent/router/policy.py`
  - 保持现有 stop-loss 逻辑，只接收 retriever 生成的候选，不新增安全判断。

- `backend/app/agent/router/rules.py`
  - 不做大删，第一阶段只标注“高置信 override / legacy fallback”，避免继续扩张。

- `backend/app/skills/registry/skills.yaml`
  - 为关键 skill 补少量英文 examples / anti_examples。第一批只覆盖 labor、finance、workers、work_orders、crop_cycle。

- `backend/tests/agent/router/test_router_governance_eval.py`
  - 增加英文和混合表达 eval。

- `backend/tests/test_tool_selector.py`
  - 保留兼容入口测试，确保 `select_tools()` 仍返回旧调用方期望的 tool list。

---

## Task 1: 建立候选池红线测试

**Files:**
- Create: `backend/tests/agent/router/test_candidate_retriever.py`
- Modify: `backend/tests/agent/router/test_router_governance_eval.py`

- [ ] **Step 1: 写 CandidateRetriever 期望行为测试**

创建 `backend/tests/agent/router/test_candidate_retriever.py`：

```python
"""Registry 驱动候选召回测试。"""

from unittest.mock import MagicMock

import pytest

from app.agent.router.candidate_retriever import CandidateRetriever
from app.agent.router.catalog import SkillCatalog

pytestmark = pytest.mark.no_db


def _tool(name: str):
    tool = MagicMock()
    tool.name = name
    tool.description = ""
    return tool


def _catalog(names: list[str]) -> SkillCatalog:
    return SkillCatalog.from_tools([_tool(name) for name in names])


def test_retriever_routes_english_unpaid_wages_to_labor_payment() -> None:
    catalog = _catalog(["manage_cost", "manage_labor_payment", "manage_workers"])

    result = CandidateRetriever().retrieve(
        "how much unpaid worker wages remain",
        catalog.candidates(),
    )

    assert result.selected_names[:1] == ["manage_labor_payment"]
    assert result.scores["manage_labor_payment"] > result.scores["manage_cost"]
    assert result.scores["manage_labor_payment"] > result.scores["manage_workers"]


def test_retriever_uses_anti_examples_to_avoid_worker_profile_for_wages() -> None:
    catalog = _catalog(["manage_labor_payment", "manage_workers"])

    result = CandidateRetriever().retrieve("我说的是工人工资", catalog.candidates())

    assert result.selected_names[:1] == ["manage_labor_payment"]
    assert "manage_workers" not in result.selected_names[:1]


def test_retriever_returns_no_candidate_for_greeting() -> None:
    catalog = _catalog(["manage_cost", "manage_crop_cycle"])

    result = CandidateRetriever().retrieve("hello", catalog.candidates())

    assert result.selected_names == []
```

- [ ] **Step 2: 跑测试确认失败**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 pytest backend/tests/agent/router/test_candidate_retriever.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'app.agent.router.candidate_retriever'
```

- [ ] **Step 3: 在 governance eval 加英文回归样例**

修改 `backend/tests/agent/router/test_router_governance_eval.py` 的 `test_router_top1_capability_accuracy` 参数，增加：

```python
        (
            "how much unpaid worker wages remain",
            "manage_labor_payment",
            "manage_labor_payment",
            "query_payables",
        ),
        (
            "show my worker list",
            "manage_workers",
            "manage_workers",
            "query_workers",
        ),
```

- [ ] **Step 4: 跑 governance eval 确认英文样例失败**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 pytest backend/tests/agent/router/test_router_governance_eval.py -q
```

Expected: 新增英文 case 至少一个失败，证明当前中心中文规则覆盖不足。

---

## Task 2: 实现轻量 CandidateRetriever

**Files:**
- Create: `backend/app/agent/router/candidate_retriever.py`
- Test: `backend/tests/agent/router/test_candidate_retriever.py`

- [ ] **Step 1: 新增 retriever 数据结构和归一化函数**

创建 `backend/app/agent/router/candidate_retriever.py`：

```python
"""Registry 驱动的轻量候选召回。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.agent.router.models import ToolCandidate


_TOKEN_ALIASES = {
    "wage": "工资",
    "wages": "工资",
    "salary": "工资",
    "payroll": "工资",
    "labor": "人工",
    "worker": "工人",
    "workers": "工人",
    "unpaid": "未付",
    "owe": "欠",
    "owed": "欠",
    "debt": "欠款",
    "cost": "成本",
    "expense": "支出",
    "bill": "账单",
    "record": "记录",
    "create": "创建",
    "add": "新增",
    "delete": "删除",
    "remove": "删除",
    "list": "列表",
    "show": "查询",
    "query": "查询",
}


@dataclass(frozen=True)
class CandidateRetrievalResult:
    selected_names: list[str]
    scores: dict[str, float] = field(default_factory=dict)
    evidence: dict[str, dict] = field(default_factory=dict)


class CandidateRetriever:
    """用 registry metadata 对候选工具做轻量召回和排序。"""

    min_score: float = 1.0

    def retrieve(
        self,
        message: str,
        candidates: list[ToolCandidate],
        *,
        limit: int = 3,
    ) -> CandidateRetrievalResult:
        normalized_terms = _normalize_terms(message)
        scored = [
            self._score_candidate(candidate, normalized_terms)
            for candidate in candidates
            if candidate.enabled
        ]
        kept = [
            item for item in scored if item[1] >= self.min_score
        ]
        kept.sort(key=lambda item: (-item[1], item[0].risk != "read", item[0].name))
        selected = kept[:limit]
        return CandidateRetrievalResult(
            selected_names=[candidate.name for candidate, _score, _evidence in selected],
            scores={candidate.name: score for candidate, score, _evidence in scored},
            evidence={candidate.name: evidence for candidate, _score, evidence in selected},
        )

    def _score_candidate(
        self,
        candidate: ToolCandidate,
        terms: set[str],
    ) -> tuple[ToolCandidate, float, dict]:
        score = 0.0
        evidence: dict[str, list[str] | float] = {}

        tag_hits = _hits(terms, candidate.entities)
        intent_hits = _hits(terms, candidate.intents)
        example_hits = _hits(terms, candidate.trigger_examples)
        anti_hits = _hits(terms, candidate.anti_examples)

        score += len(tag_hits) * 1.5
        score += len(intent_hits) * 1.0
        score += len(example_hits) * 2.0
        score -= len(anti_hits) * 3.0

        description_hits = _hits(terms, [candidate.name, candidate.domain, candidate.capability or ""])
        score += len(description_hits) * 0.5

        if candidate.risk == "read":
            score += 0.2

        evidence["tag_hits"] = tag_hits
        evidence["intent_hits"] = intent_hits
        evidence["example_hits"] = example_hits
        evidence["anti_hits"] = anti_hits
        evidence["score"] = score
        return candidate, score, evidence


def _normalize_terms(text: str) -> set[str]:
    lower = text.lower()
    rough_tokens = re.findall(r"[a-z0-9_]+|[\u4e00-\u9fa5]{1,8}", lower)
    terms = set(rough_tokens)
    for token in list(terms):
        alias = _TOKEN_ALIASES.get(token)
        if alias:
            terms.add(alias)
    return terms


def _hits(terms: set[str], values: list[str]) -> list[str]:
    hits: list[str] = []
    for value in values:
        normalized_value = value.lower()
        if any(term and term in normalized_value for term in terms):
            hits.append(value)
    return hits
```

- [ ] **Step 2: 跑 retriever 测试**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 pytest backend/tests/agent/router/test_candidate_retriever.py -q
```

Expected:

```text
3 passed
```

- [ ] **Step 3: 如英文 unpaid wages 分数不够，先补 registry examples，不补 Python if**

修改 `backend/app/skills/registry/skills.yaml`：

```yaml
  - name: manage_labor_payment
    examples:
      - how much unpaid worker wages remain
      - show unpaid labor payments
    anti_examples:
      - create a worker profile
      - list active workers
```

Expected: retriever 测试靠 metadata 通过，不在 retriever 中写 `if "wages" ...`。

---

## Task 3: 将 retriever 接入 SkillRouter fallback

**Files:**
- Modify: `backend/app/agent/router/service.py`
- Modify: `backend/app/agent/router/models.py`
- Test: `backend/tests/agent/router/test_router_governance_eval.py`

- [ ] **Step 1: 扩展 DisclosureBudget**

修改 `backend/app/agent/router/models.py`：

```python
@dataclass(frozen=True)
class DisclosureBudget:
    """工具 schema 暴露预算。"""

    max_tools_default: int = 3
    max_tools_complex: int = 5
    max_write_tools: int = 1
    max_schema_tokens: int = 1800
    max_retrieved_tools_default: int = 3
```

- [ ] **Step 2: 在 SkillRouter 初始化 CandidateRetriever**

修改 `backend/app/agent/router/service.py`：

```python
from app.agent.router.candidate_retriever import CandidateRetriever
```

在 `SkillRouter.__init__` 中增加：

```python
        self._budget = budget or DisclosureBudget()
        self._policy = policy or RouterPolicy(self._budget)
        self._retriever = CandidateRetriever()
```

如果当前构造函数已有 `RouterPolicy(budget)`，保持语义一致，不重复创建不同 budget 实例。

- [ ] **Step 3: 无规则 frames 时使用 retriever 生成候选 frame**

在 `SkillRouter.route()` 中，`frames = self._enrich_frames(...)` 后增加：

```python
        if not frames:
            retrieved = self._retriever.retrieve(
                message,
                catalog.candidates(),
                limit=self._budget.max_retrieved_tools_default,
            )
            if retrieved.selected_names:
                frames = [
                    IntentFrame(
                        domain="general",
                        intent="retrieved_candidate",
                        risk="read",
                        candidate_tools=retrieved.selected_names,
                        confidence=0.6,
                        score=0.6,
                        evidence={
                            "source": "candidate_retriever",
                            "scores": retrieved.scores,
                            "retrieval_evidence": retrieved.evidence,
                        },
                    )
                ]
```

保留 `RouterPolicy` 的读写 mismatch、高危 clarify 和 budget 控制。retriever 只产生候选，不直接选工具。

- [ ] **Step 4: 跑 governance eval**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 pytest backend/tests/agent/router/test_router_governance_eval.py -q
```

Expected:

```text
全部通过，新增英文 case 命中对应 capability。
```

---

## Task 4: 让 select_tools 使用同一条 router 路径，减少 rules.py 扩张

**Files:**
- Modify: `backend/app/agent/router/tool_selector.py`
- Test: `backend/tests/test_tool_selector.py`

- [ ] **Step 1: 新增英文兼容入口测试**

修改 `backend/tests/test_tool_selector.py`，增加：

```python
    def test_english_unpaid_wages_query_uses_labor_payment(self):
        result = select_tools("how much unpaid worker wages remain", _make_tools())
        assert result == ["manage_labor_payment"]

    def test_english_worker_list_query_uses_manage_workers(self):
        result = select_tools("show my worker list", _make_tools())
        assert result == ["manage_workers"]
```

- [ ] **Step 2: 将 select_tools 的无候选 fallback 作为主路径观测点**

保留当前 `rules.py` 命中逻辑，但在 `not candidates` 分支依赖 `SkillRouter().route()` 的 retriever 能力，不新增英文正则。

确认 `backend/app/agent/router/tool_selector.py` 中仍保持：

```python
    if not candidates:
        decision = SkillRouter().route(user_message, all_tools)
        result = decision.selected_tools[:top_k]
```

如果英文测试失败，修 registry metadata 或 retriever scorer，不在 `WRITE_PATTERNS` / `QUERY_TRIGGERS` 里补英文触发词。

- [ ] **Step 3: 跑 selector 测试**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 pytest backend/tests/test_tool_selector.py -q
```

Expected:

```text
全部通过。
```

---

## Task 5: 明确 rules.py 的剩余职责

**Files:**
- Modify: `backend/app/agent/router/rules.py`
- Modify: `backend/app/agent/router/tool_selector.py`

- [ ] **Step 1: 在 rules.py 顶部写清边界**

修改 `backend/app/agent/router/rules.py` 模块注释：

```python
"""Tool 选择高置信兼容规则。

本文件只保留高置信 override、legacy 兼容和少量风险隔离规则。
常规业务语义召回应优先写入 backend/app/skills/registry/skills.yaml
的 examples、anti_examples 和 tags，再由 CandidateRetriever 使用。
禁止为了新话术持续扩张中心正则表。
"""
```

- [ ] **Step 2: 在 tool_selector.py 日志中区分 rule 和 retriever**

保持已有日志字段，确保当 fallback 到 `SkillRouter` 时，日志输出包含：

```python
decision.fallback
decision.reason
decision.evidence
```

不要在日志中打印完整用户隐私内容，只保留 `user_message[:80]`。

- [ ] **Step 3: 跑 lint**

Run:

```bash
ruff check backend/app/agent/router/rules.py backend/app/agent/router/tool_selector.py
```

Expected:

```text
All checks passed!
```

---

## Task 6: 增加候选池治理文档和评测入口

**Files:**
- Create: `docs/agent/tool-candidate-pool.md`
- Modify: `AGENTS.md`

- [ ] **Step 1: 新增治理文档**

创建 `docs/agent/tool-candidate-pool.md`：

```markdown
# Tool Candidate Pool Governance

## 职责

候选池只决定每轮向模型暴露哪些 skill/tool 候选，不决定工具是否允许执行。

## 事实源

常规业务表达写入 `backend/app/skills/registry/skills.yaml`：

- `description`
- `examples`
- `anti_examples`
- `tags`
- `operations.*.risk`

## 禁止事项

- 禁止为了单个新话术直接扩张 `rules.py` 中心正则。
- 禁止把候选池命中当作写操作授权。
- 禁止绕过 `tool_metadata.py` 的 operation risk 和 pending 校验。

## 新增话术流程

1. 先加 eval case。
2. 再补 registry examples / anti_examples / tags。
3. 只有状态机、pending、确认、取消、高危删除等高置信规则才允许改 `rules.py`。
4. 跑 router governance、selector 和 runtime guard 测试。
```

- [ ] **Step 2: 在 AGENTS.md 导航加入口**

在 `AGENTS.md` 快速导航表增加：

```markdown
| 了解 Tool 候选池治理 | docs/agent/tool-candidate-pool.md |
```

- [ ] **Step 3: 跑 Guide+Sensor 配对检查**

Run:

```bash
bash scripts/check-guide-sensor-pairing.sh
```

Expected:

```text
所有硬性规则均有对应检查脚本，Guide+Sensor 配对完整
```

---

## Task 7: 回归验证和提交

**Files:**
- Verify only

- [ ] **Step 1: 跑候选池相关测试**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 pytest \
  backend/tests/agent/router/test_candidate_retriever.py \
  backend/tests/agent/router/test_router_governance_eval.py \
  backend/tests/test_tool_selector.py \
  -q
```

Expected:

```text
全部通过。
```

- [ ] **Step 2: 跑 runtime 写安全回归**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 pytest backend/tests/agent/test_tool_executor_metadata.py -q
```

Expected:

```text
全部通过。候选池改造不得影响 pending、未知 operation 拦截和缺目标拦截。
```

- [ ] **Step 3: 跑 lint 和架构检查**

Run:

```bash
ruff check \
  backend/app/agent/router/candidate_retriever.py \
  backend/app/agent/router/service.py \
  backend/app/agent/router/models.py \
  backend/app/agent/router/rules.py \
  backend/app/agent/router/tool_selector.py \
  backend/tests/agent/router/test_candidate_retriever.py \
  backend/tests/agent/router/test_router_governance_eval.py \
  backend/tests/test_tool_selector.py

bash scripts/check-layer-deps.sh
bash scripts/check-complexity-budget.sh
```

Expected:

```text
ruff 通过。
架构和复杂度检查不出现新增 hard error；既有 warning 在 PR 描述中说明。
```

- [ ] **Step 4: 提交**

Run:

```bash
git add \
  backend/app/agent/router/candidate_retriever.py \
  backend/app/agent/router/service.py \
  backend/app/agent/router/models.py \
  backend/app/agent/router/rules.py \
  backend/app/agent/router/tool_selector.py \
  backend/app/skills/registry/skills.yaml \
  backend/tests/agent/router/test_candidate_retriever.py \
  backend/tests/agent/router/test_router_governance_eval.py \
  backend/tests/test_tool_selector.py \
  docs/agent/tool-candidate-pool.md \
  AGENTS.md

git commit -m "feat: 引入 registry 驱动 tool 候选池"
```

Expected:

```text
提交只包含候选池实现、测试和治理文档，不包含工作区未跟踪数据文件。
```

---

## 验收标准

- 英文 `how much unpaid worker wages remain` 能召回 `manage_labor_payment.query_payables`。
- 英文 `show my worker list` 能召回 `manage_workers.query_workers`。
- 中文现有 governance eval 不降级。
- `select_tools()` 兼容入口仍返回旧调用方预期的 list-like 结果。
- 未知 operation 仍拒绝，不创建 pending。
- 写操作缺目标仍拒绝，不创建不可执行 pending。
- 新增话术优先补 registry metadata 和 eval，不继续扩张中心业务正则。

## 风险和止损

- 如果 retriever 误召回写工具，`RouterPolicy` 必须继续用 read/write mismatch 和 write budget 截断。
- 如果英文召回需要大量 alias，先补 `skills.yaml` examples，不增加中心 regex。
- 如果简单 scorer 无法区分相邻 skill，下一阶段再考虑 BM25；本阶段不引入 embedding。
- 如果 `rules.py` 与 retriever 结果冲突，第一阶段仍以高置信 rule 为优先，避免破坏已验证中文路径。

## 面试表达沉淀

企业级 Agent 的候选池不是安全机制，而是上下文预算和工具选择准确率机制。正确边界是：

```text
Candidate Pool decides what the model can see.
Runtime Guard decides what the model is allowed to do.
Eval and Trace decide whether the system is improving.
```

落地时不要把全部复杂度一次做满；先用 registry metadata 取代中心硬编码，再用评测驱动逐步升级召回算法。
