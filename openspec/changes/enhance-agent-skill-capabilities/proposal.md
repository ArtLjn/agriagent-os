## Why

当前 Agent 已经接入了记账、茬口、作业单、用工、天气、上下文、trace 和评测等多类能力，但 Skill 层仍偏零散，遇到“修改玉米茬口 9 月 1 开始”这类真实表达时容易追问过多、选错意图或无法完成更新。现在需要把 Skill 从“能调用”升级为“能稳定理解、确认、修改、诊断和回归验证”。

## What Changes

- 强化写操作 Skill 的意图识别：区分创建、修改、补记、查询、结算和取消，减少对明确用户指令的无效二选一追问。
- 扩展茬口和农事作业 Skill：支持修改已有茬口开始日期/季节/阶段、查询和更新作业单、查询/结算未付人工。
- 统一 Skill 文档与运行时元数据：每个 Skill 声明权限等级、风险等级、缓存失效、上下文依赖、缺参策略和示例。
- 完善复杂写操作确认信息：确认卡片必须展示影响范围、关键参数、自动推断值、待确认原因和可修改字段。
- 建立 Skill 能力评测回归集：覆盖记账、茬口、作业单、用工、天气、上下文依赖、确认/修改/取消流程。
- 增加开发诊断能力：可从 trace 判断工具未调用、参数错误、pending action 丢失、上下文缺失或执行失败的原因。

## Capabilities

### New Capabilities

- `skill-capability-governance`: 定义 Skill 文档、元数据、权限、上下文依赖、确认展示和缓存失效的统一治理规则。
- `planting-skill-operations`: 覆盖茬口修改、作业单查询/更新、用工查询和工资结算等种植运营类自然语言能力。
- `skill-regression-evaluation`: 定义 Skill 调用质量、参数质量、确认流程和业务写入结果的回归评测能力。
- `agent-skill-diagnostics`: 定义基于 trace、pending action、上下文和评测结果的 Skill 问题诊断能力。

### Modified Capabilities

- `action-skills`: 写操作 Skill 从“创建类能力为主”扩展为创建、修改、补记、结算和复杂确认的完整动作体系。
- `llm-tool-calling`: Tool Executor 从硬编码写操作列表升级为基于 Skill 元数据执行权限、校验、确认和 trace。
- `agent-evaluation-foundation`: 评测指标扩展到真实 Skill 能力回归，包括漏调、误调、参数错误、确认流程和执行一致性。
- `context-engineering`: Skill 上下文依赖需要纳入 ContextPolicy，使写操作能获取活跃茬口、种植单元、工人、成本分类和天气等必要上下文。

## Impact

- 后端 Agent/Skill：`backend/app/agent/skills/**`、Skill 注册、Tool Executor、pending action、tool selector、ContextPolicy。
- 后端业务服务：茬口、作业单、用工、成本、天气、上下文和 trace 相关服务。
- 评测与模拟：`backend/app/evaluation/**`、`backend/app/simulation/**`、评测用例和报告。
- 管理端与调试页：Skill Registry、Playground、Trace Monitor 需要展示 Skill 元数据、确认上下文和诊断结果。
- 测试：新增单元测试、集成测试和场景回归测试，覆盖典型自然语言表达和多轮确认流程。
