<p align="center">
  <img src="./banner.png" alt="AgriAgent OS Design Spec" width="100%">
</p>

<p align="center">
  English | <a href="./README.md">简体中文</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/React-20232A?style=flat-square&logo=react&logoColor=61DAFB" alt="React">
  <img src="https://img.shields.io/badge/TypeScript-3178C6?style=flat-square&logo=typescript&logoColor=white" alt="TypeScript">
  <img src="https://img.shields.io/badge/Vite-646CFF?style=flat-square&logo=vite&logoColor=white" alt="Vite">
  <img src="https://img.shields.io/badge/React_Native-20232A?style=flat-square&logo=react&logoColor=61DAFB" alt="React Native">
  <img src="https://img.shields.io/badge/LangGraph-1C3C3C?style=flat-square" alt="LangGraph">
  <img src="https://img.shields.io/badge/LangChain-1C3C3C?style=flat-square" alt="LangChain">
  <img src="https://img.shields.io/badge/SQLAlchemy-D71F00?style=flat-square&logo=sqlalchemy&logoColor=white" alt="SQLAlchemy">
  <img src="https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white" alt="Docker">
  <img src="https://img.shields.io/badge/AI_Agent-111827?style=flat-square" alt="AI Agent">
  <img src="https://img.shields.io/badge/Farm_Management-2E7D32?style=flat-square" alt="Farm Management">
</p>

# AgriAgent OS Design Spec

> Version: v0.9 (draft, 33 chapters scaffolded + Context/Memory compression revised + Discovery Layer design added + Knowledge & Memory architecture梳理 + fully redacted + region-tag delta proposal synced + database schema design backfilled)
> Last updated: 2026-06-20
> Maintainer: BlockShip
> Status: draft, continuously aligned with `docs/architecture/` and the codebase

---

## What is this

This repo is the **single source of truth** for the AgriAgent OS project's design spec. It consolidates the architectural decisions, module boundaries, interface contracts, and coding rules scattered across `docs/architecture/`, `docs/design/`, `.claude/rules/`, and `backend/app/**` into one place — so future iterations stay aligned across the team and across AI agents.

Reference layout: the six-bucket pattern (pre-design / formal design / interface protocols / related rules / system testing / project management) used by mainstream agent design docs.

## Relationship to existing docs

| Existing doc | Role in this spec |
| --- | --- |
| `docs/architecture/overview.md` | Folded into [00_pre-design/02_system_function_and_tech_architecture.md](./00_预设计/02_系统功能及技术架构总设计.md) |
| `docs/architecture/boundaries.md` | Boundary matrices sink into each module's "may depend on / must not depend on" table in [01_formal_design/01_agent_platform_architecture.md](./01_正式设计/01_Agent平台架构.md) |
| `docs/architecture/agent-data-flywheel-industrial-roadmap.md` | Condensed and linked from [01_formal_design/06_data_flywheel_and_evaluation.md](./01_正式设计/06_数据飞轮与评测.md) |
| `docs/architecture/evolution-roadmap.md` | Folded into [06_project_management/01_milestones_and_roadmap.md](./06_项目管理/01_里程碑与路线图.md) |
| `.claude/rules/*.md` | Cited as authoritative; this spec does not restate the clauses, only points to them |
| `.claude/rules/skill-writing.md` | Aligned with [01_formal_design/02_skill_engine_and_contract.md](./01_正式设计/02_Skill引擎与契约.md); on conflict, `skill-writing.md` wins |

Conflict resolution priority: code > `docs/architecture/` > this spec > historical commits. Any inconsistency should be **fixed in this spec first, then in the code**.

## Directory overview

