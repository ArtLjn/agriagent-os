<p align="center">
  <img src="./banner.png" alt="AgriAgentOS" width="100%">
</p>

<p align="center">
  English | <a href="../../README.md">简体中文</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/React-20232A?style=flat-square&logo=react&logoColor=61DAFB" alt="React">
  <img src="https://img.shields.io/badge/TypeScript-3178C6?style=flat-square&logo=typescript&logoColor=white" alt="TypeScript">
  <img src="https://img.shields.io/badge/Vite-646CFF?style=flat-square&logo=vite&logoColor=white" alt="Vite">
  <img src="https://img.shields.io/badge/Flutter-02569B?style=flat-square&logo=flutter&logoColor=white" alt="Flutter">
  <img src="https://img.shields.io/badge/LangChain-1C3C3C?style=flat-square" alt="LangChain">
  <img src="https://img.shields.io/badge/SQLAlchemy-D71F00?style=flat-square&logo=sqlalchemy&logoColor=white" alt="SQLAlchemy">
  <img src="https://img.shields.io/badge/MySQL-4479A1?style=flat-square&logo=mysql&logoColor=white" alt="MySQL">
  <img src="https://img.shields.io/badge/MongoDB-47A248?style=flat-square&logo=mongodb&logoColor=white" alt="MongoDB">
  <img src="https://img.shields.io/badge/AI_Agent-111827?style=flat-square" alt="AI Agent">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Monorepo-backend%20%7C%20admin%20%7C%20mobile-111827?style=flat-square" alt="Monorepo">
  <img src="https://img.shields.io/badge/Docs-Design%20Docs-2563EB?style=flat-square" alt="Design Docs">
  <img src="https://img.shields.io/badge/OpenSpec-change%20workflow-7C3AED?style=flat-square" alt="OpenSpec">
  <img src="https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white" alt="Docker Compose">
  <img src="https://img.shields.io/badge/Tests-pytest%20%7C%20vitest%20%7C%20flutter-16A34A?style=flat-square" alt="Tests">
  <img src="https://img.shields.io/badge/License-CC%20BY--NC%204.0-6B7280?style=flat-square" alt="License">
</p>

<h2 id="overview">🌱 Overview</h2>

AgriAgentOS is an AI Agent operating system for agricultural operations. It covers a mobile operations workspace, natural-language bookkeeping, activity records, crop templates, weather-assisted planning, an admin console, and an Agent data flywheel. The project uses a FastAPI backend, a React admin console, and a Flutter mobile app. Around Skill, Context, Memory, Trace, and Evaluation, it builds a governable, observable, and testable Agent platform.

Full architecture, API contracts, Agent runtime rules, and project governance live in the [design documents](./README.md).

<h2 id="quick-links">🧭 Quick Links</h2>

