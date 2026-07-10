## Context

farm-manager 的 Agent Skill 体系已经完成基础 metadata、文档规范、写操作确认、缓存失效和 Router stop-loss 建设，但当前能力边界仍以旧 tool name 和部分 CRUD/API 粒度 Skill 为主。`backend/app/agent/router/registry.py`、`backend/app/agent/router/catalog.py`、`backend/app/agent/skills/metadata.py` 和 `backend/app/agent/skills/__init__.py` 分别维护路由、候选、metadata 和 LangChain Tool 转换逻辑，事实源分散。

现有问题不是单点 bug，而是架构演进问题：Skill 数量继续增长时，继续靠目录、静态 dict 和业务关键词规则会让 Tool Selection 越来越难评估，也会让读写隔离、高风险确认和历史兼容变得脆弱。

本设计采用 Registry-first 方案，把“Skill 是什么、属于哪个业务能力、有哪些 operation、旧 tool name 如何兼容、Router 为什么选择它”沉淀到可校验 Registry 中。第一阶段目标是治理和路由收敛，不重写业务 service，也不一次性搬迁所有 Skill 目录。

## Goals / Non-Goals

**Goals:**

- 建立 `skills.yaml`、`aliases.yaml`、`domains.yaml` 作为 Skill capability registry。
- 让 Router 从 Registry 生成 domain、capability、operation 的可解释选择结果。
- 保留旧 tool name alias，兼容 pending action、trace replay 和历史测试。
- 禁止 fallback all，降低读意图暴露写 operation 的概率。
- 为后续按业务能力合并 Skill 目录提供明确迁移边界。
- 增加 Registry 校验、Router trace 和回归评测，让误选可观测、可测试。

**Non-Goals:**

- 第一阶段不重写 `backend/app/services/**`。
- 第一阶段不改变 API、数据库模型或前端交互。
- 第一阶段不删除旧 Skill 目录，不移动所有 `scripts/main.py`。
- 第一阶段不强制接入 embedding retrieval。
- 本变更不取消写操作确认，不绕过 pending action 或 pending plan。

## Decisions

### Decision 1: Registry-first instead of directory-first

采用 `backend/app/agent/skills/registry/` 作为事实源，目录只承载实现。

替代方案是先把现有目录重排成 `capabilities/<domain>/<skill>`。该方案视觉上清晰，但会同时影响 skillify 加载、旧工具名、测试路径和 pending action，风险高且无法立刻改善路由选择。Registry-first 可以先让 Router 和治理收益落地，再渐进移动目录。

### Decision 2: Capability + operation replaces CRUD tool governance

对外治理粒度改为 capability，例如 `manage_cost`、`manage_crop_cycle`、`manage_workers`；具体动作用 operation 表示，例如 `create_record`、`query_summary`、`delete_record`。

这样可以减少 LLM 看到的相似工具数量，同时把读、写、删除、结算等风险声明下沉到 operation。旧 tool name 通过 alias 映射，不作为长期能力边界。

### Decision 3: Router remains protective, not a business keyword engine

Router 使用 Registry examples、anti_examples、tags、entities 和 operation metadata 生成 Top-K，并记录 score 和 evidence。Python classifier 只保留轻量 frame 抽取、明显无工具保护、写入风险保护和兼容规则。

不再通过不断给 `classifier.py` 增加业务关键词来修单个 case。表达差异优先进入 Registry examples、anti_examples 和 Router eval。

### Decision 4: Legacy alias is a compatibility layer

`aliases.yaml` 映射旧 tool name 到 capability/operation，例如 `create_cost_record -> manage_cost.create_record`。Runtime 和 pending action 必须能解析 alias，并在 trace 中同时记录 legacy name 与 capability name。

这样可以保护历史 pending action、trace replay、测试和外部排查资料，不需要一次性打断生产链路。

### Decision 5: Split implementation into four increments

实施拆成四个可独立评估的小变更：

1. Registry Skeleton：新增 YAML 和校验，不接入 runtime。
2. Catalog Loader：`SkillCatalog` 从 Registry 读取，旧 Router 输出保持兼容。
3. Router Decision：加入 domain/capability/operation score 和 evidence。
4. Runtime Binding：runtime 消费 capability/operation/alias，pending action 保持兼容。

如果只做前两步，工作量中等偏小；做到第三步开始影响主对话链路；做到第四步才触及工具执行和 pending 确认链路。

## Risks / Trade-offs

- [Risk] Registry 与现有 `skill.md`、metadata dict 漂移。→ 增加 `check-skill-registry.sh` 和测试，要求 alias、capability、operation、metadata 可解析。
- [Risk] Router score 初期不稳定。→ 第一阶段保留旧规则 fallback，但禁止 fallback all；用 trace 和 eval 调参。
- [Risk] Capability tool schema 过大。→ operation hint 缩小 schema，复杂 capability 分阶段合并，必要时先只做 alias metadata。
- [Risk] 写 operation 被误暴露。→ Policy Guard 对读写隔离、高风险、缺参和 domain 不确定做 fail-closed。
- [Risk] 历史 pending action 无法执行。→ `aliases.yaml` 必须覆盖所有旧写 Skill，pending executor 先解析 alias 再执行。
- [Risk] 一次性合并所有 Skill 工作量过大。→ 第一阶段只做治理与路由，旧 Skill handler 继续作为 adapter。

## Migration Plan

1. 新增 Registry skeleton 和校验测试，不接入 runtime。
2. 从现有 `router/registry.py`、`skills/metadata.py`、`skill.md` 迁移第一版 capability metadata。
3. 让 `SkillCatalog` 支持从 YAML Registry 构建候选，并保留当前 Python registry fallback。
4. 扩展 Router model 和 trace payload，记录 capability、operation、score、evidence、legacy_alias。
5. 调整 Policy Guard，强制读写隔离、schema 预算、fallback all 禁止和高风险澄清。
6. 调整 runtime binding，让主对话链路消费新的 `RouterDecision`，但仍可执行旧 tool name。
7. 调整 pending action executor，通过 alias 解析旧写 Skill。
8. 跑 Router、runtime binding、tool executor metadata、pending action、Skill docs 和 coverage matrix 测试。
9. 低风险 capability 先合并：settings、workers、planting units、cost categories。
10. 高风险 capability 后合并：cost、crop cycle、work orders、labor payment。

Rollback 策略：保留旧 `router/registry.py` 和旧 tool name 执行路径作为兼容 fallback。若 Registry 路由异常，可通过配置切回旧 Router 选择逻辑，同时保留 Registry 校验和 trace 不影响执行。

## Open Questions

- Capability tool 是否第一阶段真实暴露给 LLM，还是先只作为 Router metadata 输出，仍绑定旧 tool name。
- Registry YAML 是否允许内联 JSON Schema，还是只引用现有 skillify 参数 schema。
- Router score 初始阈值是否采用文档建议值，还是先用评测集离线标定。
- 是否需要在第一阶段新增 admin debug 页面展示 Router evidence，还是只写 trace。
