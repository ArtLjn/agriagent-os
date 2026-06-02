## Why

Agent 仿真测试平台的 write skills 测试（记账、创建模板、创建茬口等）大面积失败（12/14 失败）。根因分析发现三个问题叠加：(1) 后台任务 `_execute_run` 复用 FastAPI 请求上下文中的 DB session，该 session 在请求返回后被 `get_db` 的 finally 块关闭，导致 `before`/`after` 数据库快照查询不可靠；(2) 多次测试运行残留的数据污染了后续测试的 `before` 快照；(3) 一致性检查器无法区分"LLM 根本没调用 skill"（幻觉）和"skill 调用了但 DB 写入失败"（执行失败）。这些问题使仿真测试失去可信度，必须修复。

## What Changes

- 修复 `_execute_run` 后台任务：创建独立的 DB session 和 `SimulationRunner`，不再依赖已关闭的请求级 session
- 增加测试数据隔离：每个用例执行前清理 `verify_tables` 中涉及的表，确保 `before` 快照不受历史数据污染
- 增强一致性检查器：新增 `execution_failure` 错误类型，区分"skill 被调用但 DB 写入失败"和"LLM 幻觉"
- 放宽 `match_fields` 匹配规则：支持子串匹配（如"番茄"匹配"番茄销售"）
- 优化取消操作检测：取消用例不应被误判为 hallucination

## Capabilities

### New Capabilities
- `simulation-test-execution`: 测试执行引擎的 session 生命周期管理和数据隔离机制
- `simulation-consistency-checking`: 一致性检查器的错误分类和匹配规则

### Modified Capabilities
- （无 spec-level 需求变更，纯实现层修复）

## Impact

- **后端**: `backend/app/simulation/routes.py`、`test_runner.py`、`consistency_checker.py`、`state_snapshot.py`
- **测试用例**: `backend/data/simulation_cases/*.json` 可能需要调整预期
- **前端**: `admin-web/src/pages/Simulation/index.tsx` 需要新增 `execution_failure` 的错误展示
- **数据库**: 不影响现有业务表，仅影响仿真测试的 snapshot 查询