| Folder | Contents | Primary audience |
| --- | --- | --- |
| [00_pre-design](./00_预设计) | System vision, overall tech architecture, tech selection | Everyone, especially newcomers |
| [01_formal_design](./01_正式设计) | Agent platform, Skills, Context, Memory, Prompt, DataFlywheel, business modules, frontend contract | Backend + Agent engineers |
| [02_product_requirements](./02_产品需求) | Core capability list, non-functional requirements | Product + engineering |
| [03_interface_protocols](./03_接口协议) | HTTP API, Agent internal interfaces, external services, Skill contract | Engineers + integration partners |
| [04_related_rules](./04_相关规范) | Prompt/persona, security, database, frontend/backend coding, anti-pollution | Everyone |
| [05_system_testing](./05_系统测试) | Test pyramid, regression set, Simulation, Evaluation | QA + engineering |
| [06_project_management](./06_项目管理) | Milestones, work breakdown, Git conventions | PM + engineering |

### Full index

> Note: the underlying files are named in Chinese for now; the English links below point to the same paths.

#### 00_pre-design
- [01_system_vision_and_goals.md](./00_预设计/01_系统愿景与目标.md)
- [02_system_function_and_tech_architecture.md](./00_预设计/02_系统功能及技术架构总设计.md)
- [03_tech_selection_and_dependencies.md](./00_预设计/03_技术选型与依赖.md)

#### 01_formal_design
- [01_agent_platform_architecture.md](./01_正式设计/01_Agent平台架构.md)
- [02_skill_engine_and_contract.md](./01_正式设计/02_Skill引擎与契约.md)
- [03_context_engineering.md](./01_正式设计/03_Context工程.md)
- [04_memory_engineering.md](./01_正式设计/04_Memory工程.md)
- [05_prompt_engineering.md](./01_正式设计/05_Prompt工程.md)
- [06_data_flywheel_and_evaluation.md](./01_正式设计/06_数据飞轮与评测.md)
- [07_observability_and_ops.md](./01_正式设计/07_可观测与运维.md)
- [08_business_modularization.md](./01_正式设计/08_业务模块化.md)
- [09_frontend_and_mobile_contract.md](./01_正式设计/09_前端与移动端契约.md)
- [10_database_schema_design.md](./01_正式设计/10_数据库结构设计.md)

#### 02_product_requirements
- [01_core_capability_list.md](./02_产品需求/01_核心能力清单.md)
- [02_non_functional_requirements.md](./02_产品需求/02_非功能性需求.md)

#### 03_interface_protocols
- [01_http_api_protocol.md](./03_接口协议/01_HTTP_API协议.md)
- [02_agent_internal_interfaces.md](./03_接口协议/02_Agent内部接口.md)
- [03_external_service_interfaces.md](./03_接口协议/03_外部服务接口.md)
- [04_skill_interface_contract.md](./03_接口协议/04_Skill接口契约.md)

#### 04_related_rules
- [01_prompt_and_persona_rules.md](./04_相关规范/01_Prompt与人设规范.md)
- [02_security_and_permission_rules.md](./04_相关规范/02_安全与权限规范.md)
- [03_database_and_migration_rules.md](./04_相关规范/03_数据库与迁移规范.md)
- [04_frontend_coding_rules.md](./04_相关规范/04_前端编码规范.md)
- [05_python_coding_rules.md](./04_相关规范/05_Python编码规范.md)
- [06_anti_pollution_and_doc_sync_rules.md](./04_相关规范/06_防污染与文档同步规范.md)

#### 05_system_testing
- [01_test_pyramid_and_strategy.md](./05_系统测试/01_测试金字塔与策略.md)
- [02_regression_test_set.md](./05_系统测试/02_回归测试集.md)
- [03_simulation_testing.md](./05_系统测试/03_Simulation仿真测试.md)
- [04_evaluation.md](./05_系统测试/04_Evaluation评测.md)

#### 06_project_management
- [01_milestones_and_roadmap.md](./06_项目管理/01_里程碑与路线图.md)
- [02_work_breakdown.md](./06_项目管理/02_工作拆解.md)
- [03_git_and_collaboration_rules.md](./06_项目管理/03_Git与协作规范.md)

