## Context

当前系统已经有 `backend/app/agent/skills/**`、Tool Executor、pending action、ContextPolicy、Trace、Evaluation 和 Simulation 模块。问题不在于没有工具调用链路，而在于 Skill 的业务表达、元数据、确认展示和回归验证没有随新增功能同步升级。

典型失败形态是用户说“修改玉米茬口 9 月 1 开始”，系统识别到当前夏季玉米茬口播种期是 6 月 5 日，但没有直接进入“修改已有茬口开始日期”的待确认动作，而是追问“修改现有还是创建新茬口”。这说明 Agent 缺少明确的更新类 Skill、上下文决策规则和评测用例。

## Goals / Non-Goals

**Goals:**

- 为所有 Skill 建立统一元数据契约，使运行时不再依赖分散硬编码判断权限、缓存、上下文和确认方式。
- 补齐种植运营类 Skill，优先覆盖茬口修改、作业单查询/更新、未付人工查询和工资结算。
- 优化复杂写操作 pending action，让用户看到关键参数、系统推断依据和可修改字段。
- 建立 Skill 回归评测集，把“该调哪个 Skill、参数是否正确、确认流程是否正确、数据库是否实际变化”纳入持续验证。
- 增加 trace 诊断入口，支持开发者快速定位 Skill 未调用、误调用、参数错误或上下文缺失。

**Non-Goals:**

- 不重写 Agent Runtime、LLM Provider 或全部 Prompt 系统。
- 不引入新的外部 LLM、向量库或工作流引擎。
- 不在本阶段实现完整 HR、考勤排班、工资条或复杂财务凭证。
- 不改变现有移动端和管理端 API 的对外兼容行为，必要时只新增接口或兼容字段。

## Decisions

### Decision 1: 用 Skill metadata 驱动执行策略

每个 Skill 在注册时暴露 metadata，至少包含：

- `permission_level`: `read`、`write_confirm`、`admin`、`external_network`
- `risk_level`: `low`、`medium`、`high`
- `context_dependencies`: 需要的上下文 block，如 active_cycle、planting_units、workers、cost_categories、weather
- `cache_invalidation`: 写成功后需要失效的缓存组
- `confirmation_schema`: pending action 展示字段、推断字段和可修改字段
- `evaluation_tags`: 回归用例分类

替代方案是继续维护 `WRITE_SKILLS`、缓存映射和确认字段映射等硬编码表。该方案短期简单，但每增加一个 Skill 都要改多个位置，已经在 `create_operation_work_order` 上暴露维护成本。

### Decision 2: 先扩展种植运营 Skill，而不是把所有更新塞进旧 Skill

新增或扩展以下 Skill：

- `update_crop_cycle`: 修改已有茬口的开始日期、季节、名称、面积、状态或备注。
- `get_operation_work_orders`: 查询作业单、近期作业和指定批次/地块作业。
- `update_operation_work_order`: 更新作业单范围、日期、备注、作业类型和用工明细。
- `get_labor_payables`: 查询未付人工、按工人汇总、按作业单汇总。
- `settle_labor_payment`: 结算或补付工人工资，并关联人工成本。

替代方案是复用 `create_crop_cycle`、`create_operation_work_order` 做“创建或修改”。该方案容易让 LLM 混淆创建与更新，也会让参数 schema 变得过大。

### Decision 3: pending action 使用结构化确认模型

确认信息由 `confirmation_schema` 生成，不再只拼接少数参数。确认模型包含：

- 原始输入
- 意图和目标对象
- 将被修改或创建的字段
- 系统自动推断值和依据
- 风险提示或缺失信息
- 用户可回复的确认、取消、修正方式

这能覆盖“修改玉米茬口 9 月 1 开始”这类场景：系统应展示“将夏季玉米开始日期从 2026-06-05 改为 2026-09-01”，而不是询问是否新建。

### Decision 4: 回归评测从 trace 和数据库结果双证据判断

Skill 回归用例不仅断言 LLM 是否调用某个 Skill，还要断言：

- 参数是否匹配业务预期
- pending action 是否生成或跳过
- 用户确认/修正/取消后的结果是否正确
- trace 是否记录了 context_build、tool_call、pending_action、memory_observe
- 数据库快照是否发生预期变化

单看回复文本容易遗漏“说已完成但数据库没变”的问题；单看数据库又无法解释为什么没调用 Skill。

## Risks / Trade-offs

- [Risk] Skill metadata 初期需要改动多个 Skill 文件，容易漏字段。→ 先提供默认 metadata 适配旧 Skill，并用测试强制新 Skill 完整声明。
- [Risk] 更新类 Skill 可能误修改用户不想改的茬口。→ 对有多个候选对象的场景必须生成待确认动作，并展示匹配依据。
- [Risk] 评测用例过多导致 CI 变慢。→ 区分快速回归集和完整模拟集，提交前运行快速集，夜间或手动运行完整集。
- [Risk] Tool Executor 改造影响现有写操作确认。→ 保留旧 `WRITE_SKILLS` 作为迁移 fallback，逐步迁移到 metadata。
- [Risk] 复杂确认文案影响移动端展示。→ 后端返回结构化 `pending_action.context`，前端可按字段展示，纯文本作为兼容 fallback。

## Migration Plan

1. 为 Skill 注册增加 metadata 读取能力，旧 Skill 缺失字段时使用兼容默认值。
2. 迁移现有 Skill 文档格式，优先处理 `create_operation_work_order` 和所有写操作 Skill。
3. 新增种植运营 Skill，并接入 Tool Executor、pending action 和缓存失效。
4. 将 pending action 确认消息升级为结构化模型，同时保留现有文本回复。
5. 新增 Skill 回归评测用例和诊断报告。
6. 管理端 Skill Registry、Playground、Trace Monitor 展示 metadata、确认上下文和诊断结果。

Rollback 策略：保留旧硬编码表和旧确认文本生成路径作为 fallback；若 metadata 驱动路径异常，可通过配置回退到旧执行策略。

## Open Questions

- `update_crop_cycle` 是否允许修改已经产生作业单或成本记录的茬口开始日期，还是只允许补充备注并提示影响范围？
- 工资结算是否直接复用成本记录，还是单独保留 labor payment 记录再同步成本？
- Skill 回归评测是否纳入默认 `harness-check.sh`，还是先作为单独命令运行？
