# Backend 多级目录收束设计

| 项目 | 内容 |
| --- | --- |
| 日期 | 2026-07-18 |
| 状态 | Proposed |
| 目标 | 从过细技术分层改为领域二级目录聚合，减少碎片模块和无意义小文件 |
| 关联文档 | [2026-07-12-backend-bloat-diagnosis.md](./2026-07-12-backend-bloat-diagnosis.md)、[2026-07-14-backend-directory-redesign.md](./2026-07-14-backend-directory-redesign.md) |

## 1. 背景

前一轮整改已经删除了大量兼容入口、下线 LangGraph、收束 DataFlywheel 灰度仓储后端，并把 `agent` 巨石文件拆回可读范围。但当前目录仍有两个新问题：

1. **规则过严导致碎片化**：500 行文件预算把本来可以放在同一领域文件里的逻辑拆散，增加跳转成本。当前用户确认生产代码 **1000 行以内可以接受**。
2. **一级目录过多且语义混杂**：`models/`、`schemas/`、`services/` 是技术层目录，不表达业务归属；`seed/`、`scripts/`、若干只含 `__init__.py` 的目录占据完整模块位置。

本设计将后端目录从“技术分层优先”调整为“领域聚合优先”，让一个业务域的模型、协议、服务和路由尽量在同一个二级目录内闭合。

## 2. 设计原则

### 2.1 文件大小预算

- 生产 Python 文件默认预算改为 **1000 行以内可接受**。
- 超过 1000 行才视为必须拆分；500-1000 行只在职责明显混杂时拆。
- 单函数仍建议控制在 50-80 行；超过 80 行需要说明原因或拆成步骤函数。
- 不为了绕预算拆出 20-50 行的小文件。

### 2.2 目录成立条件

新增目录至少满足一个条件：

- 承载一个稳定业务域，例如 `planting`、`finance`、`conversation`。
- 承载一个平台能力，例如 `agent`、`data_flywheel`、`evaluation`。
- 隔离基础设施实现，例如 `shared/persistence`。

只包含一个 `__init__.py` 或一个小工具文件的目录，应优先合并或迁入上级目录。

### 2.3 模块边界

- `domains/*` 面向业务主流程，允许一个领域目录内同时存在 `models.py`、`schemas.py`、`service.py`、`routes.py`。
- `agent/*` 面向 Agent 平台运行时，不和普通业务服务混放。
- `platforms/*` 面向管理台、评测、数据飞轮等平台能力。
- `shared/*` 只放跨全局基础设施，不放业务逻辑。
- `ops/*` 放 seed、schema audit、一次性运维脚本和离线工具。

## 3. 目标目录

```text
backend/app/
  main.py
  bootstrap/
    app_factory.py
    exceptions.py
    lifespan.py
    middleware.py
    routes.py

  shared/
    config.py
    database.py
    logging.py
    time.py
    llm.py
    security.py
    compatibility.py
    persistence/
      mongo.py
      repositories.py
      trace.py

  domains/
    farm/
      models.py
      schemas.py
      service.py
      routes.py
      seed.py

    planting/
      models.py
      schemas.py
      service.py
      smart_fill.py
      routes.py

    finance/
      models.py
      schemas.py
      service.py
      routes.py

    conversation/
      models.py
      schemas.py
      service.py
      pending.py
      routes.py

    weather/
      schemas.py
      service.py
      providers.py
      routes.py

    users/
      models.py
      schemas.py
      service.py
      routes.py

  agent/
    runtime/
      loop.py
      nodes.py
      tools.py
      planning.py
      pending.py
    router/
      classifier.py
      policy.py
      registry.py
    memory/
      models.py
      service.py
      summarizer.py
    reflector/
      service.py
      checks.py

  platforms/
    data_flywheel/
      models.py
      schemas.py
      service.py
      routes.py
      repositories.py
      repair_pack.py
      review_issue_chain.py

    evaluation/
      models.py
      service.py
      routes.py
      discovery.py
      metrics.py
      replay.py

  skills/
    registry.py
    runtime.py
    metadata.py
    bundles/
      manage_cost/
      manage_crop_cycle/
      manage_workers/
      weather/
      web_search/

  ops/
    seed.py
    schema_audit.py
    migrations/
```

