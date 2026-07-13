## 1. Registry Skeleton

- [x] 1.1 新增 `backend/app/agent/skills/registry/domains.yaml`，定义 finance、crop、farm、operation、labor、log、settings、external 等 domain、owner 和默认策略。
- [x] 1.2 新增 `backend/app/agent/skills/registry/skills.yaml`，迁移第一版 capability metadata、examples、anti_examples、tags、operations、risk、context dependencies 和 cache invalidation。
- [x] 1.3 新增 `backend/app/agent/skills/registry/aliases.yaml`，覆盖所有现有 legacy tool name 到 capability/operation 的映射。
- [x] 1.4 新增 Registry loader 模块，解析 YAML 并输出 capability、operation、alias、domain 的结构化对象。
- [x] 1.5 新增 Registry validation，检查必填字段、无效 domain、缺失 owner、缺失 anti_examples、operation 无 risk、alias 指向不存在目标。
- [x] 1.6 增加 `backend/tests/skills/test_skill_registry.py`，覆盖 loader、validation 和 alias 解析。

## 2. Catalog And Metadata Integration

- [x] 2.1 修改 `backend/app/agent/router/catalog.py`，优先从 Registry 构建 `ToolCandidate`，保留现有 Python registry 作为 fallback。
- [x] 2.2 修改 `backend/app/agent/router/registry.py`，降级为兼容迁移桥，并避免继续新增业务能力配置。
- [x] 2.3 修改 `backend/app/agent/skills/metadata.py`，让 runtime metadata 可从 Registry 合并 permission、risk、context、cache、enabled 和 disabled reason。
- [x] 2.4 修改 `backend/app/agent/skill_coverage.py`，将覆盖矩阵对齐到 capability/operation，同时保留 legacy skill 展示。
- [x] 2.5 扩展 `backend/tests/skills/test_skill_metadata.py` 和 `backend/tests/skills/test_skill_coverage_matrix.py`。
- [x] 2.6 扩展 `backend/tests/skills/test_skill_docs.py`，校验 `skill.md` 与 Registry name/domain/capability 不冲突。

## 3. Router Decision And Policy

- [x] 3.1 扩展 `backend/app/agent/router/models.py`，为 `IntentFrame`、`ToolCandidate`、`RouterDecision` 增加 capability、operation、score、evidence、legacy_alias、selected_operations 字段。
- [x] 3.2 修改 `backend/app/agent/router/service.py`，实现 domain shortlist、capability retrieval、operation hint 的编排。
- [x] 3.3 修改 `backend/app/agent/router/classifier.py`，减少业务硬编码，只保留轻量 frame 抽取、无工具保护、写风险保护和兼容规则。
- [x] 3.4 修改 `backend/app/agent/router/policy.py`，按 capability/operation 风险做读写隔离、schema 预算、高风险澄清和 fallback all 禁止。
- [x] 3.5 更新 Router trace payload，记录 domain score、capability score、operation score、evidence、rejected candidates 和 fallback reason。
- [x] 3.6 更新 `backend/tests/agent/router/test_skill_router.py`，覆盖成本、茬口、工人、作业单、人工结算、设置等 capability routing。
- [x] 3.7 更新 `backend/tests/agent/router/test_router_policy.py`，覆盖读写隔离、高风险、schema 预算、disabled skill 和 fallback all 禁止。
- [x] 3.8 更新 `backend/tests/agent/router/test_router_trace.py` 和 `backend/tests/agent/router/test_router_models.py`。

## 4. Runtime Binding And Execution Compatibility

- [x] 4.1 修改 `backend/app/agent/skills/__init__.py`，为 LangChain Tool 附加 capability、operation 和 alias metadata；第一阶段仍允许旧工具执行。
- [x] 4.2 修改 `backend/app/agent/runtime/nodes.py`，消费新的 `RouterDecision`，绑定 capability-aware 候选工具，并保持 final answer round 不 fallback all。
- [x] 4.3 修改 `backend/app/agent/runtime/tool_executor.py`，按 operation risk 处理 read、write_confirm、write_high、external_network 和 disabled 状态。
- [x] 4.4 修改 `backend/app/agent/executor/pending_actions.py`，执行 pending action 前解析 legacy alias，并在 trace 中记录 legacy name 和 resolved capability operation。
- [x] 4.5 更新 `backend/tests/agent/test_runtime_router_binding.py`，覆盖 capability-aware binding 和 no fallback all。
- [x] 4.6 更新 `backend/tests/agent/test_tool_executor_metadata.py`，覆盖 operation-level risk 和 disabled behavior。
- [x] 4.7 更新 `backend/tests/agent/test_pending_action_executor.py`，覆盖 legacy alias pending action replay。

## 5. Governance Checks And Evaluation

- [x] 5.1 新增 `scripts/check-skill-registry.sh`，运行 Registry validation 和关键 alias 覆盖检查。
- [x] 5.2 更新 `scripts/check-skill-docs.sh`，纳入 Registry 与 skill.md 一致性检查。
- [x] 5.3 更新 `scripts/harness-check.sh`，加入 Skill Registry 检查。
- [x] 5.4 新增或扩展 Router eval cases，覆盖 Top-1 capability accuracy、Top-3 recall、读意图写暴露、高风险误暴露和 selected tools 数量。
- [x] 5.5 运行最小验证：`ruff check backend/app/agent backend/tests/agent backend/tests/skills`。
- [x] 5.6 运行 Router 和 Skill 相关测试：`pytest backend/tests/agent/router backend/tests/agent/test_runtime_router_binding.py backend/tests/agent/test_tool_executor_metadata.py backend/tests/agent/test_pending_action_executor.py backend/tests/skills/test_skill_metadata.py backend/tests/skills/test_skill_docs.py -q`。
- [x] 5.7 运行治理检查：`bash scripts/check-skill-registry.sh && bash scripts/check-skill-docs.sh && bash scripts/check-complexity-budget.sh`。

## 6. Optional Capability Consolidation

- [x] 6.1 低风险合并 `manage_settings`，把 `get_user_settings` 和 `manage_user_settings` 通过 capability operation 统一。
- [x] 6.2 低风险合并 `manage_workers`，把 `get_workers` 和 `manage_workers` 通过 capability operation 统一。
- [ ] 6.3 低风险合并 `manage_planting_units`，把查询和管理 operation 统一。
- [ ] 6.4 低风险合并 `manage_cost_categories`，把分类查询和管理 operation 统一。
- [ ] 6.5 在低风险合并稳定后，再为 `manage_cost`、`manage_crop_cycle`、`manage_work_orders`、`manage_labor_payment` 单独拆后续 OpenSpec change。