| Entry | What it covers |
| --- | --- |
| [Screenshots](#screenshots) | Admin technical console and mobile business screens |
| [Core Capabilities](#core-capabilities) | Agent, operational data, smart fill, and data flywheel |
| [Architecture Highlights](#architecture-highlights) | Runtime, Skill, Context, Memory, and Trace boundaries |
| [Quick Start](#quick-start) | Docker Compose and local development |
| [Common Checks](#common-checks) | Backend, admin console, mobile, and architecture gates |
| [Documentation](#documentation) | Design docs, architecture docs, API spec, and current sprint |

## Who Should Read This

| Role | What you get |
| --- | --- |
| Agent engineer | Skill Registry, Context Engine, Memory Service, Runtime Loop, Reflection, and Trace feedback loops |
| Backend engineer | FastAPI layering, domain folders, platform capabilities, database models, and Alembic constraints |
| Frontend engineer | React admin console, Flutter mobile app, API boundaries, and real business screens |
| Product / operations | Operations workspace, crop templates, ledger, weather, user management, and data flywheel |
| Evaluation / QA | Simulation, Evaluation, TraceMonitor, DataFlywheel, and repair-pack workflows |

<h2 id="screenshots">🖼️ Screenshots</h2>

### 🛠️ Admin Technical Console

<table>
  <tr>
    <td align="center"><img src="../assets/screenshots/admin-trace-monitor.png" alt="Trace Monitor" width="320"><br>Trace Monitor</td>
    <td align="center"><img src="../assets/screenshots/admin-token-dashboard.png" alt="Token Dashboard" width="320"><br>Token Dashboard</td>
    <td align="center"><img src="../assets/screenshots/admin-playground.png" alt="Agent Playground" width="320"><br>Agent Playground</td>
  </tr>
  <tr>
    <td align="center"><img src="../assets/screenshots/admin-data-flywheel.png" alt="DataFlywheel" width="320"><br>DataFlywheel</td>
    <td align="center"><img src="../assets/screenshots/admin-skill-registry.png" alt="Skill Registry" width="320"><br>Skill Registry</td>
    <td align="center"><img src="../assets/screenshots/admin-skill-router-eval.png" alt="Skill Router Eval" width="320"><br>Skill Router Eval</td>
  </tr>
  <tr>
    <td align="center"><img src="../assets/screenshots/admin-prompt-inspector.png" alt="Prompt Inspector" width="320"><br>Prompt Inspector</td>
    <td align="center"><img src="../assets/screenshots/admin-user-management.png" alt="User Management" width="320"><br>User Management</td>
    <td align="center"><img src="../assets/screenshots/admin-weather.png" alt="Weather Context" width="320"><br>Weather Context</td>
  </tr>
</table>

### 📱 Mobile Business Workspace

<table>
  <tr>
    <td align="center"><img src="../assets/screenshots/mobile-home.png" alt="Home Workspace" width="180"><br>Home Workspace</td>
    <td align="center"><img src="../assets/screenshots/mobile-record.png" alt="AI Smart Fill" width="180"><br>AI Smart Fill</td>
    <td align="center"><img src="../assets/screenshots/mobile-yaya.png" alt="AI Assistant" width="180"><br>AI Assistant</td>
    <td align="center"><img src="../assets/screenshots/mobile-ledger.png" alt="Ledger Overview" width="180"><br>Ledger Overview</td>
    <td align="center"><img src="../assets/screenshots/mobile-crop-templates.png" alt="Crop Templates" width="180"><br>Crop Templates</td>
  </tr>
</table>

<h2 id="core-capabilities">⚙️ Core Capabilities</h2>

- **Agricultural AI Agent**: natural-language Q&A, tool calls, SSE streaming, write-operation confirmation, and final-response auditing.
- **Operational data management**: costs, income, credit, labor, activity logs, planting cycles, plots, and work orders.
- **Smart fill**: the mobile app uses `/smart-fill/scenarios` and `/smart-fill/parse` to generate form drafts before any business write.
- **Crop template library**: system templates, farm copies, growth stages, duplicate checks, and template maintenance.
- **Context and memory**: ContextBundle, TaskState, short-term summaries, and explicit long-term memory control the Agent input surface.
- **Observability and data flywheel**: TraceMonitor, Simulation, Evaluation, DataFlywheel, and repair packs close the failure-to-regression loop.
- **Admin console**: users, configuration, skills, tokens, traces, data flywheel, simulation, evaluation, and operations dashboards.

## Capability Matrix

| Capability | Coverage | Main entry |
| --- | --- | --- |
| Agent Runtime | Tool calls, parallel execution, final response, output constraints, write confirmation | `backend/app/agent/` |
| Skill System | Skill registry, operation metadata, permissions, schema, routing evaluation | `backend/app/skills/` |
| Context Engineering | ContextBundle, selector, token budget, TaskState relevance gate | `backend/app/context/` |
| Memory Engineering | Short-term window, session summary, explicit long-term memory, observation events | `backend/app/memory/` |
| Prompt Engineering | Prompt registry, snippet composition, rendering, replay | `backend/app/prompt/` |
| Data Flywheel | Sample queue, LLM pre-labeling, human confirmation, issue chain, repair pack | `backend/app/platforms/data_flywheel/` |
| Simulation & Evaluation | Simulation cases, evaluation replay, router regression, report aggregation | `backend/app/platforms/evaluation/` |
| Admin Console | Trace, Token, Skill, Prompt, Playground, users, weather, data flywheel | `admin-web/src/` |
| Mobile App | Home, workspace, AI assistant, ledger, crop templates, profile settings | `mobile-app/lib/` |

<h2 id="architecture-highlights">🏗️ Architecture Highlights</h2>

AgriAgentOS is not just an LLM wired to a chat box. It separates risky writes, context pollution, wrong tool selection, and unauditable answers into explicit engineering boundaries:

- **Runtime decoupled from business logic**: Runtime owns the node state machine, tool calls, and final response. It does not own Prompt, Context, Memory, or domain rules.
- **Skill operations as contracts**: A Skill carries operation metadata, input schema, risk level, confirmation policy, and routing hints.
- **Explainable context**: Context is built by selector, budget, compressor, and trace payloads instead of dumping the database or raw traces into prompts.
- **Fail-closed writes**: Costs, crops, work orders, labor, and other business writes enter pending action or pending plan by default; missing critical fields are not guessed.
- **Trace to data flywheel**: Real requests, tool calls, model outputs, and failure evidence can become samples for evaluation, regression, and repair packs.
- **Directories as boundaries**: New backend code belongs in `domains/*`, `platforms/*`, or the Agent platform boundary, not in legacy technical-layer folders.

## Tech Stack

| Module | Technology |
| --- | --- |
| Backend | FastAPI, SQLAlchemy, Pydantic, Alembic, LangChain, Skillify |
| Data | MySQL 8.x, MongoDB 7, JSONL event log |
| Admin console | React 19, TypeScript, Vite, Ant Design 5, Vitest |
| Mobile app | Flutter, Riverpod, Dio, GoRouter, Flutter Secure Storage |
| Agent platform | Skill Registry, Context Engine, Memory Service, Runtime Loop, Reflection, Trace, Evaluation |
| Deployment | Docker Compose, Uvicorn, Nginx static frontend container |

## Module Map

| Module | Purpose | Main concern |
| --- | --- | --- |
| `backend/app/bootstrap/` | FastAPI app factory, route registration, middleware, lifespan | Clear and testable startup |
| `backend/app/domains/` | Users, farms, crops, finance, weather, sessions | Business rules stay out of platform code |
| `backend/app/application/` | Chat, sessions, suggestions, reports | Thin API entry points |
| `backend/app/agent/` | Runtime, planner, executor, guardrails, reflection | Decomposable Agent execution |
| `backend/app/skills/` | Skill implementation, registration, permission, schema | Governable and testable tools |
| `backend/app/platforms/` | admin, data_flywheel, evaluation, simulation | Platform capabilities isolated from domains |
| `admin-web/` | React admin console | Operations, evaluation, traces, and data flywheel |
| `mobile-app/` | Flutter mobile app | User-facing operations workspace |

## Project Structure

```text
backend/app/
├── bootstrap/       # App factory, route registration, middleware, exceptions, lifespan
├── domains/         # Users, farms, crops, finance, weather, sessions
├── application/     # Chat, sessions, suggestions, reports
├── agent/           # Agent runtime, planner, executor, guardrails, reflection
├── skills/          # Skill implementation, registration, permissions, schema, adapters
├── prompt/          # Prompt registry, composition, rendering, replay
├── context/         # ContextBundle, selector, budget, compression, task state
├── memory/          # Short-term memory, explicit long-term memory, observation
├── platforms/       # admin, data_flywheel, evaluation, simulation, shared
├── shared/          # Config, database, logging, security, time, model registry
├── infra/           # trace, Mongo, rate limit, cache, circuit breaker, RAG client
└── ops/             # seed, audit, operations helpers

admin-web/           # React admin console
mobile-app/          # Flutter mobile app
docs/                # Architecture, design, standards, screenshot assets
openspec/            # Change proposals and capability specifications
```

Do not recreate legacy backend entry folders such as `app.core`, `app.api`, `app.models`, `app.schemas`, `app.services`, `app.modules`, or `app.simulation`.

<h2 id="quick-start">🚀 Quick Start</h2>

### Docker Compose

```bash
cp backend/config.yaml.example backend/config.yaml

cat > .env <<'ENV'
MYSQL_ROOT_PASSWORD=change-me
MYSQL_PASSWORD=change-me
MONGO_INITDB_ROOT_PASSWORD=change-me
AUTH_JWT_SECRET=change-me-to-a-long-random-secret
ENV

docker compose up -d --build
```

Default ports:

| Service | URL |
| --- | --- |
| Backend API | `http://127.0.0.1:18000` |
| Admin console | `http://127.0.0.1:18080` |
| Health check | `http://127.0.0.1:18000/health` |

LLM, weather, RAG, and vector retrieval settings are configured through `backend/config.yaml` or environment variables. Template files do not contain real secrets.

### Local Development

Backend:

```bash
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Admin console:

```bash
cd admin-web
pnpm install
pnpm dev
```

Mobile app:

```bash
cd mobile-app
flutter pub get
flutter run
```

## Common Checks

```bash
# Backend
cd backend
ruff check .
pytest -v

# Admin console
cd admin-web
pnpm lint
pnpm test

# Mobile app
cd mobile-app
flutter analyze
flutter test
```

Architecture and complexity gates:

```bash
bash scripts/check-layer-deps.sh
bash scripts/check-complexity-budget.sh
bash scripts/check-guide-sensor-pairing.sh
```

## Development Conventions

- **Branching**: use `codex/*` or a dedicated worktree by default, then merge through a PR.
- **Commits**: use Conventional Commits, such as `feat:`, `fix:`, `docs:`, `refactor:`, and `test:`.
- **Doc sync**: when APIs, data models, Skills, config, deployment, or security policy change, update the matching design documents.
- **Testing**: add automated tests for clear and testable requirements; for design-only or non-automatable changes, add structure checks and human-review points.
- **Security**: do not commit `.env`, real secrets, credentials, production connection strings, or bulky temporary artifacts.
- **Assets**: README pages reference stable screenshots in `docs/assets/screenshots/`; `output/` is only a candidate asset pool.

<h2 id="documentation">📚 Documentation</h2>

| Document | Purpose |
| --- | --- |
| [AGENTS.md](../../AGENTS.md) | Agent working rules, project map, and hard constraints |
| [Architecture overview](../architecture/overview.md) | Current architecture source of truth and module boundaries |
| [Backend architecture](../architecture/backend-architecture.md) | Backend responsibilities, request flow, and Agent platform split |
| [Design documents](./README.md) | Formal design, interface protocols, testing strategy, and project management |
| [Agent development standard](../agent/agent-development-standard.md) | Agent / Skill / Context / Trace development rules |
| [API spec](../reference/api-spec.yaml) | OpenAPI / HTTP protocol reference |
| [Current sprint](../plans/current-sprint.md) | Current sprint status and follow-up tasks |

## Screenshot & Asset Policy

The README pages only reference stable documentation assets under `docs/assets/screenshots/`. The `output/` directory is used for generated artifacts, design candidates, and temporary screenshot storage, not as a long-term documentation source.

## License

[CC BY-NC 4.0](./LICENSE) © BlockShip. You may share and adapt with attribution. Commercial use is not permitted.
