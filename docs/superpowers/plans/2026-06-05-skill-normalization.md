# Skill Normalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish a project-local Skill authoring standard inspired by Agent Skills, then enforce it with tests and migrate the riskiest farm-manager Skills.

**Architecture:** Keep runtime tool names in snake_case for compatibility, while documenting each Skill with a stable hybrid format: frontmatter metadata, behavioral sections, runtime strategy, and failure handling. Add a repository-local validator so documentation, schema intent, and runtime behavior stop drifting apart.

**Tech Stack:** Python 3.11, pytest, Markdown skill files under `backend/app/agent/skills`, existing shell harness under `scripts/`.

---

## File Structure

- Modify `.claude/rules/skill-writing.md` to define the new hybrid Skill standard.
- Create `backend/app/agent/skills/doc_validator.py` as a focused parser/validator for `skill.md` files.
- Modify `backend/tests/skills/test_skill_docs.py` to use the validator and assert required sections/metadata.
- Create `scripts/check-skill-docs.sh` as a CI-friendly Sensor for the Skill guide.
- Modify `scripts/harness-check.sh` to run the Skill doc checker.
- Modify all existing Skill docs with the minimal new contract sections:
  - `backend/app/agent/skills/cost-analytics/skill.md`
  - `backend/app/agent/skills/create-cost-record/skill.md`
  - `backend/app/agent/skills/cost-summary/skill.md`
  - `backend/app/agent/skills/create-crop-cycle/skill.md`
  - `backend/app/agent/skills/create-crop-template/skill.md`
  - `backend/app/agent/skills/create-operation-work-order/skill.md`
  - `backend/app/agent/skills/crop-cycle/skill.md`
  - `backend/app/agent/skills/farm-logs/skill.md`
  - `backend/app/agent/skills/update-crop-cycle/skill.md`
  - `backend/app/agent/skills/farm-status/skill.md`
  - `backend/app/agent/skills/get-labor-payables/skill.md`
  - `backend/app/agent/skills/get-operation-work-orders/skill.md`
  - `backend/app/agent/skills/log-farm-activity/skill.md`
  - `backend/app/agent/skills/settle-debt/skill.md`
  - `backend/app/agent/skills/settle-labor-payment/skill.md`
  - `backend/app/agent/skills/update-crop-stage/skill.md`
  - `backend/app/agent/skills/update-operation-work-order/skill.md`
  - `backend/app/agent/skills/weather/skill.md`
  - `backend/app/agent/skills/web_search/skill.md`

## Task 1: Define And Enforce Skill Doc Contract

**Files:**
- Modify: `.claude/rules/skill-writing.md`
- Create: `backend/app/agent/skills/doc_validator.py`
- Modify: `backend/tests/skills/test_skill_docs.py`

- [ ] **Step 1: Write failing validator tests**

Replace `backend/tests/skills/test_skill_docs.py` with validator unit tests that import `validate_skill_doc` and check contract behavior without scanning all existing docs yet:

```python
"""Skill 文档结构测试。"""

from pathlib import Path

from app.agent.skills.doc_validator import validate_skill_doc


def test_validator_requires_runtime_strategy(tmp_path):
    doc = tmp_path / "skill.md"
    doc.write_text(
        """---
name: demo_skill
type: read-only
description: 查询示例数据。
triggers:
  - 示例
parameters:
  type: object
  properties: {}
  required: []
---

# 示例

## 何时使用
用户查询示例时使用。

## 不要使用
用户要写入时不要使用。

## 参数推断
无参数。

## 缺参策略
无参数。

## 示例
- 用户：“示例” -> `demo_skill()`
""",
        encoding="utf-8",
    )

    result = validate_skill_doc(doc)

    assert "缺少章节：## Runtime 策略" in result.errors


def test_validator_accepts_tool_name_alias_for_snake_case_runtime(tmp_path):
    doc = tmp_path / "skill.md"
    doc.write_text(
        """---
name: demo-skill
tool_name: demo_skill
type: read-only
description: 查询示例数据。
triggers:
  - 示例
parameters:
  type: object
  properties: {}
  required: []
---

# 示例

## 何时使用
用户查询示例时使用。

## 不要使用
用户要写入时不要使用。

## 参数推断
无参数。

## 缺参策略
无参数。

## Runtime 策略
- permission: read
- direct_call: false
- direct_return: false
- cache: none

## 失败处理
- 参数缺失：返回中文提示，不暴露内部异常。

## 示例
- 用户：“示例” -> `demo_skill()`
""",
        encoding="utf-8",
    )

    result = validate_skill_doc(doc)

    assert result.errors == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
.venv/bin/python -m pytest tests/skills/test_skill_docs.py -q
```

