## Why

Data Flywheel 现在可以把失败样本标注为 bad case，但这些标注仍停留在数据库记录层，vibecoding 或其他 coding agent 很难知道该读取哪些证据、该修哪个模块、该跑哪些验证。

本变更把失败样本导出为可消费的 repair pack，让标注数据从“问题索引”变成“可执行修复任务包”，支持按 `fix_target` 分批交给 vibecoding 逐步优化 Agent。

## What Changes

- 新增失败案例修复包导出能力，将 Data Flywheel 中已标注的失败样本导出为包含 manifest、cases、debug evidence、regression draft 和 README 的目录包。
- 新增 `bad label -> fix_target -> suggested_action -> verification` 的修复路由规则，让每个导出包明确指向 `router`、`pending_plan`、`tool_guardrail`、`domain_policy`、`tool_result_state`、`guardrail` 或 `prompt_or_sft`。
- 支持按标签、`fix_target`、优先级、样本数量和是否具备回归断言筛选导出，避免把所有 bad case 混在一个包里。
- 导出包包含给 vibecoding 使用的操作说明：先复现/补测试，再最小修改，最后运行 verification commands。
- 导出包保留来源引用和脱敏后的 debug evidence，不直接输出敏感信息。
- 修复完成后支持将关联 label 标记为 resolved，并保留修复包和回归用例来源。

## Capabilities

### New Capabilities

- `failure-repair-pack-export`: 定义从 Data Flywheel 失败样本生成可由 vibecoding 消费的修复包、修复路由、导出结构和 resolved 回写行为。

### Modified Capabilities

- `agent-evaluation-foundation`: 评测用例需要能保留 repair pack 来源，并支持从修复包中的 regression draft 进入评测/回放。
- `simulation-test-execution`: 仿真执行需要能运行从 repair pack 生成或接受的 regression cases，并将结果回流为修复包验证状态。

## Impact

- 后端：新增 Data Flywheel repair pack service、导出 API、修复路由规则、脱敏与归档逻辑；扩展 case draft 来源元数据。
- 前端：Data Flywheel 增加“生成修复包 / 导出修复包 / 标记 resolved”工作流，展示 `fix_target`、优先级、回归准备状态和 vibecoding 提示。
- 数据：可新增 repair pack 元数据表，或先以导出目录和现有 label/case draft 表建立关联；不改变在线聊天热路径。
- 测试：补充修复路由、导出结构、脱敏、case draft 来源和 resolved 回写的单元/接口测试。
- 运维：导出目录需要可配置，默认位于项目数据目录或管理员指定目录；不得写入 `.git/`、根目录临时脚本或敏感配置文件。
