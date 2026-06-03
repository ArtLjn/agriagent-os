## Why

当前 farm-manager Agent 的 write skills（记账、创建模板等）存在三个影响用户体验和数据质量的问题：

1. **分类不一致**: `create_cost_record` 的 `category` 是开放字符串，LLM 对同一概念可能返回"化肥"、"肥料"、"复合肥"等变体，导致报表统计时同一类支出被拆成多个分类，数据混乱。

2. **参数解析失败无自纠错**: 用户说"记一笔账"（缺少金额），LLM 生成 pending action 后用户才意识到缺参数，流程中断。理想情况下 LLM 应在 tool call 前自我修正。

3. **确认信息不透明**: pending action 只展示"确认记账：化肥 200元"，用户看不到 LLM 是如何从原话中提取出这些参数的，无法判断理解是否正确。

4. **无效 tool call 过多**: 简单问答（如"上个月花了多少钱"）也走完整的 tool calling 流程，增加延迟和成本。

## What Changes

- **Tool Schema 动态 enum**: `create_cost_record` 的 `category` 参数改为从用户 `cost_categories` 表中动态加载的 enum 列表，LLM 必须从现有标签中选择
- **Pydantic 参数校验 + 自纠错**: 在 LangGraph tool node 中用 Pydantic 校验 tool call 参数，失败时把错误信息反馈给 LLM 让其自动修正
- **Plan-Then-Execute 架构**: write skills 改为"LLM 输出计划 → Orchestrator 校验 → pending confirm → 执行"流程，LLM 不能直接触发写操作
- **确认消息展示完整上下文**: pending action 消息包含"原话理解 + 提取参数 + 将要执行的操作"
- **When2Tool router**: 闲聊/简单问答直接回复，不调用 tool；只有数据查询和修改才走 tool calling
- **LLM 无创建标签权限**: 新分类不自动创建，pending action 中提示用户可手动添加

## Capabilities

### New Capabilities
- `write-skill-schema-constraint`: write skill 参数约束（动态 enum、Pydantic 校验）
- `write-skill-plan-execution`: Plan-Then-Execute 执行模式
- `agent-intent-router`: 用户意图路由（闲聊 vs 查询 vs 修改）
- `pending-action-context-display`: 确认消息上下文展示

### Modified Capabilities
- （无 spec-level 需求变更，纯实现层优化）

## Impact

- **后端**: `backend/app/agent/skills/create-cost-record/scripts/main.py`、`backend/app/agent/graph.py`、`backend/app/agent/skills/__init__.py`
- **API**: `/agent/chat` 的响应格式不变，但内部执行流程变化
- **前端**: pending action 展示内容更丰富
- **数据库**: 不改表结构，只改参数校验逻辑