## 4. 现有目录映射

| 当前目录/文件 | 目标位置 | 说明 |
| --- | --- | --- |
| `core/config.py`、`core/settings/*` | `shared/config.py` | 配置聚合到单文件，不为几十行 settings 子文件保留子包 |
| `core/database.py` | `shared/database.py` | 基础设施 |
| `core/llm*.py` | `shared/llm.py` | LLM 客户端基础设施，当前合并后仍低于 1000 行 |
| `core/compat.py` | `shared/compatibility.py` | 仅保留 Python 版本兼容，不做旧 import 壳 |
| `core/seed.py`、`seed/system_crop_templates.py` | `domains/farm/seed.py` 或 `ops/seed.py` | 系统模板 seed 属于业务初始化，不占一级模块 |
| `models/*.py` | `domains/*/models.py` 或 `platforms/*/models.py` | 按实体归属迁移 |
| `schemas/*.py` | `domains/*/schemas.py` 或 `platforms/*/schemas.py` | 与对应领域放一起 |
| `services/*_service.py` | `domains/*/service.py` | 领域内合并，避免技术层大杂烩 |
| `api/*.py` | `domains/*/routes.py` 或 `platforms/*/routes.py` | `api/` 最终只做聚合注册或下线 |
| `scripts/schema_hardening_audit.py` | `ops/schema_audit.py` | 运维工具 |
| `modules/auth`、`modules/farm` | `domains/users`、`domains/farm` | 避免 `modules` 空壳层 |
| `platforms/data_flywheel/*` | 保留在 `platforms/data_flywheel` | 允许 1000 行以内文件存在 |
| `platforms/evaluation/*` | 保留在 `platforms/evaluation` | 评测是平台能力，不进入 `domains` |

## 5. models 与 schemas 的处理

`models/` 和 `schemas/` 当前是全局技术目录，适合早期项目，但现在会造成三类问题：

- 找业务要跨 `models/`、`schemas/`、`services/`、`api/` 四处跳。
- 新增实体时容易只按文件名拆，而不是按领域边界思考。
- 小模型、小 schema 文件大量堆积。

新规则：

- 每个领域优先保留一个 `models.py` 和一个 `schemas.py`。
- 同一领域内的多个小模型合并到同一个文件，例如 `farm.py`、`crop.py`、`cycle.py` 可先进入 `domains/planting/models.py` 或按业务判断分到 `farm` / `planting`。
- 只有当领域模型文件超过 1000 行，或某个子领域需要独立迁移/测试，才拆为子包。
- SQLAlchemy ORM 与 Pydantic schema 不混在一个文件，除非是极小内部 DTO。

## 6. core 目录收束

`core/` 曾包含配置、DB、日志、LLM、时间、兼容、seed 等不同性质内容。新设计中改为 `shared/`：

- `shared/config.py`：对外暴露 `settings`，内部可保留 `shared/config/*`，但不为几十行文件拆子包。
- `shared/database.py`：DB session、engine、Base。
- `shared/logging.py`：日志初始化和获取 logger。
- `shared/llm.py`：LLM client manager、config watcher、factory 可先合并，超过 1000 行再拆。
- `shared/time.py`：timezone、date context、UTC helper。
- `shared/compatibility.py`：仅保留 Python 3.10/3.11 兼容能力。

不再让 seed、业务 helper 或一次性脚本进入 `shared`。
不再保留 `app.core.*` 兼容入口；活动代码和测试应直接导入 `app.shared.*`。

## 7. 小工具与空目录

### 7.1 seed/scripts

- `seed/` 不作为一级业务模块。
- 系统作物模板 seed 若是业务初始化，迁到 `domains/farm/seed.py`。
- schema hardening audit、迁移辅助等放入 `ops/`。

### 7.2 只含 `__init__.py` 的目录

优先清理：