Expected: FAIL because `app.agent.skills.doc_validator` does not exist or current docs miss new sections.

- [ ] **Step 3: Implement minimal validator**

Create `backend/app/agent/skills/doc_validator.py`:

```python
"""Skill 文档结构校验器。"""

from dataclasses import dataclass
from pathlib import Path
import re


REQUIRED_SECTIONS = [
    "## 何时使用",
    "## 不要使用",
    "## 参数推断",
    "## 缺参策略",
    "## Runtime 策略",
    "## 失败处理",
    "## 示例",
]

REQUIRED_FRONTMATTER_KEYS = [
    "name",
    "type",
    "description",
    "triggers",
    "parameters",
]


@dataclass(frozen=True)
class SkillDocValidationResult:
    path: Path
    errors: list[str]


def validate_skill_doc(path: Path) -> SkillDocValidationResult:
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []
    frontmatter = _extract_frontmatter(text)
    if frontmatter is None:
        errors.append("缺少 YAML frontmatter")
    else:
        for key in REQUIRED_FRONTMATTER_KEYS:
            if not re.search(rf"^{re.escape(key)}:", frontmatter, re.MULTILINE):
                errors.append(f"frontmatter 缺少字段：{key}")
        if re.search(r"^name:\s*[a-z0-9]+-[a-z0-9-]+", frontmatter, re.MULTILINE):
            if not re.search(r"^tool_name:\s*[a-z0-9_]+", frontmatter, re.MULTILINE):
                errors.append("kebab-case name 必须提供 snake_case tool_name")

    for section in REQUIRED_SECTIONS:
        if section not in text:
            errors.append(f"缺少章节：{section}")

    return SkillDocValidationResult(path=path, errors=errors)


def _extract_frontmatter(text: str) -> str | None:
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end == -1:
        return None
    return text[4:end]
```

- [ ] **Step 4: Update guide**

Rewrite `.claude/rules/skill-writing.md` so it says:

```markdown
# Skill 书写规范

## 目标
Skill 文档采用项目内 hybrid contract：兼容现有 snake_case Tool Runtime，同时吸收 Agent Skills 的 progressive disclosure 思路。`skill.md` 负责告诉模型何时使用、何时不用、如何处理歧义；Python/Pydantic 负责真实参数校验；runtime 负责权限、缓存、直达策略。

## 目录结构
...

## skill.md 必填结构
frontmatter 必须包含：`name`、`type`、`description`、`triggers`、`parameters`。如果 `name` 使用 kebab-case，必须提供 `tool_name` 指向现有 snake_case runtime tool。

正文必须包含：
- `## 何时使用`
- `## 不要使用`
- `## 参数推断`
- `## 缺参策略`
- `## Runtime 策略`
- `## 失败处理`
- `## 示例`

## Runtime 策略
必须显式写出：
- `permission`: read / write_confirm / write
- `direct_call`: true / false
- `direct_return`: true / false
- `cache`: none / ttl seconds / invalidation groups