## Reading paths

| Who you are | Suggested order |
| --- | --- |
| Newcomer onboarding | 00 → 02 → 03 → 01 |
| Backend engineer | 01.01 → 01.02 → 01.03 → 03.02 → 04 |
| Agent / Prompt engineer | 01.01 → 01.02 → 01.05 → 04.01 → 06 |
| Mobile engineer | 02 → 03.01 → 01.09 → 04.04 |
| Admin Web engineer | 02 → 03.01 → 01.09 → 04.04 |
| Product / PM | 02 → 00.01 → 06 |
| QA | 05 → 03 → 01 |

## Hard constraints (PR-blocking)

1. **Dependency direction**: `schemas/ → agent/application → agent/runtime → modules → services → core/infra → models`; frontend `api/ → components → layouts → pages`. See [01.01 agent_platform_architecture](./01_正式设计/01_Agent平台架构.md).
2. **Cross-cutting concerns**: auth / log / telemetry / trace only via dependency injection. Business layers must not import them directly.
3. **File & method size limits**: production Python files ≤ 1000 lines; 500-1000 lines is an observation/review range; methods should stay ≤ 50 lines and require justification or step extraction above 80 lines; classes ≤ 200 lines; method parameters ≤ 5.
4. **New code must have tests**: target ≥ 80% coverage, critical paths must be covered.
5. **Skill contract**: every Skill must ship a `skill.md` + `scripts/main.py` and conform to [01.02 skill_engine_and_contract](./01_正式设计/02_Skill引擎与契约.md).
6. **Structured logging**: no `print` / `console.log` for debugging; logs must carry `trace_id`.
7. **Database changes**: Alembic only; no manual SQL DDL; MySQL 8.x with `utf8mb4` charset.
8. **Write Skills cannot be cached**, and must not guess business-critical fields when parameters are missing.

## Maintenance cadence

- **Triggers for editing this spec**: ① add/modify an API endpoint; ② add/modify a data model; ③ add/modify a Skill; ④ modify config or deployment; ⑤ modify security policy; ⑥ add a functional module.
- **Every formal PR**: if it hits any trigger above, the corresponding chapter must be updated in the same PR with a link back.
- **Quarterly review**: cross-check the index against the real structure of `backend/app/`, `admin-web/src/`, `mobile-app/lib/`. Inconsistencies are fixed by the original author.

## Glossary

| Term | Definition |
| --- | --- |
| Agent | The farm-assistant intelligent agent, composed of Application + Runtime + Planner + Executor + Reflector |
| Advisor | Backward-compatible entry of the Agent; handles Guardrails, greetings, Pending Actions, streaming orchestration |
| Skill | Single-capability module, implemented per the `.claude/rules/skill-writing.md` contract; either read-only or write |
| ContextBundle | The dynamic context bundle consumed by Runtime; built by Selector + Budget + Compressor |
| MemoryService | Unified port for short-term memory + long-term memory + Retrieval + Observation |
| PromptComposer | Renderer that stitches snippets into the final system prompt, governed by `prompt/` |
| DataFlywheel | Sample workbench: extracts from sessions / traces / simulation failures → rule candidates → LLM pre-labeling → human confirmation → regression / evaluation / training data |
| Simulation | Regression executor: runs DB-backed regression cases |
| Evaluation | Trend scorer: pass rate / tool-selection accuracy / pending-miss rate across versions |
| Pending Action | A write-op action that requires user confirmation; supports confirm / cancel / expire |
| Smart Fill | Mobile-side unified entry for smart form filling: `/api/v1/scenarios` lists scenarios + `/parse` parses |
| Farm Cockpit | Mobile home dashboard; carries daily advice, key metrics, quick entries |
| Yaya | Mobile AI assistant chat page (the "Yaya" IP) |

## Changelog