- `backend/app/modules`
- 空壳 `backend/app/platforms` 若没有导出职责，可仅保留真实子目录，不写多余逻辑。

谨慎清理：

- `backend/app/skills/*` 目录。部分 skill 目录可能依赖文件系统扫描、registry 或外部脚本布局，清理前必须审计 `SkillManager` 和 registry YAML。

## 8. 迁移顺序

### 阶段 A：规则与文档先行

1. 更新复杂度预算：生产代码 1000 行，单函数 80 行预警。
2. 更新 `AGENTS.md`、`.claude/rules/python-style.md`、复杂度脚本文案。
3. 明确“不要为了 500 行硬拆”的准则。

### 阶段 B：低风险收束

1. 建立 `shared/`，从 `core/` 迁移纯基础设施。
2. 合并 `core` 中 20-80 行碎片文件。
3. 把 `seed/`、`scripts/` 收到 `ops/` 或对应领域。
4. 删除只含 `__init__.py` 且无扫描依赖的空目录。

### 阶段 C：领域聚合

1. 建立 `domains/farm`、`domains/planting`、`domains/finance`、`domains/conversation`、`domains/weather`、`domains/users`。
2. 迁移 `models/`、`schemas/`、`services/`、`api/` 到对应领域。
3. 每轮只迁一个领域，迁完删除旧路径，不新增兼容壳。

### 阶段 D：平台目录整理

1. 保留 `platforms/data_flywheel` 和 `platforms/evaluation`。
2. 不再强拆 500-1000 行文件，改为按职责混杂度判断。
3. 将 DataFlywheel 的全局模型/schema 逐步收进平台目录。

### 阶段 E：治理 sensor

1. 新增目录必须说明领域或平台归属。
2. 新增 `Protocol/ABC` 必须证明至少两个实现或明确外部适配边界。
3. 新增 backend 实现必须证明生产使用点。

## 9. 推荐第一轮 PR

第一轮不迁业务大域，先做规则和低风险结构：

1. 修改复杂度预算为 1000 行生产文件阈值。
2. 建立 `shared/`，先迁入低风险 Python 兼容工具 `shared/compatibility.py`，不做 core 全量迁移。
3. 将 `core/seed.py`、`seed/system_crop_templates.py`、`scripts/schema_hardening_audit.py` 归入 `ops/`。
4. 清理无使用点的空目录；若扫描无空目录，则记录为本轮无清理对象。
5. 更新两份既有 spec 的整改方向：从“继续拆巨石”改为“领域聚合 + 合并碎片”。

### 9.1 Round 1 落地记录（2026-07-18）

- 复杂度规则已切到生产 Python 文件 1000 行硬上限，500-1000 行只作为观察区间。
- `backend/app/ops/` 已承接启动 seed、系统作物模板 seed 和 schema hardening audit；旧 `app.seed`、`app.scripts`、`app.core.seed` 活动引用清空，不保留兼容入口。
- `backend/app/shared/compatibility.py` 已承接 Python 3.10/3.11 兼容工具；旧 `app.core.compat` 活动引用清空，不保留兼容入口。
- `platforms/data_flywheel/service.py` 的响应序列化 helper 已归入 `service_serializers.py`，唯一超过 1000 行的生产文件降至 1000 行以内。
- `models/` / `schemas/` 本轮未做大规模迁移；后续按单一领域或平台能力逐批收束。

这轮 PR 的目标是建立新规则，而不是一次性移动所有 models/schemas。

### 9.2 Round 2 落地记录（2026-07-18）

- `backend/app/shared/config.py` 已承接 `core/config.py` 与 `core/settings/*`：统一暴露
  `Settings`、`settings`、`AIConfig`、`StorageConfig`、`MongoConfig`、助手角色配置等 public symbols。
- `backend/app/shared/database.py` 已承接 `core/database.py` 与 `core/dependencies.py`：
  统一暴露 `Base`、`engine`、`SessionLocal`、`get_db`。
- `backend/app/shared/time.py` 已承接 `core/timezone.py` 与 `core/date_context.py`：
  统一暴露北京时间工具与请求日期 ContextVar。
