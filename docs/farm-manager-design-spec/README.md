<p align="center">
  <img src="./banner.png" alt="AgriAgent OS Design Spec" width="100%">
</p>

<p align="center">
  简体中文 | <a href="./README_en.md">English</a>
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

# AgriAgent OS 设计规范（Design Spec）

> 版本：v1.2（草稿，全部 34 篇骨架已成 + Context/Memory 压缩机制修订 + Discovery Layer 设计补充 + 知识与记忆架构梳理 + 完整脱敏 + 作物地域化 delta 提案同步 + 数据库结构设计补全 + Agent 范式规范化设计）  
> 编写日期：2026-06-20  
> 维护人：BlockShip  
> 文档状态：草稿，持续对齐 `docs/architecture/` 与代码现状

---

## 这是什么

本目录是 **AgriAgent OS 项目的统一设计规范**，目标是把分散在 `docs/architecture/`、`docs/design/`、`.claude/rules/`、`backend/app/**` 的架构决策、模块边界、接口契约、编码规范**收敛成一份单一事实来源**，避免后续迭代中团队/Agent 走偏。

参考体例：主流 Agent 设计文档的预设计 / 正式设计 / 接口协议 / 相关规范 / 系统测试 / 项目管理六分法。

## 与既有文档的关系

| 现有文档 | 本 Spec 中的角色 |
| --- | --- |
| `docs/architecture/overview.md` | 被本章 [00_预设计/02_系统功能及技术架构总设计.md](./00_预设计/02_系统功能及技术架构总设计.md) 整合 |
| `docs/architecture/boundaries.md` | 边界矩阵下沉到 [01_正式设计/01_Agent平台架构.md](./01_正式设计/01_Agent平台架构.md) 各模块的「可依赖 / 禁止依赖」表 |
| `docs/architecture/agent-data-flywheel-industrial-roadmap.md` | 浓缩并指针到 [01_正式设计/06_数据飞轮与评测.md](./01_正式设计/06_数据飞轮与评测.md) |
| `docs/architecture/evolution-roadmap.md` | 演进路线归口到 [06_项目管理/01_里程碑与路线图.md](./06_项目管理/01_里程碑与路线图.md) |
| `.claude/rules/*.md` | 引用为权威，本 Spec 不复述条款，只索引位置 |
| `.claude/rules/skill-writing.md` | 与 [01_正式设计/02_Skill引擎与契约.md](./01_正式设计/02_Skill引擎与契约.md) 一致，冲突时以 `skill-writing.md` 为准 |

冲突原则：代码 > `docs/architecture/` > 本 Spec > 历史 commit。任何不一致**先改本 Spec 再改代码**。

## 目录速览

| 目录 | 内容 | 主要读者 |
| --- | --- | --- |
| [00_预设计](./00_预设计) | 系统愿景、技术架构总设计、技术选型 | 全员，特别是新人 |
| [01_正式设计](./01_正式设计) | Agent 平台、Skill、Context、Memory、Prompt、DataFlywheel、业务模块、前端契约 | 后端 + Agent 工程师 |
| [02_产品需求](./02_产品需求) | 核心能力清单、非功能需求 | 产品 + 工程 |
| [03_接口协议](./03_接口协议) | HTTP API、Agent 内部接口、外部服务、Skill 契约 | 工程师 + 联调方 |
| [04_相关规范](./04_相关规范) | Prompt/人设、安全、数据库、前后端编码、防污染 | 全员 |
| [05_系统测试](./05_系统测试) | 测试金字塔、回归集、Simulation、Evaluation | QA + 工程 |
| [06_项目管理](./06_项目管理) | 里程碑、工作拆解、Git 规范 | PM + 工程 |

### 完整目录索引

#### 00_预设计
- [01_系统愿景与目标.md](./00_预设计/01_系统愿景与目标.md)
- [02_系统功能及技术架构总设计.md](./00_预设计/02_系统功能及技术架构总设计.md)
- [03_技术选型与依赖.md](./00_预设计/03_技术选型与依赖.md)

