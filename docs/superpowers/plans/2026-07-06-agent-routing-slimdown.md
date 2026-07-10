# Agent Routing Slimdown Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让普通读请求交给主模型选择工具，同时保留写操作和权限护栏。

**Architecture:** Runtime 使用 `SkillCatalog` 生成 enabled read tool 候选池；写操作仍由 `SkillRouter` 生成确认计划。`select_tools` 降级为兼容薄层，不再维护查询类强绑定和小模型兜底。普通 query 不再走 deterministic direct routing。

**Tech Stack:** FastAPI, LangGraph runtime, LangChain tools, pytest, ruff。

---

### Task 1: 改写 runtime 读请求契约

**Files:**
- Modify: `backend/tests/agent/test_runtime_router_binding.py`
- Modify: `backend/app/agent/runtime/nodes.py`

- [ ] **Step 1: 保留普通读请求绑定只读工具池测试**

确认 `test_read_query_exposes_read_tools_for_model_choice` 断言普通读请求 `tool_choice == "auto"`，且绑定 read tools，不包含写工具。

- [ ] **Step 2: 移除 runtime 对查询类 force_binding 的依赖**

`_route_tools()` 不再通过 `_select_tools()` 为读请求计算 `force_binding`。写请求的确认仍来自 `SkillRouter` 的 `IntentFrame.requires_confirmation`。

- [ ] **Step 3: 运行 runtime 测试**

Run: `cd backend && ./.venv/bin/python -m pytest tests/agent/test_runtime_router_binding.py -q`

Expected: 全部通过。

### Task 2: 降级 select_tools 为兼容薄层

**Files:**
- Modify: `backend/app/agent/tool_selector.py`
- Modify: `backend/tests/agent/test_select_tools_force_binding.py`
- Modify: `backend/tests/agent/eval/test_baseline.py`
- Modify: `backend/tests/agent/eval/test_pollution_differential.py`
- Modify: `backend/tests/agent/eval/test_multiturn_pollution.py`

- [ ] **Step 1: 删除 LLMIntentClassifier 小模型兜底**

移除 `OpenAI` 依赖和 `LLMIntentClassifier` 类，`select_tools()` 参数中移除 `intent_classifier`。

- [ ] **Step 2: 删除查询类 force_binding**

`select_tools()` 不再读取 `QUERY_INTENT_FORCE_BINDING`，读查询返回普通 `tools`，`force_binding` 仅保留空集合。

- [ ] **Step 3: 保留写规则筛选**

保留 `WRITE_PATTERNS`、写读冲突裁剪、disabled skill 过滤和 `SkillRouter` fallback。

- [ ] **Step 4: 更新测试名称和断言**

查询类测试改为断言 `force_binding` 为空；写/闲聊测试保留。

- [ ] **Step 5: 运行 select_tools 测试**

Run: `cd backend && ./.venv/bin/python -m pytest tests/agent/test_select_tools_force_binding.py tests/agent/eval/test_baseline.py tests/agent/eval/test_pollution_differential.py tests/agent/eval/test_multiturn_pollution.py -q`

Expected: 全部通过。

### Task 3: 移除普通读请求 direct routing

**Files:**
- Modify: `backend/app/agent/runtime/nodes.py`
- Modify: `backend/app/agent/runtime/direct_routing.py`
- Modify: `backend/tests/test_direct_tool_routing.py`

- [ ] **Step 1: 删除 `_direct_query_response()` 调用**

Runtime 不再在 initial LLM 前为普通 query 直接构造 tool call。

- [ ] **Step 2: 保留安全过滤函数**

保留 `filter_tool_calls_by_selected()` 和 direct tool result final answer 相关函数；它们属于工具调用白名单和最终回复优化，不是普通读请求预路由。

- [ ] **Step 3: 更新 direct routing 测试**

旧的 “skip initial llm call” 测试改为 “query 也进入 LLM 并绑定候选工具”。

- [ ] **Step 4: 运行 direct routing 相关测试**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_direct_tool_routing.py tests/agent/test_runtime_router_binding.py -q`

Expected: 全部通过。

### Task 4: 验证 skillify-sdk 保留但不删除

**Files:**
- Modify: `docs/superpowers/specs/2026-07-06-agent-routing-slimdown-design.md`

- [ ] **Step 1: 确认引用仍存在**

Run: `rg -n "from skillify|skillify-sdk|skillify @" backend/app backend/requirements.txt backend/Dockerfile deploy/server-sync.sh`

Expected: 能看到 Skill 注册和部署依赖引用，因此本期不删除。

- [ ] **Step 2: 不修改 SDK 目录**

确认 `git status --short backend/skillify-sdk` 没有删除或修改。

### Task 5: 最终验证

**Files:**
- Verify: backend tests and lint

- [ ] **Step 1: 运行相关测试**

Run: `cd backend && ./.venv/bin/python -m pytest tests/agent/test_runtime_router_binding.py tests/agent/router/test_skill_router.py tests/agent/test_select_tools_force_binding.py tests/agent/test_tool_choice_required.py tests/test_direct_tool_routing.py -q`

Expected: 全部通过。

- [ ] **Step 2: 运行 ruff**

Run: `cd backend && ./.venv/bin/ruff check app/agent/runtime/nodes.py app/agent/runtime/direct_routing.py app/agent/tool_selector.py tests/agent/test_runtime_router_binding.py tests/test_direct_tool_routing.py`

Expected: `All checks passed!`

- [ ] **Step 3: 清理污染并跑复杂度预算**

Run: `find backend -type d -name '__pycache__' -prune -exec rm -rf {} +; find backend -type f \( -name '*.pyc' -o -name '.DS_Store' \) -delete; bash scripts/check-complexity-budget.sh`

Expected: exit 0；历史 warning 可存在，但不得出现工作区污染文件。