- `backend/app/shared/logging.py` 已承接日志初始化、`get_logger`、`request_id_var`。
- `backend/app/shared/llm.py` 已承接 `core/llm.py`、`core/llm_client_manager.py`、
  `core/llm_config_watcher.py`，保留 LLM factory、manager、熔断、热更新和 watcher 能力。
- `backend/app/shared/json_repair.py` 已承接 JSON 提取、修复和安全解析工具。
- 旧 `backend/app/core` 目录已删除，不保留 `app.core.*` re-export 壳；活动代码与测试的
  `app.core.*` 扫描结果为空。
- 本轮仍不做 `models/` / `schemas/` 全站领域迁移；后续按单一领域或平台能力逐批收束。

### 9.3 Round 3 落地记录（2026-07-19）

- 新增 `backend/app/domains/`，承接 `users`、`farm`、`weather`、`finance`、
  `planting`、`conversation` 六个业务领域。
- 旧 `backend/app/modules/auth` 已迁入 `domains/users`；旧
  `backend/app/modules/farm` 已迁入 `domains/farm`；`backend/app/modules`
  目录删除，不保留兼容入口。
- 旧 `backend/app/api` 路由按领域或平台迁出：业务路由进入 `domains/*/*routes.py`，
  admin 路由进入 `platforms/admin`，simulation 路由进入 `platforms/simulation`。
- 旧 `backend/app/models`、`backend/app/schemas`、`backend/app/services` 已清空删除；
  ORM / schema / service 按领域、平台或 shared 真实边界归位。
- `simulation/` 已收束到 `platforms/simulation`；运行时 dataclass 保持
  `platforms/simulation/models.py`，ORM 表模型为 `platforms/simulation/orm_models.py`。
- Alembic metadata 加载改为 `app.shared.model_registry`，只负责导入真实模型模块以注册
  SQLAlchemy metadata，不提供旧 `app.models` re-export。
- `scripts/check-layer-deps.sh` 已增加旧目录和旧 import sensor，阻止
  `app.api`、`app.models`、`app.schemas`、`app.services`、`app.modules`、
  `app.simulation` 回潮。

#### Round 3 剩余未迁清单

- `context/`、`memory/`、`prompt/` 仍保留顶层平台工程目录。它们属于 Agent 上下文工程、
  记忆工程和 Prompt 治理，不是单一业务领域；直接迁入 `agent/` 会扩大 runtime 依赖面，
  需后续按平台边界专项评审。
- `infra/` 仍保留顶层基础设施目录。`online_document_*`、trace、pending action 等仍是
  多存储/运行时基础设施，贸然并入领域会隐藏横切依赖；后续应按 shared persistence 或
  agent/platform 子域继续收束。
- `application/` 和 `skills/` 仍保留顶层。它们分别承载业务编排层和 Agent 可调用业务能力，
  本轮仅更新其 import 到新的 domains 路径，不改变执行协议。

## 10. 风险与缓解

| 风险 | 缓解 |
| --- | --- |
| 大量 import 迁移导致回归 | 每轮只迁一个领域；先迁测试和生产 import，再删除旧路径 |
| skills 目录被误清 | 清理前审计 registry 和文件系统扫描逻辑；没有证据不删除 |
| 领域划分争议 | 先迁边界清晰的 farm/finance/weather，planting 和 conversation 放后 |
| `models` 全局依赖太多 | 允许过渡期保留 `models/`，但禁止新增模型到全局目录 |
| 1000 行规则被滥用 | 超 800 行要求文件头或文档说明职责；超 1000 行必须拆 |

## 11. 完成判定

- `backend/app` 一级目录数量减少，`core`、`models`、`schemas`、`services`、`api` 的职责逐步被领域目录吸收。
- 新增代码能从目录路径看出业务归属。
- 20-50 行碎片文件明显减少。
- 生产代码不再因 500 行预算被迫假拆。
- CI 仍能阻止真正失控的超大文件、单函数巨石和无使用点抽象。