#### 01_正式设计
- [01_Agent平台架构.md](./01_正式设计/01_Agent平台架构.md)
- [02_Skill引擎与契约.md](./01_正式设计/02_Skill引擎与契约.md)
- [03_Context工程.md](./01_正式设计/03_Context工程.md)
- [04_Memory工程.md](./01_正式设计/04_Memory工程.md)
- [05_Prompt工程.md](./01_正式设计/05_Prompt工程.md)
- [06_数据飞轮与评测.md](./01_正式设计/06_数据飞轮与评测.md)
- [07_可观测与运维.md](./01_正式设计/07_可观测与运维.md)
- [08_业务模块化.md](./01_正式设计/08_业务模块化.md)
- [09_前端与移动端契约.md](./01_正式设计/09_前端与移动端契约.md)
- [10_数据库结构设计.md](./01_正式设计/10_数据库结构设计.md)
- [11_Skill设计/天气Skill.md](./01_正式设计/11_Skill设计/天气Skill.md)
- [12_Skill路由选择架构.md](./01_正式设计/12_Skill路由选择架构.md)
- [13_Agent范式规范化设计.md](./01_正式设计/13_Agent范式规范化设计.md)

#### 02_产品需求
- [01_核心能力清单.md](./02_产品需求/01_核心能力清单.md)
- [02_非功能性需求.md](./02_产品需求/02_非功能性需求.md)

#### 03_接口协议
- [01_HTTP_API协议.md](./03_接口协议/01_HTTP_API协议.md)
- [02_Agent内部接口.md](./03_接口协议/02_Agent内部接口.md)
- [03_外部服务接口.md](./03_接口协议/03_外部服务接口.md)
- [04_Skill接口契约.md](./03_接口协议/04_Skill接口契约.md)

#### 04_相关规范
- [01_Prompt与人设规范.md](./04_相关规范/01_Prompt与人设规范.md)
- [02_安全与权限规范.md](./04_相关规范/02_安全与权限规范.md)
- [03_数据库与迁移规范.md](./04_相关规范/03_数据库与迁移规范.md)
- [04_前端编码规范.md](./04_相关规范/04_前端编码规范.md)
- [05_Python编码规范.md](./04_相关规范/05_Python编码规范.md)
- [06_防污染与文档同步规范.md](./04_相关规范/06_防污染与文档同步规范.md)

#### 05_系统测试
- [01_测试金字塔与策略.md](./05_系统测试/01_测试金字塔与策略.md)
- [02_回归测试集.md](./05_系统测试/02_回归测试集.md)
- [03_Simulation仿真测试.md](./05_系统测试/03_Simulation仿真测试.md)
- [04_Evaluation评测.md](./05_系统测试/04_Evaluation评测.md)

#### 06_项目管理
- [01_里程碑与路线图.md](./06_项目管理/01_里程碑与路线图.md)
- [02_工作拆解.md](./06_项目管理/02_工作拆解.md)
- [03_Git与协作规范.md](./06_项目管理/03_Git与协作规范.md)

## 阅读路径

| 你是谁 | 推荐顺序 |
| --- | --- |
| 新人 onboarding | 00 → 02 → 03 → 01 |
| 后端工程师 | 01.01 → 01.02 → 01.03 → 03.02 → 04 |
| Agent/Prompt 工程师 | 01.01 → 01.02 → 01.12 → 01.13 → 01.05 → 04.01 → 06 |
| 移动端工程师 | 02 → 03.01 → 01.09 → 04.04 |
| Admin Web 工程师 | 02 → 03.01 → 01.09 → 04.04 |
| 产品/PM | 02 → 00.01 → 06 |
| QA | 05 → 03 → 01 |

## 硬约束（违反即 PR 不通过）

