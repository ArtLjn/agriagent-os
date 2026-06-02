## Context

当前 farm-manager Agent 使用 LangGraph + LangChain StructuredTool 架构执行 write skills（记账、创建模板等）。执行流程为：

```
用户输入 → LLM 推理 → tool_calls → _parallel_tool_node → 
写操作拦截为 pending action → 用户确认 → _execute_pending_action → DB 写入
```

当前实现的问题：
1. **Schema 无约束**: `create_cost_record` 的 `category` 是开放字符串，LLM 自由填写导致"化肥"/"肥料"/"复合肥"等重复变体
2. **参数错误无反馈**: 缺少金额时 LLM 仍尝试调用 tool，pending action 中包含无效参数，用户确认后才暴露问题
3. **确认信息不透明**: `build_confirm_message` 只展示参数值，不展示 LLM 如何理解原话
4. **无路由区分**: 闲聊和查询都走完整 tool calling 流程

## Goals / Non-Goals

**Goals:**
- `category` 参数强制从用户现有标签中选择，消除分类不一致
- 参数校验失败时 LLM 自动修正，不生成无效 pending action
- 确认消息展示"原话理解 + 提取参数 + 执行操作"三层信息
- 闲聊/问候类输入直接回复，不走 tool calling
- LLM 不自动创建新分类，新类型在 pending action 中提示用户手动添加

**Non-Goals:**
- 不修改 cost_records / crop_templates 等数据表结构
- 不引入新的 LLM 提供商或模型
- 不改写 Agent 的核心 graph 架构（仍使用 LangGraph）
- 不实现自动分类合并/去重功能

## Decisions

### 1. 动态 enum 从 cost_categories 表加载

**选择**: `skills_to_langchain_tools` 生成 StructuredTool 时，从 `cost_categories` 表查询当前 farm 的标签列表，填入 JSON Schema 的 `enum` 字段。

**理由**: enum 约束能让 LLM 在生成 tool_call 时就从有限选项中选择，而不是自由填写后在校验阶段才发现问题。

**实现方式**: `_schema_to_pydantic` 函数中，检测到字段名是 `category` 时，从数据库加载 enum 值替换 schema 中的定义。

**风险**: 每次加载 skill 都要查一次数据库。缓解：缓存标签列表，用户修改标签时清除缓存。

### 2. Pydantic 校验放在 tool node 中，错误反馈给 LLM

**选择**: 在 `_parallel_tool_node` 的 tool 调用前，用 Pydantic 校验参数。校验失败时返回包含错误信息的 `ToolMessage`，LLM 下一轮会修正参数。

**理由**: 这样无效参数不会进入 pending action 流程，用户不会看到"确认记账：金额 null"这种无效请求。

**替代方案**: 在 skill 的 `execute` 中校验 —— 太晚，此时已经走了 pending action 流程。

### 3. Plan-Then-Execute 用于 write skills

**选择**: write skills 保持现有的 pending action 拦截机制（已是一种 Plan-Then-Execute），但增强"Plan"阶段的展示信息。

**理由**: 当前架构本质上已经是 Plan-Then-Execute（LLM 计划 → pending → 用户批准 → 执行），不需要大改 graph 结构。重点是增强 Plan 阶段的可解释性。

**增强内容**: `build_confirm_message` 改为：
```
💰 确认记账：化肥 200元（支出）
📝 理解：您说的是"昨天买了200块化肥"
📋 参数：金额=200, 分类=化肥, 日期=2026-06-02
```

### 4. When2Tool router 在 graph 入口实现

**选择**: 在 `invoke_advisor` / `stream_advisor` 的 graph 调用前，增加一个简单的意图分类逻辑。

**规则**:
- 问候语（"你好"、"在吗"）→ 直接回复，不走 graph
- 数据统计查询（"上个月花了多少钱"）→ 走 graph，但 prefer read skills
- 写操作（"记账"、"创建"）→ 走 graph，正常流程

**理由**: 简单规则足以过滤大部分无效 tool call，不需要引入额外的 LLM 调用做意图分类。

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| enum 约束过强导致 LLM 选错分类 | 子串匹配辅助：如果用户说的分类不在 enum 中，选最接近的，并在确认消息中提示 |
| 标签缓存未及时更新 | 标签 CRUD 操作后清除缓存；或者每次请求都加载（标签数量少，开销可忽略） |
| Pydantic 校验增加延迟 | 校验是本地计算，延迟 <1ms，可忽略 |
| Plan-Then-Execute 增加用户操作步骤 | 这是设计目标，write 操作必须有确认 |
| When2Tool router 误判 | 规则保守：不确定时默认走 graph，避免漏掉真正的请求 |
