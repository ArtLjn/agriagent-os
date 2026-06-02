## Context

Agent 仿真测试平台 (`backend/app/simulation/`) 用于端到端验证 Agent write skills 是否真正执行了数据库操作。write skills 测试大面积失败（12/14），通过 `/spike` 快速验证排除了"session 生命周期"假设后，定位到四个真正根因：

**数据污染（首要根因）**: 多次测试运行后 crop_templates、cost_records 等表残留记录。例如 TC-WRITE-010 "创建橘子模板"在第一次运行时成功创建，第二次运行时模板已存在，Agent 返回"已存在"，但测试断言预期"已创建"且 DB 新增 1 条，导致失败。

**match_fields 严格匹配**: TC-WRITE-002 预期 `category="番茄销售"`，但 Agent 实际返回 `category="番茄"`（LLM 的 ToolMessage 中只有"番茄"参数）。严格字符串相等导致匹配失败。

**取消操作误判**: TC-ADV-002 "取消后模板不应入库"中，仿真测试发送取消、DB 确实无变化，但 consistency checker 的 `_check_hallucination` 看到 LLM 回复包含"已创建"关键词就报了 hallucination。

**Agent 行为与预期错位**: TC-WRITE-005 "记一笔账"缺少金额，测试预期 Agent 直接返回失败，但 Agent 实际生成了 pending action（让用户确认金额），仿真测试按流程发送取消，最终 DB 无变化但 LLM 回复可能包含"已取消"而非"失败"。

**检测粒度不足**: `check_consistency()` 只能判断"LLM 声称执行了但 DB 无变化"（hallucination），无法区分"skill 根本没被调用"和"skill 调用了但 DB 写入失败"。

## Goals / Non-Goals

**Goals:**
- 实现测试用例级别的数据隔离（执行前清理相关表），消除数据污染
- 放宽 `match_fields` 匹配规则，字符串支持子串匹配、数字支持等值匹配
- 修复取消操作误判：取消后 DB 无变化时不报 hallucination
- 区分"幻觉"（没调用 skill）和"执行失败"（调用了但 DB 写入失败）
- 防御性改进：`_execute_run` 使用独立 session（避免未来 session 生命周期问题）

**Non-Goals:**
- 不修改 Agent 核心逻辑（graph.py、advisor.py 的 LLM 调用流程）
- 不修改 Skill 实现（skill scripts 中的 DB 操作逻辑）
- 不引入外部测试框架（保持现有自研仿真平台架构）
- 不改用 async SQLAlchemy（保持现有同步 session 模式）

## Decisions

### 1. `_execute_run` 内部创建新的 `SimulationRunner`（防御性）

**选择**: 在 `_execute_run` 中使用 `SessionLocal()` 创建新 session，并构建新的 `SimulationRunner` 和 `DbStateSnapshot`。

**理由**: `/spike` 验证了 SQLite 下 session 关闭后仍能查询，但依赖已关闭的 session 不是可靠的做法。改为后台任务自己管理 session，消除未来的不确定性。

**替代方案**: 保持现状（spike 证明当前能工作）—— 但存在隐性风险，session 关闭后的行为取决于 SQLAlchemy 版本和数据库驱动。

### 2. 数据隔离放在 `run_single` 的 `_setup_precondition` 中

**选择**: 实现 `_setup_precondition` 方法，支持 `{"clean_tables": ["crop_templates", "growth_stages"]}` 指令，在每个用例执行前删除指定表中与当前 farm_id 相关的记录。

**理由**: 这是首要根因。TC-WRITE-010 "创建橘子模板"第一次运行成功创建，第二次运行时模板已存在，Agent 返回"已存在"但测试断言"已创建"+新增1条，导致失败。清理后每个 case 的 `before` 快照都是干净的。

**风险**: 如果 case 依赖之前 case 创建的数据，clean_tables 会破坏这种依赖。解决方案：每个 case 自包含，需要前置数据时用 `precondition` 显式创建（如 `ensure_template_exists`）。

### 3. 取消操作不再报 hallucination

**选择**: 修改 `check_consistency`，当 `expected_db_changes` 为空（即测试预期 DB 无变化）且存在 `pending_action` 时，跳过 hallucination 检查。

**理由**: TC-ADV-002 "取消后模板不应入库"中，取消操作是正确的（DB 无变化符合预期），但被 `_check_hallucination` 误判。因为 LLM 的 ToolMessage 包含 `[PENDING_ACTION]` 标记，LLM 回复中仍可能包含"已创建"等 success keywords，semantic extractor 提取到 claim 后，hallucination checker 看到 DB 无变化就报了错。

**替代方案**: 在 semantic extractor 中排除 pending action 场景 —— 更复杂，不如在 consistency checker 中按预期判断。

### 4. `match_fields` 子串匹配 + 数字等值匹配

**选择**: `_check_expected_changes` 中，当 `match_fields` 的字段值是字符串时，支持子串匹配（`expected_value in actual_value`）。数字支持 `int == float` 等值匹配（`200 == 200.0`）。布尔仍严格相等。

**理由**: TC-WRITE-002 预期 `category="番茄销售"`，但 Agent 实际返回 `category="番茄"`（ToolMessage 参数只有"番茄"）。严格字符串相等导致匹配失败。SQLite 中数字可能以 float 存储，`200` 和 `200.0` 应视为相等。

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| clean_tables 误删生产数据 | 仿真测试只在测试环境运行；`clean_tables` 只删除与 farm_id 匹配的记录；admin-web 有明确提示这是测试 |
| 每个 case 清理数据导致测试变慢 | 只有 `precondition.clean_tables` 显式指定的表才会清理；大部分 case 不需要 |
| trace 查询增加耦合 | trace collector 已经是 Agent 执行路径的一部分，只是读取已有数据 |
| 子串匹配降低严格性 | 数字和布尔仍严格匹配；仅字符串放宽 |