1. **依赖方向**：`schemas/ → agent/application → agent/runtime → modules → services → core/infra → models`；前端 `api/ → components → layouts → pages`。详见 [01.01 Agent平台架构](./01_正式设计/01_Agent平台架构.md)。
2. **横切关注点**：auth / log / telemetry / trace 只通过依赖注入，禁止业务层直接 import。
3. **文件与方法限制**：生产 Python 文件 ≤ 1000 行，500-1000 行按职责观察评审；方法建议 ≤ 50 行，超过 80 行需说明或拆分；类 ≤ 200 行；方法参数 ≤ 5 个。
4. **新代码必有测试**：覆盖率 ≥ 80% 为目标，关键路径必须覆盖。
5. **Skill 契约**：每个 Skill 必须有 `skill.md` + `scripts/main.py`，且符合 [01.02 Skill引擎与契约](./01_正式设计/02_Skill引擎与契约.md)。
6. **结构化日志**：禁止 `print` / `console.log` 调试；日志带 `trace_id`。
7. **数据库变更**：只用 Alembic；禁止手动 SQL 改表；统一 MySQL 8.x，charset `utf8mb4`。
8. **写操作 Skill 不允许缓存**，不允许缺参猜测业务关键字段。

## 维护节奏

- **本 Spec 改动触发条件**：①新增/修改 API 端点；②新增/修改数据模型；③新增/修改 Skill；④修改配置或部署；⑤修改安全策略；⑥新增功能模块。
- **每次正式 PR**：如涉及以上触发条件，必须同步更新对应章节并链接到 PR。
- **季度回顾**：核对目录与 `backend/app/`、`admin-web/src/`、`mobile-app/lib/` 真实结构，不一致处由原作者修复。

## 术语速查

| 术语 | 解释 |
| --- | --- |
| Agent | 农场助手智能体，由 Application + Runtime + Planner + Executor + Reflector 组成 |
| Advisor | Agent 兼容入口，处理 Guardrails、问候、Pending Action、流式编排 |
| Skill | 单一能力模块，按 `.claude/rules/skill-writing.md` 契约实现，分只读 / 写操作 |
| ContextBundle | Runtime 消费的动态上下文包，由 Selector + Budget + Compressor 构造 |
| MemoryService | 短时记忆 + 长时记忆 + Retrieval + Observation 的统一接口端口 |
| PromptComposer | 把 Snippet 组合成最终 system prompt 的渲染器，受 `prompt/` 治理 |
| DataFlywheel | 样本加工台：从会话/trace/仿真失败中提取 → 规则候选 → LLM 预标注 → 人工确认 → 回归/评测/训练数据 |
| Simulation | 回归执行台：跑 DB-backed regression cases |
| Evaluation | 趋势评分台：版本对比通过率、工具选择准确率、pending 漏拦截率 |
| Pending Action | 写操作需用户确认的暂存动作，支持确认/取消/过期 |
| Smart Fill | 移动端智能填写统一入口：`/api/v1/scenarios` 列场景 + `/parse` 解析 |
| Farm Cockpit | 移动端首页驾驶舱，承载每日建议、关键指标、快捷入口 |
| Yaya | 移动端 AI 助理对话页（芽芽 IP） |

## 变更记录

