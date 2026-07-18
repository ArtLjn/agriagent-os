# Backend Directory Consolidation Round 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成第一批低风险 backend 目录收束，放宽 500 行硬门禁，并把 seed/scripts 小模块归入更合适的 ops/shared 边界。

**Architecture:** 本轮只做低风险迁移：文档和检查脚本先承认生产 Python 文件 1000 行以内可接受；`backend/app/ops` 承接初始化 seed 与 schema audit 工具；`backend/app/shared` 只承接无需业务语义的轻量基础设施。兼容入口不保留，所有生产和测试引用直接改到新路径。

**Tech Stack:** FastAPI backend、SQLAlchemy、Pydantic、ruff、pytest、bash harness scripts。

---

### Task 1: 规则与检查脚本对齐

**Files:**
- Modify: `AGENTS.md`
- Modify: `scripts/check-complexity-budget.sh`
- Modify: `scripts/check-layer-deps.sh`
- Modify: `docs/specs/2026-07-12-agent-module-remediation.md`
- Modify: `docs/specs/2026-07-12-backend-bloat-diagnosis.md`
- Modify: `docs/specs/2026-07-14-backend-directory-redesign.md`
- Modify: `docs/plans/current-sprint.md`
- Modify: `docs/farm-manager-design-spec/README.md`
- Modify: `docs/farm-manager-design-spec/README_en.md`
- Modify: `docs/farm-manager-design-spec/04_相关规范/05_Python编码规范.md`
- Modify: `docs/farm-manager-design-spec/04_相关规范/06_防污染与文档同步规范.md`

- [ ] **Step 1: 将生产 Python 文件阈值改成 1000 行硬门禁**

Run: `rg -n "单文件 ≤ 500|≤ 500 行|超过 500|上限 500|> 500|500 行预算" AGENTS.md docs scripts`
Expected: 列出需要同步的旧规则，不包含业务数值字段。

- [ ] **Step 2: 修改复杂度脚本**

Update `backend/app` 的 `.py` 限制为 1000；500-1000 仅观察输出；`backend/tests` 继续按 500 行观察，避免本轮扩大测试目录策略。

- [ ] **Step 3: 修改层级检查脚本**

Update `scripts/check-layer-deps.sh` 的 Python 文件大小检查：`>1000` 非 baseline 才失败，`500-1000` 输出观察警告。

- [ ] **Step 4: 同步文档措辞**

把会误导后续 Agent 继续为 500 行硬拆的描述改为“生产 Python 文件 1000 行以内可接受，500-1000 按职责判断；单函数建议 50-80 行观察”。

### Task 2: seed/scripts 归入 ops

**Files:**
- Create: `backend/app/ops/__init__.py`
- Move: `backend/app/core/seed.py` -> `backend/app/ops/bootstrap_seed.py`
- Move: `backend/app/seed/system_crop_templates.py` -> `backend/app/ops/system_crop_templates.py`
- Move: `backend/app/scripts/schema_hardening_audit.py` -> `backend/app/ops/schema_hardening_audit.py`
- Delete: `backend/app/seed/__init__.py`
- Delete: `backend/app/scripts/__init__.py`
- Modify: `backend/app/bootstrap/lifespan.py`
- Modify: `backend/alembic/versions/20260619_seed_system_crop_templates.py`
- Modify: `backend/tests/seed/test_system_crop_templates.py`
- Modify: `backend/tests/test_schema_hardening_audit.py`
- Modify: `backend/docs/schema-hardening-migration.md`
- Modify: `docs/design/crop-template-system-library.md`
- Modify: `docs/specs/2026-07-15-system-crop-template-crud.md`

- [ ] **Step 1: 移动文件并直接改引用**

Run: `rg -n "app\\.seed|app\\.scripts|app\\.core\\.seed|from app\\.core\\.seed" backend docs openspec`
Expected: 旧路径只出现在历史计划或需要更新的文档中。

- [ ] **Step 2: 删除旧目录空壳**

Remove `backend/app/seed` 和 `backend/app/scripts` 下的 `__init__.py`，不创建兼容 re-export。

- [ ] **Step 3: 运行相关测试**

Run: `cd backend && PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider tests/seed/test_system_crop_templates.py tests/test_schema_hardening_audit.py -q`
Expected: PASS。

### Task 3: core/shared 低风险收束

**Files:**
- Create: `backend/app/shared/__init__.py`
- Move: `backend/app/core/compat.py` -> `backend/app/shared/compatibility.py`
- Modify imports in active backend app/tests files that use `app.core.compat`
- Delete empty `backend/app/core/__init__.py` only if no `from app.core import ...` import requires it

- [ ] **Step 1: 迁移兼容工具到 shared**

Run: `rg -n "app\\.core\\.compat|from app\\.core\\.compat" backend/app backend/tests`
Expected: 只命中 active import，可逐个改为 `app.shared.compatibility`。

- [ ] **Step 2: 删除旧 core 兼容入口**

Run: `rg -n "app\\.core\\.compat|from app\\.core\\.compat" backend/app backend/tests`
Expected: 无命中。

- [ ] **Step 3: 运行相关测试**

Run: `cd backend && PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider tests/memory/test_maybe_summarize.py tests/memory/test_memory_service.py -q`
Expected: PASS。

### Task 4: 文档追踪与全量验证

**Files:**
- Modify: `docs/specs/2026-07-18-backend-directory-consolidation-design.md`
- Modify: `docs/specs/2026-07-12-backend-bloat-diagnosis.md`
- Modify: `docs/specs/2026-07-14-backend-directory-redesign.md`

- [ ] **Step 1: 记录本轮完成项和剩余边界**

Add round1 状态：规则阈值已切换、`ops` 建立、`shared.compatibility` 建立；`models/schemas` 暂不大迁移，仅后续按领域处理。

- [ ] **Step 2: 运行要求的验证命令**

Run:
`PYTHONDONTWRITEBYTECODE=1 ruff check --no-cache backend/app backend/tests`
`cd backend && PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider tests/seed/test_system_crop_templates.py tests/test_schema_hardening_audit.py tests/memory/test_maybe_summarize.py tests/memory/test_memory_service.py -q`
`bash scripts/check-complexity-budget.sh`
`bash scripts/check-layer-deps.sh`

- [ ] **Step 3: 提交并创建 ready PR**

Run:
`git status --short`
`git add <changed files>`
`git commit -m "refactor: 收束 backend 目录规则和低风险模块"`
`git push -u origin codex/backend-directory-consolidation-round1`
`gh pr create --fill --ready`
