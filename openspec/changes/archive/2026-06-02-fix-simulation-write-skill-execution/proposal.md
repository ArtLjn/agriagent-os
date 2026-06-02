## Why

Agent 仿真测试平台的 write skills 测试大面积失败（12/14 失败）。通过 `/spike` 快速验证排除了"session 生命周期"假设后，定位到四个真正根因：(1) **数据污染** — 多次测试运行后 crop_templates、cost_records 等表残留记录，导致后续"创建模板"类用例的 `before` 快照不纯净；(2) **match_fields 严格匹配** — 测试用例写 `category="番茄"` 但 Agent 返回 `category="番茄销售"`，严格相等导致匹配失败；(3) **Agent 行为与测试预期不匹配** — 模糊输入如"记一笔账"Agent 生成 pending action 而非直接失败，测试断言与实际行为错位；(4) **取消操作误判** — 取消 pending action 后 DB 无变化，但 consistency checker 仍报 hallucination。这些问题叠加导致仿真测试失去可信度，必须修复。

## What Changes

- **增加测试数据隔离**（核心修复）：实现 `precondition.clean_tables`，每个用例执行前清理涉及表中与当前 farm_id 相关的记录，消除历史数据污染
- **放宽 `match_fields` 匹配规则**：字符串字段支持子串匹配（`"番茄"` 匹配 `"番茄销售"`），数字支持 `int == float` 等值匹配
- **修复取消操作误判**：当 `expected_db_changes` 为空且用户取消 pending action 时，不再标记 hallucination 错误
- **增强一致性检查器**：新增 `execution_failure` 错误类型，通过 Agent trace 区分"skill 根本没被调用"（幻觉）和"skill 调用了但 DB 写入失败"
- **防御性改进**：`_execute_run` 后台任务使用独立的 DB session（虽然 spike 证明 session 生命周期不是当前根因，但作为防御性措施保留）

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