## 边界规则
- Skill 原始输出不等于最终用户回复；是否可直返由 runtime 控制。
- 写操作必须走 pending confirmation。
- 缺参和校验失败必须返回中文业务提示，不暴露 Pydantic/SQLAlchemy 内部异常。
- 高风险业务规则必须在 Python/Pydantic 中校验，不能只写在 prompt 或 skill.md。
```

Keep the existing implementation/test conventions below that text if still relevant.

- [ ] **Step 5: Run tests**

Run:

```bash
cd backend
.venv/bin/python -m pytest tests/skills/test_skill_docs.py -q
```

Expected: PASS for validator unit tests.

## Task 2: Migrate All Existing Skill Docs

**Files:**
- Modify: `backend/app/agent/skills/create-cost-record/skill.md`
- Modify: `backend/app/agent/skills/cost-summary/skill.md`
- Modify: `backend/app/agent/skills/crop-cycle/skill.md`
- Modify: `backend/app/agent/skills/update-crop-cycle/skill.md`
- Modify: `backend/app/agent/skills/farm-status/skill.md`
- Modify every other `backend/app/agent/skills/*/skill.md` reported by `tests/skills/test_skill_docs.py`

- [ ] **Step 1: Add full Skill docs contract test and run it to see missing sections**

Add this test to `backend/tests/skills/test_skill_docs.py`:

```python
def test_all_skill_docs_follow_hybrid_contract():
    skill_root = Path(__file__).parents[2] / "app" / "agent" / "skills"
    docs = sorted(skill_root.glob("*/skill.md"))

    assert docs, "未发现 skill.md"
    errors = {}
    for doc in docs:
        result = validate_skill_doc(doc)
        if result.errors:
            errors[str(doc.relative_to(skill_root))] = result.errors

    assert not errors
```

Run:

```bash
cd backend
.venv/bin/python -m pytest tests/skills/test_skill_docs.py -q
```

Expected: FAIL listing docs missing `Runtime 策略` or `失败处理`.

- [ ] **Step 2: Add Runtime 策略 and 失败处理 to the five highest-risk docs**

Append or insert these sections before `## 示例`:

```markdown
## Runtime 策略
- permission: write_confirm
- direct_call: false
- direct_return: false
- cache: 写入成功后失效 cost_summary、cost_analytics、get_farm_status

## 失败处理
- 金额缺失或无效：提示用户补充有效金额。
- 金额超过 10000000：不要写入，提示用户确认金额。
- 分类缺失：提示用户补充分类或选择明显分类。
- 缺少可信农场上下文：拒绝写入。
- 数据库异常：返回中文失败提示，不暴露内部异常。
```

- [ ] **Step 3: Add Runtime 策略 and 失败处理 to cost-summary**

Insert:

```markdown
## Runtime 策略
- permission: read
- direct_call: true
- direct_return: false
- cache: 300 秒，写入账务后失效

## 失败处理
- 无记录：返回“暂无成本或收入记录”。
- 日期缺失：默认本月。
- 不知道 cycle_id：不传 cycle_id，查询当前农场全部记录。
- 查询异常：返回中文失败提示，不暴露内部异常。
```

- [ ] **Step 4: Add Runtime 策略 and 失败处理 to crop-cycle**

Insert:

```markdown
## Runtime 策略
- permission: read
- direct_call: false
- direct_return: false
- cache: 600 秒

## 失败处理
- 缺少 cycle_id：先返回当前农场状态供用户选择，不暴露参数校验错误。
- 指定 cycle_id 不存在：返回未找到对应种植周期。
- 查询异常：返回中文失败提示，不暴露内部异常。
```

- [ ] **Step 5: Add Runtime 策略 and 失败处理 to update-crop-cycle**

Insert:

```markdown
## Runtime 策略
- permission: write_confirm
- direct_call: false
- direct_return: false
- cache: 执行成功后失效 crop_cycle、get_farm_status

## 失败处理
- 缺少 start_date：追问新的开始日期。
- 日期格式无效：提示使用 YYYY-MM-DD。
- 无法定位目标茬口：提示提供茬口 ID、作物名或完整茬口名。
- 匹配多个茬口：列出候选并让用户选择。
- 数据库异常：返回中文失败提示，不暴露内部异常。
```

- [ ] **Step 6: Add Runtime 策略 and 失败处理 to farm-status**

Insert:

```markdown
## Runtime 策略
- permission: read
- direct_call: true
- direct_return: true
- cache: 300 秒，相关写入后失效

## 失败处理
- 缺少可信农场上下文：提示无法获取农场信息。
- 服务异常：返回“获取农场状态失败，请稍后再试。”
```

