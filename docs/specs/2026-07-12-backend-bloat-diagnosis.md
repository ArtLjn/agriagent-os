# Backend Bloat Diagnosis Report

## 文档信息

| 项 | 内容 |
| --- | --- |
| 路径 | [docs/specs/2026-07-12-backend-bloat-diagnosis.md](./2026-07-12-backend-bloat-diagnosis.md) |
| 创建日期 | 2026-07-12 |
| 类型 | 分析报告 + 整改追踪（Diagnosis & Remediation Tracking） |
| 分析对象 | `backend/app/` 全量代码 |
| 关联文档 | [2026-07-12-agent-module-remediation.md](./2026-07-12-agent-module-remediation.md)（agent 模块整改 spec） |
| 关联 spec | [2026-07-10-skill-capability-governance-design.md](./2026-07-10-skill-capability-governance-design.md) |
| 关联设计 | [2026-07-14-backend-directory-redesign.md](./2026-07-14-backend-directory-redesign.md)（目标架构与 5 大决策迁移路径） |
| 最近更新 | 2026-07-18（补充 P3-1 classifier 第二阶段拆分进度） |

本报告最初（2026-07-12）只做诊断与量化。**2026-07-14 起扩展为整改追踪文档**：
新增"发现 9：过度设计与不稳定因素"与"整改计划追踪"章节。
后续每个整改项的启动、进度、完成都更新到末尾的 [整改计划追踪](#整改计划追踪) 章节。

## 分析方法

| 维度 | 采集方式 |
| --- | --- |
| 文件数与行数 | `find app/ -type f -name "*.py" -exec wc -l {} +` |
| 超限文件 | `awk '$1 > 500'` |
| 微型文件 | `awk '$1 <= 30'`（排除 `__init__.py`） |
| 空目录 | `find app/ -type d -empty` |
| 测试根污染 | `ls tests/*.db tests/*.db-* tests/test_*.py` |
| 死代码 | `grep -rn "from app.agent.X "` 反向核对 |
| 重复抽象 | 命名前缀聚类（`*_service.py`、`*_router.py`、`*_repository.py`） |

所有数据采集时间：2026-07-12，基于分支 `codex/refactor-skill-capability-registry`。

## 总量概览

| 指标 | 数值 |
| --- | --- |
| 应用代码文件数 | **450 个 `.py` 文件** |
| 应用代码总行数 | **61,248 行** |
| 测试代码文件数 | 234 个 `.py` 文件 |
| 超限文件数（> 500 行） | **14 个** |
| 空目录数 | **4 个** |
| 微型文件数（≤ 30 行非 init） | **43 个** |
| `*_service.py` 文件数（backend 全量） | 26 个 |

## 模块分布

按文件数与行数降序：

| 模块 | 文件数 | 行数 | 行占比 | 健康度 |
| --- | --- | --- | --- | --- |
| `agent/` | 184 | 20,301 | 33.2% | 🔴 已单独分析（详见 agent-module-remediation spec） |
| `modules/` | 40 | 9,947 | 16.3% | 🔴 `data_flywheel` 独占 91% |
| `services/` | 40 | 9,736 | 15.9% | 🟡 26 个 *_service.py，可能过度细化 |
| `infra/` | 25 | 5,156 | 8.4% | 🟡 2 个文件 > 500 行 |
| `api/` | 21 | 3,279 | 5.4% | 🟢 |
| `evaluation/` | 24 | 2,414 | 3.9% | 🟡 1 个文件 > 500 行 |
| `schemas/` | 15 | 1,799 | 2.9% | 🟢 |
| `context/` | 21 | 1,732 | 2.8% | 🟢 |
| `simulation/` | 9 | 1,389 | 2.3% | 🟢 |
| `core/` | 16 | 1,268 | 2.1% | 🟢 |
| `models/` | 22 | 1,295 | 2.1% | 🟢 |
| `memory/` | 10 | 1,050 | 1.7% | 🟡 2 个空子目录 |
| `prompt/` | 8 | 619 | 1.0% | 🟢 |
| `bootstrap/` | 6 | 332 | 0.5% | 🟢 |
| `seed/` | 2 | 369 | 0.6% | 🟢 |
| `scripts/` | 2 | 445 | 0.7% | 🟡 与项目根 `scripts/` 边界模糊 |
| `observability/` | 3 | 77 | 0.1% | 🟡 太小，可考虑合并 |
| `logs/` | 0 | 0 | 0% | 🟡 74 MB 本地日志（gitignored，非仓库污染） |

**核心结论**：`agent/` + `modules/data_flywheel` + `services/` 三个热点占 65.4% 代码量。

> 2026-07-17 状态补充：上方统计与后续“发现”章节保留 2026-07-12 快照的当时路径，
> 不回写历史行数。DataFlywheel 真实代码已在 A5 迁入 `platforms/data_flywheel/`，
> 旧 DataFlywheel 根包已在 2026-07-17 清理，下游使用平台真实路径。
`agent/` 已有独立整改 spec；其余两个为本报告新发现的重灾区。

## 关键发现

### 发现 1：超限文件全清单（14 个 > 500 行）

按行数降序：

| # | 行数 | 文件 | 所属模块 | 已在整改 spec？ |
| --- | --- | --- | --- | --- |
| 1 | 1345 | [app/agent/runtime/tool_executor.py](../../backend/app/agent/runtime/tool_executor.py) | agent | ✅ |
| 2 | 1049 | [app/agent/runtime/nodes.py](../../backend/app/agent/runtime/nodes.py) | agent | ✅ |
| 3 | 1045 | [app/modules/data_flywheel/service.py](../../backend/app/modules/data_flywheel/service.py) | data_flywheel | ❌ |
| 4 | 1014 | [app/modules/data_flywheel/review_issue_chain_service.py](../../backend/app/modules/data_flywheel/review_issue_chain_service.py) | data_flywheel | ❌ |
| 5 | 789 | [app/agent/router/classifier.py](../../backend/app/agent/router/classifier.py) | agent | ✅ |
| 6 | 662 | [app/modules/data_flywheel/repair_pack_repository.py](../../backend/app/modules/data_flywheel/repair_pack_repository.py) | data_flywheel | ❌ |
| 7 | 630 | [app/modules/data_flywheel/repair_pack_service.py](../../backend/app/modules/data_flywheel/repair_pack_service.py) | data_flywheel | ❌ |
| 8 | 547 | [app/evaluation/discovery/rule_engine.py](../../backend/app/evaluation/discovery/rule_engine.py) | evaluation | ❌ |
| 9 | 531 | [app/infra/pending_actions.py](../../backend/app/infra/pending_actions.py) | infra | ❌ |
| 10 | 528 | [app/infra/pending_action_presenter.py](../../backend/app/infra/pending_action_presenter.py) | infra | ❌ |
| 11 | 524 | [app/modules/data_flywheel/review_issue_chain_repository.py](../../backend/app/modules/data_flywheel/review_issue_chain_repository.py) | data_flywheel | ❌ |
| 12 | 515 | [app/application/smart_fill.py](../../backend/app/application/smart_fill.py) | application | ✅ |
| 13 | 508 | [app/agent/executor/pending_actions.py](../../backend/app/agent/executor/pending_actions.py) | agent | ❌（spec 漏列） |
| 14 | 501 | [app/modules/data_flywheel/router.py](../../backend/app/modules/data_flywheel/router.py) | data_flywheel | ❌ |

**关键发现**：

- agent 整改 spec 只覆盖 14 个中的 **4 个**
- `data_flywheel` 一个模块独占 6 个超限文件（占 43%），是最大的整改盲区
- `infra/pending_actions.py` 与 `infra/pending_action_presenter.py` 名字相似、都超限，疑似职责重叠

### 发现 2：`data_flywheel` 是隐藏重灾区

```
app/modules/data_flywheel/   27 files  9,034 lines  (占 modules/ 的 91%)
```

#### 2.1 6 个文件超 500 行

见上表 #3、#4、#6、#7、#11、#14。

#### 2.2 内部出现"_helpers"切片文件

[review_issue_chain_helpers.py](../../backend/app/modules/data_flywheel/review_issue_chain_helpers.py) 378 行——
命名模式与旧 chat helpers 切片一致，
是"主类太大把私有方法外移"的典型切片式拆分。

#### 2.3 同模块内"分层"过度

一个 `modules/` 子目录内同时承载：

| 关注点 | 文件 |
| --- | --- |
| 主服务 | `service.py` (1045) |
| 子服务 | `repair_pack_service.py` (630)、`review_issue_chain_service.py` (1014)、`session_sync_service.py` (393)、`judge_service.py` (380)、`session_review_service.py` (52) |
| 数据访问 | `repair_pack_repository.py` (662)、`review_issue_chain_repository.py` (524)、`issue_repository.py` (222)、`document_repositories.py` (61) |
| HTTP 路由 | `router.py` (501)、`repair_packs_router.py` (270)、`review_issue_chains_router.py` (248)、`annotations_router.py` (212) |
| 业务对象 | `case_builder.py`、`review_issue_chain_case.py`、`repair_pack_chain.py`、`repair_pack_readme.py` |
| 工具/辅助 | `review_issue_chain_helpers.py` (378)、`review_issue_chain_repair.py` (144)、`document_repository_*` 系列 5 个文件 |

模块内部实质上自建了一套"service / repository / router / case / helpers"分层，
与 `app/services/`、`app/infra/`、`app/api/` 顶层分层**重复**。

#### 2.4 同时存在多个文档存储实现

| 文件 | 行数 | 角色 |
| --- | --- | --- |
| `document_repository_mongo.py` | 313 | MongoDB 实现 |
| `document_repository_mysql.py` | 318 | MySQL 实现 |
| `document_repository_dual.py` | 267 | 双写实现 |
| `document_repository_selector.py` | 84 | 选择器 |
| `document_repository_common.py` | 259 | 共用 |

同一关注点拆 5 个文件，是否真正必要需要业务确认。如果是为了 MongoDB 迁移期
的过渡设计，应在迁移完成后收敛。

### 发现 3：`services/` 26 个 `*_service.py` 疑似过度细化

backend 全量 26 个 `*_service.py`，分布：

| 位置 | 数量 |
| --- | --- |
| `app/services/` | 21 个 |
| `app/modules/data_flywheel/` | 5 个 |
| `app/memory/service.py` | 1 个 |

`app/services/` 21 个 service 完整名单：

```
agent_report_service.py    agent_service.py          agent_turn_service.py
conversation_service.py    cost_category_service.py  cost_service.py
crop_service.py            cycle_service.py          debt_service.py
farm_context_service.py    feedback_service.py       labor_service.py
log_service.py             pending_plan_service.py   planting_read_service.py
planting_service.py        quota_service.py          report_data_service.py
session_dataset_service.py session_debug_export_service.py
weather_service.py
```

#### 可疑的成对/成组服务

| 组 | 文件 | 怀疑 |
| --- | --- | --- |
| cost | `cost_service.py` + `cost_category_service.py` | 是否应合并为 `manage_cost`？ |
| crop | `crop_service.py` + `cycle_service.py` + `planting_service.py` + `planting_read_service.py` | 4 个相关服务，边界模糊 |
| agent | `agent_service.py` + `agent_report_service.py` + `agent_turn_service.py` | 3 个 agent 相关 service 散在 `services/`，而 agent 模块本身已有 184 文件 |
| session | `session_dataset_service.py` + `session_debug_export_service.py` + `conversation_service.py` | 会话相关 3 服务 |
| planting | `planting_service.py` (499) + `planting_read_service.py` | 读写分离还是切片？ |

**判断**：典型"一个实体一个 service"反模式。配合项目硬规则"三次重复再抽象、
没有第二个实现不新增抽象"看，存在过度细化嫌疑，但具体合并方向需业务方确认。

### 发现 4：空目录（4 个，违反防污染规则）

```
app/memory/long_term/      ← 空子目录
app/memory/retrieval/      ← 空子目录
app/agent/response/        ← 已纳入整改 spec
app/agent/sessions/        ← 已纳入整改 spec
```

`app/memory/long_term/` 与 `app/memory/retrieval/` 疑似是为未来功能预留的占位，
但 [python-style.md](../../.claude/rules/python-style.md) 与 [CLAUDE.md](../../.claude/CLAUDE.md) 第 7 条硬规则
都明确禁止工作区污染。建议删除，或加 `.gitkeep` + 在 README 中说明用途。

### 发现 5：本地测试 artifact 污染（已 gitignored）

```
backend/tests/   78 个 test_*.py 直接堆在根目录
                 35 个 *.db / *.db-shm / *.db-wal 本地 SQLite artifact
```

| 项 | 是否 tracked by git | 是否本地污染 |
| --- | --- | --- |
| `tests/*.db` 系列 | ❌ gitignored（`.gitignore` 含 `*.db`） | ✅ 本地工作区污染 |
| `tests/test_*.py` 根散放 | ✅ tracked | ✅ 仓库组织违规 |

**核心问题不是 .db 文件**（已被 gitignore），而是 **78 个 test_*.py 散落在 tests/ 根**违反
"tests/ 镜像源码结构"的规范。应有 14 个测试子目录（agent/、services/、api/ 等），
但根目录仍有 78 个文件未下沉。

### 发现 6：本地日志污染（已 gitignored）

```
backend/app/logs/   74 MB 本地日志文件
                   最早 2026-05-30，最近 2026-07-12
                   单文件最大 10 MB（app.log.2）
```

| 项 | 是否 tracked | 是否本地污染 |
| --- | --- | --- |
| `app/logs/*.log*` | ❌ gitignored（`.gitignore` 含 `logs/`） | ✅ 本地磁盘污染 |

不进入仓库，但本地工作区累积 74 MB 日志属于运维问题：

- 没有日志轮转上限配置（logrotate 缺失）
- `app.log.2` 单文件 10 MB 说明 rotation 阈值过高
- 长期累积会消耗开发者磁盘

### 发现 7：微型文件过多（43 个 ≤ 30 行非 init）

样本（完整名单见附录 A）：

```
5   app/observability/__init__.py
8   app/agent/runtime/errors.py
14  app/skills/context.py
15  app/agent/planner/__init__.py
17  app/agent/planner/models.py
18  app/agent/runtime/quota.py
19  app/agent/executor/tool_calls.py
19  旧 response_trace.py 切片（已在 P0-6 合并删除）
19  旧 context_invalidation.py 切片（已在 P0-6 合并删除）
20  app/agent/runtime/graph_factory.py
21  旧 context_memory.py 切片（已在 P0-6 合并删除）
...
```

微型文件不一定都是问题（如 `__init__.py` 是包标记），但 43 个中大部分是
"单一函数文件"或"re-export 文件"，属于同关注点切片。典型案例已在
agent-module-remediation spec 的 R2.3 章节列出。

### 发现 8：模块边界模糊

#### 8.1 `core/` 与 `infra/` 边界

```
core/   16 files / 1268 lines   ← 业务无关核心
infra/  25 files / 5156 lines   ← 基础设施
```

两者定义重叠：`infra/pending_actions.py` (531) 与 `infra/pending_action_presenter.py` (528)
属于"业务基础设施"还是"业务逻辑"？项目 [CLAUDE.md](../../.claude/CLAUDE.md) 第 7 条提到的依赖方向
是 `api → application/modules/platform → shared/core/models/infra`，把 infra 和 core 都放在底层。
但实际 infra/ 内部出现了 500+ 行业务逻辑文件，与"基础设施"语义不符。

#### 8.2 `app/scripts/` 与项目根 `scripts/` 重叠

| 位置 | 文件数 | 用途 |
| --- | --- | --- |
| `backend/app/scripts/` | 2 | 应用级脚本 |
| `backend/scripts/` | 10 | 工程级脚本（lint、check、deploy） |

两个 scripts 目录用途区分不清，新脚本该放哪里缺乏规则。

#### 8.3 `observability/` 太小

```
app/observability/   3 files  77 lines
  __init__.py     5 lines
  lifecycle.py   20 lines
  metrics.py     52 lines
```

单独成包的收益不明显，可考虑：

- 合并到 `core/`
- 或合并到 `infra/`
- 或保留但明确未来扩展计划

### 发现 9：过度设计与不稳定因素（2026-07-14 扩展）

> 本节扩展自最初诊断。前 8 个发现聚焦"文件大小与组织"等表层结构问题；
> 本节深挖**架构层面的过度设计**及其衍生的**不稳定因素**——这些比文件大小更危险，
> 因为它们会潜伏 bug、放大改动成本、制造认知迷雾。

#### 9.0 采集方法

| 维度 | 采集方式 |
| --- | --- |
| Protocol / ABC / abstractmethod | `grep -rn "class.*Protocol\|abstractmethod" backend/app --include="*.py"` |
| 单实现 Protocol 核对 | 人工核对每个 Protocol 的实现类数量 |
| 兼容层 / 双写层 | `find backend/app -name "*compat*" -o -name "*dual*" -o -name "*legacy*" -o -name "*fallback*"` |
| Repository 多后端 | `find backend/app -name "document_repository*"` + 对照 `config.yaml` |
| 实际使用核对 | `grep -rn "from app.X" backend/` 反向追溯 |

#### 9.1 过度设计清单（按杀伤力排序）

##### 🔴 #1 `ContextSelector` Protocol 重复定义 2 次

```python
# context/policy.py:33
class ContextSelector(Protocol):
    def select(self, **kwargs) -> list[ContextBlock]: ...

# context/builder.py:41  ← 逐字相同
class ContextSelector(Protocol):
    def select(self, **kwargs) -> list[ContextBlock]: ...
```

**不稳定因素**：
- 改签名要同步改 2 处定义，漏改一处 IDE 不报错
- `from app.context.policy import ContextSelector` 与 `from app.context.builder import ContextSelector` 走两个 namespace，mypy 视角下是"两个类型"
- 调用方 import 路径混乱，重构易破坏

##### 🔴 #2 `document_repository` 16 个实现类，生产配置实际只用 mongo

```yaml
# backend/config.yaml 当前运行配置
storage:
  trace: "mongo"
  case_drafts: "mongo"
  # ... 全部 mongo
```

注意：`app/core/settings/models.py` 中 storage 默认值仍是 `mysql`，测试与无配置启动路径可能
依赖默认值。删除 MySQL / Dual / MongoRead 实现前，必须同时确认生产配置、测试默认、回滚策略
和 MongoDB 迁移 OpenSpec 状态，不能只凭 `config.yaml` 一处判断。

```python
# document_repository_selector.py 维护 4 种 backend × 4 个对象 = 16 个类
"MySQLPrelabelRepository", "MongoPrelabelRepository",
"DualWritePrelabelRepository", "MongoReadPrelabelRepository",
# × 4 对象
```

**不稳定因素**：
- **12 个未使用的实现类** 仍在测试覆盖里 → 改 schema 时所有 backend 都要同步，漏一个就 CI 红
- dual-write 的失败处理路径几乎不会被走到 → 潜伏数据不一致 bug
- "为迁移设计"已变成"迁移完没收尾" → 新人不知道生产用 mysql 还是 mongo
- 每加一个 data_flywheel 对象要写 4 套实现 → 新功能成本 ×4

##### 🔴 #3 `planner/` 死代码与 `planning/` 命名混淆

```
agent/planner/    # 63 行，0 外部引用
agent/runtime/planning/   # PlanDraft / DomainValidator 已收拢到 runtime planning 边界
```

**不稳定因素**：
- 两个目录名字几乎一样，IDE 跳转经常跳错
- `planner/` 是旧规划入口，当前未找到外部消费者，可作为删除候选
- `planning/` 不是死目录，`PlanDraft`、`DomainValidator` 与 `attach_validation` 已迁移到 `runtime/planning/`
- 真正问题是命名太近、职责边界不清：一个可删，一个应迁移/收敛到 runtime planning 能力，不能打包删除

##### 🟠 #4 `MemoryServicePort` Protocol 只有 1 个实现

```python
# memory/ports.py:9
class MemoryServicePort(Protocol): ...

# memory/service.py:52
class InMemoryMemoryService: ...  # 唯一实现
```

**违反** CLAUDE.md 第 7 条 + python-style.md "没有第二个实现不新增抽象"。

**不稳定因素**：
- Protocol 永远只有 1 个实现 → Protocol 改了实现没改也不报错（duck typing）
- 新加方法时不知道该加在 Protocol 还是实现上 → Protocol 易谎报能力

##### 🟠 #5 `infra/online_document_common.py` 一个文件 3 个 Protocol

```python
class ConversationMessageRepository(Protocol)
class AgentRecordRepository(Protocol)
class GuardrailsLogRepository(Protocol)
```

**不稳定因素**：与 #2 同源——为 mongo/mysql 切换设计，但实际只用 mongo。3 个 Protocol 各自有 mysql/mongo 实现，**mysql 实现是死代码**。

##### 🟠 #6 `_ComparableStage(Protocol)` 单文件内的局部 Protocol

`services/crop_service.py:19` 一个下划线开头的 Protocol，作者自己都觉得是临时/私有。

**不稳定因素**：类型约束本可用 `TypeVar` 或 `Any` 解决，多一层 Protocol 后下游用法反而被绑死。

##### 🟡 #7 `context/selectors/` 目录与 `document_repository_selector.py` 命名空间冲突

```
context/selectors/                       ← 目录，3 个 selector 文件
modules/data_flywheel/..._selector.py    ← 文件，build_data_flywheel_repository
```

**不稳定因素**：IDE 搜 "selector" 出 6+ 个不相关结果，认知负担高。

##### 🟡 #8 `core/compat.py` 可能已不必要

```python
try:
    from enum import StrEnum as StrEnum
except ImportError:
    class StrEnum(str, Enum): ...  # Python 3.10 兼容
```

被 9 个文件引用。若项目 `python_requires` ≥ 3.11，这整个文件是死代码。

**不稳定因素**：兼容层一旦失去目标版本，会变成"看起来很重要其实没用"的认知陷阱。

#### 9.2 不稳定因素汇总

| 因素 | 触发场景 | 当前典型例子 |
| --- | --- | --- |
| **认知不稳定** | 改概念要在 N 处同步 | `ContextSelector` ×2、`planner/` vs `planning/` |
| **行为不稳定** | 多 backend / dual-write 路径潜伏 bug | `document_repository_*` 16 类、`online_document_*` 3 Protocol |
| **演进不稳定** | 加新对象要改 N 处 | data_flywheel 新增一类要写 4 套 backend |
| **测试不稳定** | 测了不用、用了没测 | 12 个未使用 Repository 仍占测试覆盖 |
| **死代码不稳定** | 谁都不敢删但又改不动 | `planner/`、`MemoryServicePort`；`planning/` 需迁移/收敛但不可直接删除 |
| **命名不稳定** | IDE 跳转跳错 | `selector.py` vs `selectors/`、两个 `ContextSelector` |

#### 9.3 最危险的两类

> **#2 document_repository 与 #3 planner/planning 命名混淆** 是最高优先级。
> 一个制造潜伏 bug（dual-write 路径不常走），
> 一个制造认知迷雾（一个旧目录可删、一个运行时仍在用）。
> 根治掉这两类，"沉重感"会断崖式下降。

#### 9.4 量化

| 指标 | 数值 |
| --- | --- |
| Protocol / ABC 总数 | **22 个** |
| 重复定义的 Protocol | **1 个**（`ContextSelector` 在 2 个文件） |
| 单实现 Protocol（疑似过度抽象） | **≥ 2 个**（`MemoryServicePort`、`_ComparableStage`） |
| 多后端 Repository 类总数 | **16 个**（4 对象 × 4 backend） |
| 多后端中实际未使用的实现 | **~12 个**（生产 config 全 mongo） |
| 兼容层 / 双写层文件 | **7 个**（compat / dual / fallback / adapter / selector 类） |
| 疑似死代码目录 | **1 个**（`agent/planner/`）；`agent/planning/` 已收敛到 runtime planning 边界 |

## 量化诊断

### 与项目硬规则对照

| 项目硬规则 | 当前状态 | 缺口 |
| --- | --- | --- |
| 单文件 ≤ 500 行 | 14 个文件违规 | 🔴 严重 |
| 单方法 ≤ 50 行 | 未全量扫描 | ⚠ 待量化 |
| 类 ≤ 200 行 | 未全量扫描 | ⚠ 待量化 |
| 删除不再使用的代码 | 4 个空目录、`planner/` 死代码 | 🔴 已识别 |
| 三次重复再抽象 | 26 个 `*_service.py` | 🟡 需评审 |
| 没有第二个实现不新增抽象 | 5 个 `document_repository_*` | 🟡 需评审 |

### 模块健康度评分

| 模块 | 文件数 | 行数 | 超限文件 | 空目录 | 死代码 | 评分 |
| --- | --- | --- | --- | --- | --- | --- |
| `agent/` | 184 | 20301 | 5 | 2 | 1 包 | 🔴 重度（已有整改 spec） |
| `modules/data_flywheel/` | 27 | 9034 | 6 | 0 | 未知 | 🔴 重度 |
| `services/` | 40 | 9736 | 0 | 0 | 未知 | 🟡 中度（过度细化） |
| `infra/` | 25 | 5156 | 2 | 0 | 未知 | 🟡 中度 |
| `evaluation/` | 24 | 2414 | 1 | 0 | 未知 | 🟡 中度 |
| `memory/` | 10 | 1050 | 0 | 2 | 未知 | 🟡 中度 |
| `observability/` | 3 | 77 | 0 | 0 | 未知 | 🟡 中度（过小） |
| 其余模块 | — | — | 0 | 0 | 未知 | 🟢 健康 |

## 整改 spec 覆盖度评估

| 超限文件 | 整改 spec 覆盖 | 备注 |
| --- | --- | --- |
| 14 个 > 500 行 | 4 个（agent 部分的 4 个） | **覆盖率 28.6%** |
| 4 个空目录 | 2 个（agent 部分） | **覆盖率 50%** |
| `planner/` 死代码 | ✅ | 已覆盖 |
| `data_flywheel` 重灾区 | ❌ | **0% 覆盖** |
| `services/` 过度细化 | ❌ | **0% 覆盖** |
| `infra/` 双胞胎文件 | ❌ | **0% 覆盖** |
| `evaluation/rule_engine.py` | ❌ | **0% 覆盖** |
| tests/ 根散放 | ❌ | **0% 覆盖** |

**结论**：现有 agent-module-remediation spec 覆盖度严重不足。整改范围需要从
agent 扩充到 backend 全量，建议升级为独立的 backend-module-remediation spec。

> **2026-07-14 更新**：本报告自身已扩展为 backend-level 整改追踪文档，
> 见下方 [整改计划追踪](#整改计划追踪) 章节。该章节按 P0/P1/P2 维护每个整改项的状态。

## 整改计划追踪

> 2026-07-14 新增。每个整改项需更新"状态"列；完成的项注明 commit hash 与验证方式。
> 整改原则：**先减后拆、先合后分**——本阶段禁止新增业务能力或抽象；
> 允许为迁移既有代码创建 `application/`、`skills/`、`platforms/` 等目标目录。

### 整改原则

1. **冻结新增**：整改完成前禁止新增业务 skill / 禁止新增业务子模块 / 禁止新增 Protocol
2. **先减后拆**：先删除死代码与过度设计，再考虑拆分巨石文件
3. **小步提交**：每个 P0/P1 项独立 commit / PR，可独立回滚
4. **CI 验证**：每项整改必须通过 `bash scripts/harness-check.sh` 全套检查
5. **同步本文档**：每项整改启动/完成时更新对应行的"状态"列

### 状态图例

| 图例 | 含义 |
| --- | --- |
| ⏳ | 待启动 |
| 🚧 | 进行中（附 WIP commit） |
| ✅ | 完成（附 commit hash） |
| ❌ | 阻塞（附原因） |
| ⚠️ | 待业务/评审确认 |

### P0 — 立即处理（低风险高收益）

| # | 整改项 | 范围 | 关联发现 | 状态 | 验证方式 |
| --- | --- | --- | --- | --- | --- |
| P0-1 | 删除 `agent/planner/` 整个目录 | `backend/app/agent/planner/`（当前工作树已无版本文件） | 9-#3、4 | ✅ | `rg "app\.agent\.planner|agent\.planner" backend/app backend/tests` 返回空；本工作树待提交 |
| P0-2 | 评估并迁移/收拢 `agent/planning/` | `backend/app/agent/runtime/planning/`（保留 PlanDraft 语义） | 9-#3 | ✅ | `runtime/nodes.py` 与测试 import 已改为 `app.agent.runtime.planning`；`PYTHONDONTWRITEBYTECODE=1 python -m pytest tests/agent/planning/test_plan_draft_models.py::test_runtime_planning_exports_plan_draft_contract -q` 通过；本工作树待提交 |
| P0-3 | 合并 `ContextSelector` Protocol 双定义 | `context/policy.py`、`context/builder.py` | 9-#1 | ✅ e481ee56 | `ContextSelector` 仅保留 `app.context.policy.ContextSelector`；builder 只在 `TYPE_CHECKING` 下引用；`PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider tests/context/test_context_selector_protocol.py -q` 通过；`PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider tests/context/test_context_selector_protocol.py tests/agent/test_chat_use_case.py -q` 因本地 MySQL `localhost:3306` 不可用失败（11 failed, 10 passed）；`ruff check backend/app backend/tests`、`bash scripts/check-complexity-budget.sh` 通过 |
| P0-4 | 合并 runtime 顶部碎片 | `agent/runtime/{errors,quota,graph_factory}.py` | 7、附录 A | ✅ 568529e7 | 合并为 `agent/runtime/support.py`，旧碎片已删除且旧 import 搜索为空；`PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider tests/agent/runtime/test_runtime_support.py -q` 通过；`PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider tests/agent/runtime/test_runtime_support.py tests/agent/test_chat_use_case.py -q` 因本地 MySQL `localhost:3306` 不可用失败（11 failed, 10 passed）；`ruff check backend/app backend/tests`、`bash scripts/check-complexity-budget.sh` 通过 |
| P0-5 | 合并 `observability/` 整包 | `observability/{__init__,lifecycle,metrics}.py` | 8.3 | ✅ 54960408 | 平铺为 `observability.py` 单文件；旧 `app.observability.lifecycle/metrics` import 搜索为空；`PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider tests/observability/test_observability_module.py -q` 通过；`PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider tests/memory/test_maybe_summarize.py tests/memory/test_summarizer.py tests/evaluation/test_trace_events.py -q` 通过；`ruff check backend/app backend/tests`、`bash scripts/check-complexity-budget.sh` 通过（复杂度检查保留既有警告） |
| P0-6 | 合并旧 application 三碎片 | `context_invalidation.py`、`context_memory.py`、`response_trace.py` | 7、附录 A | ✅ a7f23c6a | 已并入 chat helpers，旧碎片已删除且旧 import 搜索为空；chat runtime helper 与 response trace 聚焦测试通过；`PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider tests/agent/test_chat_use_case.py -q` 因本地 MySQL `localhost:3306` 不可用失败（11 failed, 8 passed）；`ruff check backend/app backend/tests`、`bash scripts/check-complexity-budget.sh` 通过（复杂度检查保留既有警告） |

### P1 — 一周内处理（需轻度测试）

| # | 整改项 | 范围 | 关联发现 | 状态 | 验证方式 |
| --- | --- | --- | --- | --- | --- |
| P1-1 | 删除 `MemoryServicePort` Protocol | `backend/app/memory/ports.py` | 9-#4 | ✅ bff22473 | `backend/app/memory/ports.py` 已删除；`rg -n "MemoryServicePort\|MemoryContextProviderPort\|app\\.memory\\.ports\|from app\\.memory\\.ports\|import app\\.memory\\.ports" backend/app backend/tests` 无输出；新增 `tests/memory/test_memory_service_contract.py` 锁住 `InMemoryMemoryService` 运行时方法；`PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider tests/memory/test_memory_service_contract.py -q` 通过（2 passed）；`PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider tests/memory/test_memory_service_contract.py tests/memory/test_memory_service.py tests/test_agent_service.py -q` 因本地 MySQL `localhost:3306` 不可用失败（1 failed, 28 passed），失败用例为 `tests/test_agent_service.py::TestStreamChatWithAgent::test_stream_cycle_confirm_missing_template_creates_template_pending`；`ruff check backend/app backend/tests`、`bash scripts/check-complexity-budget.sh` 通过（复杂度检查保留既有警告） |
| P1-2 | 删除 `_ComparableStage(Protocol)` | `backend/app/services/crop_service.py` | 9-#6 | ✅ 本 worktree/PR 已处理 | `crop_service.py` 已删除私有 `_ComparableStage(Protocol)`，阶段比较改用 `Iterable[Any]` 和显式属性读取；新增 `tests/services/test_crop_service_stage_compare.py` 锁住顺序无关、重复阶段数量保留、`key_tasks` 空白归一化和私有 Protocol 清理；`PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider tests/services/test_crop_service_stage_compare.py tests/test_cost.py tests/api/test_planting_operations.py -q` 通过（35 passed, 1 skipped）；`ruff check backend/app backend/tests` 通过；`bash scripts/check-complexity-budget.sh` 通过（保留既有复杂度预算警告）；`rg "_ComparableStage\|Protocol" backend/app/services/crop_service.py` 无输出 |
| P1-3 | 评估 `core/compat.py` 是否仍必要 | `backend/app/core/compat.py` 及 9 处引用 | 9-#8 | ✅ 已评估：暂保留，待 Python baseline 升级至 3.11+ | `backend/tests/test_python_compat.py` 明确记录生产服务器仍为 Python 3.10，并禁止直接使用标准库 `StrEnum` / `datetime.UTC`；`backend/requirements.txt` 未声明 Python baseline；`backend/Dockerfile` 为 `python:3.11-slim`，但不足以覆盖测试门禁和缺失的包级 baseline；`rg -n "from app\\.core\\.compat import\|app\\.core\\.compat\|\\bUTC\\b\|\\bStrEnum\\b" backend/app backend/tests` 确认当前兼容层仍覆盖 `StrEnum` 与 `UTC` 引用；验证命令：`PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider tests/test_python_compat.py tests/test_config.py tests/test_mongo_config.py -q`、`ruff check backend/app backend/tests`、`bash scripts/check-complexity-budget.sh` |
| P1-4 | 合并 `stream_chat_*` 切片群 | `application/chat/stream_*.py`（5 文件，已从根目录归位） | 7 | ✅ 子包归位完成 / 进一步合并待后续 | `stream_chat_*` 已归入 `application/chat/`，本轮同步删除旧根模块同对象兼容入口；直接合并会让 `stream_chat.py` 超过 500 行预算，后续需先拆职责再收敛为更少文件 |
| P1-5 | `review_issue_chain_*` 切片收回 | `platforms/data_flywheel/review_issue_chain/` | 2.2 | ✅ 子包归位完成 / root 兼容薄壳已下线 | `review_issue_chain/{helpers,case,repair,service}.py` 为真实入口，并拆出 `inbox/operations/cards/builders/queries/support`；生产代码、测试和 monkeypatch target 使用子包真实路径 |
| P1-6 | `repair_pack_*` 切片收回 | `platforms/data_flywheel/repair_pack/` | 2 | ✅ 子包归位完成 / root 兼容薄壳已下线 | `repair_pack/{chain,readme,service}.py` 为真实入口，并拆出 `candidate/constants/redaction`；生产代码、测试和 monkeypatch target 使用子包真实路径 |
| P1-7 | `context/selectors/` 轻量 selector 收束 | `backend/app/context/selectors/` | 9-#7、附录 A | ✅ 已归位并删除旧兼容壳 / 单文件完全合并待后续继续拆职责 | `conversation/cycle/farm/ledger/retrieval/user_settings/weather` 已收束到 `selectors/core.py`，旧子模块兼容壳已删除；新代码使用 `app.context.selectors.core` 或包级 `app.context.selectors`，`memory.py`、`planting.py` 因职责独立与 500 行预算继续保留；`tests/context/test_selector_relocation_compat.py` 覆盖真实入口与包级 API |
| P1-8 | `manage-crop-cycle/scripts/` 小 operation 收束 | `skills/manage-crop-cycle/scripts/` | 7 | ✅ 已归位并删除旧兼容壳 / 重更新逻辑继续独立 | `create_cycle/delete_cycle/query_cycles/query_cycle_info` 已合入 `scripts/main.py`，旧小脚本兼容壳已删除；新代码使用 `app.skills.manage-crop-cycle.scripts.main`，`update_cycle.py`、`update_stage.py` 因职责和行数预算继续保留；`tests/skills/test_manage_crop_cycle_script_compat.py` 覆盖真实入口与重逻辑真实模块 |
| P1-9 | 删除 agent 根兼容壳 | `agent/{advisor,report,skill_coverage,intent_router,tool_selector,tool_selection_rules,llm,assistant_roles}.py` | 7、9-#7 | ✅ 已下线 | 生产代码和普通测试改为真实路径：`app.application.advice.advisor`、`app.application.report`、`app.platforms.evaluation.skill_coverage`、`app.agent.router.*`、`app.core.llm`、`app.core.settings.roles`；不再断言旧路径可 import 或旧 patch target 生效 |

### P2 — 需业务确认（高风险高收益）

| # | 整改项 | 范围 | 关联发现 | 状态 | 验证方式 |
| --- | --- | --- | --- | --- | --- |
| P2-1 | **`document_repository_*` 砍掉 12 个未用 backend 类** | `platforms/data_flywheel/document_repository_*.py`（2026-07-17 A5 已从 `modules/data_flywheel/` 迁入） | 9-#2 | ⚠️ | 确认生产 config、settings 默认、测试路径、回滚策略和 Mongo 迁移状态；保留 `Mongo*`，再删 `MySQL*`/`Dual*`/`MongoRead*` |
| P2-2 | `infra/online_document_common.py` 3 Protocol 同步处理 | `backend/app/infra/online_document_common.py` | 9-#5 | ⚠️ | 与 P2-1 同步决策 |
| P2-3 | `services/` 21 个 `*_service.py` 评估合并 | `backend/app/services/` | 3 | ⚠️ | 业务方确认实体边界 |
| P2-4 | `tests/` 根目录 78 个 test_*.py 下沉 | `backend/tests/` | 5 | ⏳ | 按源码镜像目录重构 |
| P2-5 | 日志轮转配置补全 | `backend/app/logs/` | 6 | ⏳ | 配置 logrotate；磁盘监控 |
| P2-6 | 删除空目录 | `app/memory/long_term/`、`app/memory/retrieval/`、旧 Evaluation 根包、旧 DataFlywheel 根包等 | 4 | ✅ 部分推进 | 2026-07-17 已删除只含 `__init__.py` 的旧 Evaluation / DataFlywheel 空壳包；其余空目录按后续扫描继续处理 |

### P3 — 长期治理（结构性）

| # | 整改项 | 范围 | 关联发现 | 状态 | 验证方式 |
| --- | --- | --- | --- | --- | --- |
| P3-1 | 巨石文件拆分（在合并完成后） | `tool_executor.py` (1517)、`classifier.py` (1233)、`nodes.py` (1049) | 1 | ⏳ | 按 lifecycle / 规则族 / 节点类型分别拆；2026-07-17 第一阶段先拆 `agent/router/policy.py` 的候选选择状态与预算辅助逻辑，以解除 501 行硬错误；同日继续拆 `agent/router/classifier.py`，将 hint 常量迁入 `classifier_hints.py`、无状态 `IntentFrame` 构造迁入 `classifier_frames.py`，`classifier.py` 从 1341 行降至 736 行；同日 `agent/runtime/tool_executor.py` 第一阶段将权限/metadata 决策、operation 解析、读工具 trace/result 归一化迁入 `tool_metadata.py`，`tool_executor.py` 从 1622 行降至 1198 行，不代表 P3-1 全部完成；2026-07-18 第二阶段（PR #29）新增 `agent/runtime/node_helpers.py` 承载 data_source trace、router 决策、prompt budget、LLM response 记录等无状态节点辅助，`nodes.py` 从 1049 行降至 647 行；新增 `agent/runtime/tool_pending_args.py` 与 `agent/runtime/tool_pending.py` 承载 pending 参数补齐、pending plan / pending action 确认与存储辅助，`tool_executor.py` 从 1198 行降至 311 行；2026-07-18 第三阶段（PR #30）新增 `agent/runtime/llm_invocation.py`、`llm_response_repair.py`、`llm_prompt.py`、`llm_node_steps.py`，分别承载 LLM 请求内重试、响应修正、system prompt / context 输入准备、节点后半流程记录，`nodes.py` 从 647 行降至 426 行，低于 500 行，且本轮新增/修改的 runtime 节点拆分文件未新增单函数 >50 行问题；2026-07-18 classifier 第二阶段（PR #待创建）新增 `agent/router/classifier_extractors.py` 承载 worker、工资、作业单参数与证据抽取，新增 `agent/router/classifier_signals.py` 承载 hint/正则信号与规则条件判断，`RuleIntentClassifier` 保留分类流程编排与 frame 组装边界，`classifier.py` 从 736 行降至 158 行，`classifier_frames.py` 保持 478 行未继续增长，新文件分别为 213 / 383 行且未新增单函数 >50 行问题；验证：`PYTHONDONTWRITEBYTECODE=1 ruff check --no-cache backend/app backend/tests` 通过，目标 pytest 179 passed / 4 deselected / 4 warnings，`bash scripts/check-complexity-budget.sh` exit 0（保留 4 类 baseline 警告），`bash scripts/check-layer-deps.sh` exit 0（保留 51 个 baseline/TODO 警告），`git diff --check origin/main...HEAD && git diff --check` 通过；额外行数确认：`classifier.py` 158 行，`classifier_extractors.py` 213 行，`classifier_frames.py` 478 行，`classifier_hints.py` 107 行，`classifier_signals.py` 383 行 |
| P3-2 | 引入"新增 Protocol/ABC 必须列出 ≥2 实现"规则 | `.claude/rules/python-style.md` + CI sensor | 9 | ⏳ | sensor 脚本扫描单实现 Protocol |
| P3-3 | 引入"新增 backend 实现必须证明使用"规则 | `.claude/rules/` + CI sensor | 9-#2 | ⏳ | 与 P3-2 类似；agent 根兼容壳下线后，活跃代码应持续保持旧 import / patch 路径扫描为空 |

## 附录 A：微型文件清单（43 个 ≤ 30 行非 init）

按行数升序（仅列出前 20 个，完整列表由 `find app/ -type f -name "*.py" ! -name "__init__.py" -exec wc -l {} + | awk '$1 <= 30'` 生成）：

```
5   app/observability/__init__.py
8   app/agent/runtime/errors.py
14  app/skills/context.py
15  app/agent/planner/__init__.py
17  app/agent/planner/models.py
18  app/agent/runtime/quota.py
19  app/agent/executor/tool_calls.py
19  旧 response_trace.py 切片（已在 P0-6 合并删除）
19  旧 context_invalidation.py 切片（已在 P0-6 合并删除）
20  app/agent/runtime/graph_factory.py
21  旧 context_memory.py 切片（已在 P0-6 合并删除）
25  app/skills/registry/__init__.py
30  app/application/admin_config_use_case.py
... (其余 23 个略)
```

## 附录 B：数据采集命令复现

为便于未来重新跑诊断，关键命令记录如下：

```bash
cd backend

# 文件数与行数
find app/ -type f -name "*.py" -exec wc -l {} + | tail -1

# 超限文件
find app/ -type f -name "*.py" -exec wc -l {} + \
  | awk '$1 > 500 && $2 != "total"' | sort -n

# 微型文件
find app/ -type f -name "*.py" ! -name "__init__.py" -exec wc -l {} + \
  | awk '$1 <= 30 && $2 != "total"' | sort -n

# 空目录
find app/ -type d -empty

# 服务文件
find app -name "*_service.py"

# 测试根污染
ls tests/*.db tests/*.db-* 2>/dev/null | wc -l
ls tests/test_*.py 2>/dev/null | wc -l

# 本地日志大小
du -sh app/logs/
```

## 文档状态

- **2026-07-12**：初版诊断报告生成。覆盖发现 1-8、量化诊断、附录。
- **2026-07-14**：扩展为整改追踪文档。新增发现 9（过度设计与不稳定因素）与 [整改计划追踪](#整改计划追踪) 章节；
  每个整改项的状态将持续更新到该章节。
- 本报告的"诊断数字"是**静态快照**，代码变化后需重新采集（采集命令见附录 B）。
- 本报告的"整改计划追踪"是**动态章节**，每个整改项启动/完成时同步更新表格中的"状态"列。
- 与 [agent-module-remediation spec](./2026-07-12-agent-module-remediation.md) 的关系：
  该 spec 专注 agent 模块；本报告覆盖 backend 全量（含 agent / data_flywheel / services / infra / 等）。