| 版本 | 日期 | 变更 | 作者 |
| --- | --- | --- | --- |
| v0.1 | 2026-06-19 | 创建目录骨架与核心章节初稿（00-04 共 25 篇） | BlockShip |
| v0.2 | 2026-06-19 | 补齐 05_系统测试（4 篇）+ 06_项目管理（3 篇），共 32 篇骨架完成 | BlockShip |
| v0.3 | 2026-06-19 | [03_Context工程] § 6 压缩策略改为贴合实际代码（5 道关卡 + 多轮失忆根因 + 主流方案对比 + 推荐方案）；[04_Memory工程] § 6 短期记忆补"当前实现 / 已识别问题 / 修复方向"，新增 § 12 多轮失忆治理路线、§ 13 存储演进路线（Redis 决策：当前不上） | BlockShip |
| v0.4 | 2026-06-19 | [01_正式设计/06_数据飞轮与评测] 新增 § 9 Discovery Layer 与风险发现（2 级过滤 + 取 max 评分 + 规则引擎 + LLM Judge + 工作台 3 处改动 + MVP 4.5 人日），原 § 9-§ 12 顺延为 § 10-§ 13；[00_预设计/02_系统功能及技术架构总设计] 架构图 + 五大子系统表 + § 5.7 决策 + § 7 落地状态补 Discovery Layer | BlockShip |
| v0.5 | 2026-06-19 | 知识与记忆架构梳理（brainstorming 产出）：[04_Memory工程] § 7 长时记忆补 § 7.2 落地实施（candidate→confirmed 流转 + memory_records 新建表 + 与 summary 共触发）；§ 8 检索补 § 8.2 引入 Qdrant 触发条件（4 条同时满足）+ § 8.3 实施边界；§ 14 当前状态 / § 16 相关文档同步；[02_Skill引擎与契约] create_crop_template 加 region 注释。详见 [docs/superpowers/specs/2026-06-19-knowledge-and-memory-architecture-design.md](../superpowers/specs/2026-06-19-knowledge-and-memory-architecture-design.md) | BlockShip |
| v0.6 | 2026-06-19 | 脱敏：删除对比章节中的具体外部项目名与路径（[Readme]、[01_Agent平台架构] § 9、[02_系统功能及技术架构总设计] § 6、[04_Memory工程] § 15），改写为"典型多 Agent 系统 / 典型 Agent 架构"；删除生产服务器 IP（[07_可观测与运维] § 11、[03_技术选型与依赖] § 5.1） | BlockShip |
| v0.7 | 2026-06-19 | 深度脱敏补漏：[07_可观测与运维] § 5 删除"对齐智能家居 LOGBUS 风格"，§ 11 部署路径 / 服务名 / 运维脚本全部改为占位（`<repo_dir>` / `<service_name>`）；[03_技术选型与依赖] § 5 同步；[03_接口协议/03_外部服务接口] § 5/§ 6 日志路径 + systemd unit 中所有 `/root/workspace/...` 改占位、User 字段改 `<deploy_user>` | BlockShip |
| v0.8 | 2026-06-19 | 作物地域化同步：新建 [openspec/changes/extend-crop-template-with-region-tag](../../openspec/changes/extend-crop-template-with-region-tag/proposal.md) delta 提案（proposal/design/specs/tasks 完整）；同步 [04_相关规范/03_数据库与迁移规范] 表清单 `crops → crop_templates` + region_tag 说明；[01_正式设计/08_业务模块化] CropPort 签名加 region + 新增 list_system_templates / import_system_template；[02_产品需求/01_核心能力清单] 作物管理补地域化变体；[03_接口协议/01_HTTP_API协议] 补 `GET /crops/templates/system?region=` 与 `POST /import` 端点 | BlockShip |
| v0.9 | 2026-06-20 | 新增 [01_正式设计/10_数据库结构设计]：以 `backend/sql/farm_manager.sql` 生产 dump 为基准，反推 33 张表（含 `alembic_version`）的字段、约束、索引、外键；附接口→表映射矩阵、生产 vs 代码层差异对账、预留待建表（`memory_records`/`audit_logs`/`evaluation_reports` 等） | BlockShip |
| v1.0 | 2026-06-22 | Running summary Phase A 落地：`conversations.summary` 自动生成与持久化、`set_session_summary()` 同步缓存、ConversationSelector 注入 `conversation_summary` block；长期记忆提取仍保持拆分提案单独推进 | BlockShip |
| v1.1 | 2026-06-22 | 新增 [01_正式设计/12_Skill路由选择架构]：定义 Skill Catalog、Rule Classifier、Router Policy、Direct Routing、Tool Chain、Trace 与批量回归门禁；明确 `get_farm_status` 只用于泛化农场状态，禁止所有读 Skill 隐式扩展到农场状态 | BlockShip |
| v1.2 | 2026-06-23 | 新增 [01_正式设计/13_Agent范式规范化设计]：定性当前单主 Agent + Skill + 触发式反思范式，补当前/目标架构图、Reflection 触发规范、Skill 触发树、农事用工子树、不过度设计的三阶段落地与回归种子 | BlockShip |
| v1.3 | 2026-07-06 | [01_正式设计/06_数据飞轮与评测] 补充问题仓与规则候选治理：明确人工坏会话入仓、IssueRepositoryEntry、RuleCandidatePackage、正例/反例验证、晋级门禁，以及“作物/茬口/农场状态”Skill 选错专项样板 | BlockShip |

## 协议

[CC BY-NC 4.0](./LICENSE) © BlockShip — 允许分享与改编，必须署名，不得用于商业目的。