- [ ] **Step 7: Add minimal frontmatter where missing**

For docs without frontmatter, add frontmatter that matches the runtime tool name and existing parameter expectations. Use snake_case `name` unless the directory name is already the desired public name. Required shape:

```markdown
---
name: get_operation_work_orders
type: read-only
description: 查询农事作业单。
triggers:
  - 作业单
parameters:
  type: object
  properties: {}
  required: []
---
```

Do this for any doc reported with `缺少 YAML frontmatter`.

- [ ] **Step 8: Add minimal Runtime 策略 / 失败处理 to remaining docs**

For every remaining doc reported by `tests/skills/test_skill_docs.py`, add:

```markdown
## Runtime 策略
- permission: read
- direct_call: false
- direct_return: false
- cache: none

## 失败处理
- 参数缺失：返回中文提示，不暴露内部异常。
- 服务异常：返回中文失败提示，不暴露内部异常。
```

Adjust `permission` to `write_confirm` for write-operation docs and set cache information to the current implementation when obvious.

- [ ] **Step 9: Run Skill doc tests**

Run:

```bash
cd backend
.venv/bin/python -m pytest tests/skills/test_skill_docs.py -q
```

Expected: PASS for all docs.

## Task 3: Add CI-Friendly Skill Sensor

**Files:**
- Create: `scripts/check-skill-docs.sh`
- Modify: `scripts/harness-check.sh`

- [ ] **Step 1: Write failing harness expectation**

Run:

```bash
bash scripts/check-skill-docs.sh
```

Expected: FAIL because the script does not exist.

- [ ] **Step 2: Create script**

Create `scripts/check-skill-docs.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR/backend"

.venv/bin/python -m pytest tests/skills/test_skill_docs.py -q
```

- [ ] **Step 3: Make script executable**

Run:

```bash
chmod +x scripts/check-skill-docs.sh
```

- [ ] **Step 4: Wire into harness**

In `scripts/harness-check.sh`, add:

```bash
bash scripts/check-skill-docs.sh
```

near the other guide/sensor checks.

- [ ] **Step 5: Run script**

Run:

```bash
bash scripts/check-skill-docs.sh
```

Expected: PASS.

- [ ] **Step 6: Run focused regression**

Run:

```bash
cd backend
.venv/bin/python -m pytest tests/skills/test_skill_docs.py tests/test_direct_tool_routing.py tests/test_mixed_tool_results.py tests/test_parse_cost_with_llm.py tests/test_skills.py -q
```

Expected: PASS.

## Task 4: Final Review And Cleanup

**Files:**
- Inspect all files changed in Tasks 1-3.

- [ ] **Step 1: Run status and diff**

Run:

```bash
git status --short
git diff -- .claude/rules/skill-writing.md backend/app/agent/skills/doc_validator.py backend/tests/skills/test_skill_docs.py scripts/check-skill-docs.sh scripts/harness-check.sh backend/app/agent/skills/create-cost-record/skill.md backend/app/agent/skills/cost-summary/skill.md backend/app/agent/skills/crop-cycle/skill.md backend/app/agent/skills/update-crop-cycle/skill.md backend/app/agent/skills/farm-status/skill.md
```

Expected: only intended files changed for this plan, plus pre-existing unrelated workspace changes remain untouched.

- [ ] **Step 2: Run final focused tests**

Run:

```bash
bash scripts/check-skill-docs.sh
cd backend
.venv/bin/python -m pytest tests/test_direct_tool_routing.py tests/test_mixed_tool_results.py tests/test_parse_cost_with_llm.py tests/test_skills.py -q
```

Expected: PASS.

- [ ] **Step 3: Report residual risks**

Report that this phase enforces docs and performs minimal contract migration for all existing Skill docs, but does not deeply rewrite every Skill implementation for output contract or Pydantic/source-of-truth generation.

---

## Self-Review

- Spec coverage: The plan covers project-local Skill contract, validation, all existing Skill docs, and CI sensor.
- Placeholder scan: No TBD/TODO placeholders remain.
- Type consistency: Validator API is `validate_skill_doc(path: Path) -> SkillDocValidationResult`; tests use the same signature.