| Version | Date | Change | Author |
| --- | --- | --- | --- |
| v0.1 | 2026-06-19 | Created the directory scaffold and the first drafts of the core chapters (25 chapters across 00–04) | BlockShip |
| v0.2 | 2026-06-19 | Filled in 05_system_testing (4 chapters) + 06_project_management (3 chapters); the 32-chapter scaffold is complete | BlockShip |
| v0.3 | 2026-06-19 | [03_context_engineering] § 6 compression strategy rewritten to match the actual code (5 stages + multi-turn amnesia root causes + comparison of mainstream approaches + recommended approach); [04_memory_engineering] § 6 short-term memory adds "current implementation / identified issues / fix directions"; adds § 12 multi-turn amnesia remediation roadmap and § 13 storage evolution roadmap (Redis decision: not yet) | BlockShip |
| v0.4 | 2026-06-19 | [01_formal_design/06_data_flywheel_and_evaluation] adds § 9 Discovery Layer and risk discovery (2-level filter + max-score + rule engine + LLM Judge + 3 workbench tweaks + 4.5 person-day MVP); the original § 9–§ 12 shift to § 10–§ 13; [00_pre-design/02_system_function_and_tech_architecture] architecture diagram + five-subsystem table + § 5.7 decision + § 7 landing status adds Discovery Layer | BlockShip |
| v0.5 | 2026-06-19 | Knowledge & Memory architecture brainstorming output: [04_memory_engineering] § 7 long-term memory adds § 7.2 implementation (candidate→confirmed transitions + new `memory_records` table + shared trigger with summary); § 8 retrieval adds § 8.2 four conditions for adopting Qdrant + § 8.3 implementation boundaries; § 14 current status / § 16 related docs synced; [02_skill_engine_and_contract] `create_crop_template` gets a region note | BlockShip |
| v0.6 | 2026-06-19 | Redaction: dropped concrete external project names and paths from comparison chapters ([Readme], [01_agent_platform_architecture] § 9, [02_system_function_and_tech_architecture] § 6, [04_memory_engineering] § 15), rewritten as "typical multi-agent systems / typical agent architectures"; removed the production server IP ([07_observability_and_ops] § 11, [03_tech_selection_and_dependencies] § 5.1) | BlockShip |
| v0.7 | 2026-06-19 | Deeper redaction pass: [07_observability_and_ops] § 5 drops the "align with smart-home LOGBUS style" line, § 11 deployment paths / service names / ops scripts all turned into placeholders (`<repo_dir>` / `<service_name>`); [03_tech_selection_and_dependencies] § 5 synced; [03_interface_protocols/03_external_service_interfaces] § 5/§ 6 log paths + every `/root/workspace/...` in the systemd unit turned into placeholders, User field turned into `<deploy_user>` | BlockShip |
| v0.8 | 2026-06-19 | Region-tag sync: created [openspec/changes/extend-crop-template-with-region-tag](../../openspec/changes/extend-crop-template-with-region-tag/proposal.md) delta proposal (full proposal/design/specs/tasks); synced [04_related_rules/03_database_and_migration_rules] table list `crops → crop_templates` + region_tag note; [01_formal_design/08_business_modularization] CropPort signature adds region + new `list_system_templates` / `import_system_template`; [02_product_requirements/01_core_capability_list] crop management gets region variants; [03_interface_protocols/01_http_api_protocol] adds `GET /crops/templates/system?region=` and `POST /import` endpoints | BlockShip |
| v0.9 | 2026-06-20 | Added [01_formal_design/10_database_schema_design]: using `backend/sql/farm_manager.sql` production dump as the baseline, derives the fields, constraints, indexes, and foreign keys of 33 tables (including `alembic_version`); adds an interface→table mapping matrix, a production-vs-code delta reconciliation, and a reserved-tables list (`memory_records` / `audit_logs` / `evaluation_reports`, etc.) | BlockShip |

## License

[CC BY-NC 4.0](./LICENSE) © BlockShip — share and adapt with attribution, no commercial use.
