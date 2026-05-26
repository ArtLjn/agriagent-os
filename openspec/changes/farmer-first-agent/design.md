## Context

当前 Agent 的 system prompt（base.j2）只注入时间变量（current_date/weekday/time），不包含任何农场数据。所有农场信息依赖 Agent 自主调用 Skill 工具获取，但 Agent 并不总是调用——导致回复经常泛泛而谈。

回复格式无约束，Agent 平均输出 300-500 字的 Markdown 长文，农户（父母辈）没有耐心阅读。

5 个现有 Skill 全是只读查询类，农户要记一笔账、建一个茬口，必须退出对话去表单操作。

系统约束：2h2g 服务器、SQLite、3-4 个农户用户、GLM-4 模型。

## Goals / Non-Goals

**Goals:**
- Agent 每次回复前自动获取农场上下文（茬口、农事、债务、天气），作为 prompt 的一部分注入
- 回复格式短而准：每条建议 ≤2 行，总共 ≤5 条，先说结论再说原因
- 5 个写操作 Skill 让农户通过对话完成记账、建茬口、记农事、还赊账、更新阶段
- 每日建议从纯文本改为结构化返回，前端卡片化渲染
- 上下文注入层收拢到 farm_context_service，为以后加 RAG/MySQL 留扩展口

**Non-Goals:**
- 向量 RAG（当前全是结构化数据，SQL 就够，且 2h2g 跑不动向量库）
- MySQL 迁移（当前用户量不需要，以后改只需换 DATABASE_URL）
- 推送通知（无推送通道）
- 病虫害图片识别
- 多农场管理

## Decisions

### Decision 1: 上下文注入用「结构化摘要」而非 RAG

**选择**: 在 `farm_context_service.build_summary(farm_id)` 中查库组装 ≤300 字摘要，注入 `{{ farm_context_summary }}`。

**摘要组成**:
- 活跃茬口：≤3 个（名称 + 当前阶段 + 预计采收日）
- 近期农事：≤3 条（最近 3 天）
- 未结清债务：≤3 笔（最近到期的）
- 月度成本：1 条汇总（金额）
- 天气：≤3 天（从已有 weather skill 缓存取）

**理由**: 全部是结构化数据，SQL 精确查询比向量检索准确。摘要体积约 180 tokens，占上下文窗口 <1%。

**替代方案**: RAG 向量检索。拒绝理由：2h2g 跑不动向量库，「欠多少钱」这类聚合查询向量查不准。

### Decision 2: 回复格式通过 prompt 硬约束控制

**选择**: 在 base.j2 中增加 `{{ response_format_rules }}` 模板块，内容为：

```
【回复格式】（最高优先级，必须遵守）
- 称呼用户为「{{ display_name }}」
- 每条建议/操作不超过2行
- 总共不超过5条
- 先说结论，再说原因（如：明天降温12° → 你那西瓜正伸蔓期怕冻）
- 禁止铺垫、寒暄、总结段
- 用「你」不用「您」，口语化
```

**理由**: 格式控制在 prompt 层比后处理截断更自然，LLM 能理解并遵守。

**替代方案**: 后端对输出做截断/摘要。拒绝理由：截断会破坏语义，不如让 LLM 直接生成短文本。

### Decision 3: 写操作 Skill 通过 skillify 框架统一管理

**选择**: 5 个写操作 Skill 和现有只读 Skill 一样通过 skillify 注册为 LangChain StructuredTool。区别在于：

1. Skill 的 `execute()` 内部先做 Pydantic 参数校验
2. `graph.py` 中写操作 Skill 的 tool description 标注 `[需确认]`
3. Agent 调用写 Skill 时，在 `_llm_node` 中拦截，先返回确认消息给用户
4. 用户确认后，通过 `chat_with_agent(message="确认", pending_action_id=xxx)` 触发执行

**确认流程**:
```
农户：「昨天买了200块化肥」
Agent：「记一笔：化肥 200元，现金。确认？」
农户：「确认」/「是赊账，农资店老王那」
Agent：「好的，已记账。化肥 200元，赊账，农资店老王。」
```

**理由**: 农户可能说错金额，确认机制防误操作。不需要每次都确认——查询类直接执行，只有写操作需要确认。

**替代方案**: 无确认直接执行。拒绝理由：记账金额错了用户会不信任系统。

### Decision 4: 每日建议返回结构化 JSON

**选择**: `DailyAdviceResponse` 从 `{advice: str}` 改为：
```python
class AdviceItem(BaseModel):
    title: str          # ≤10字，如「明天降温关风口」
    detail: str         # ≤40字，如「12°低温，你那西瓜伸蔓期怕冻」
    priority: int       # 1-3，1=最紧急
    icon: str           # emoji，如 🌡️

class DailyAdviceResponse(BaseModel):
    cycle_id: int | None = None
    items: list[AdviceItem]
    created_at: datetime
```

**理由**: 前端可以每条建议独立渲染卡片，带优先级排序和图标，比 Markdown 文本更直观。

**BREAKING**: 移动端需同步更新 AdviceCard 组件。

### Decision 5: farm_context_service 作为唯一的上下文组装入口

**选择**: 所有农场上下文组装逻辑收拢到 `services/farm_context_service.py`，agent_service 只调用 `build_summary()`。

**理由**: 以后加 RAG 知识库检索、MySQL 迁移、用户画像等，只需要改 farm_context_service 内部增加数据源，上层全部不动。

**扩展路径**: `farm_context_service` 内部可按数据源拆分策略——当前只有 `SQLStrategy`，以后可加 `RAGStrategy`、`ProfileStrategy`，每个策略独立实现 `build()` 方法。

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|---------|
| 写操作 Skill 参数提取不准（农户说「200块化肥」没说是不是赊账） | 默认为现结，Agent 追问「现金还是赊账？」而非猜测 |
| 回复格式约束被 LLM 忽略 | 在 prompt 中标注「最高优先级」，并加 few-shot 示例 |
| 结构化返回格式 BREAKING 改动 | 移动端同步发版，API 版本号加 v2 前缀过渡 |
| 确认流程增加对话轮次，农户觉得烦 | 只写操作确认，查询不确认；常用操作学习后可跳过确认 |
| 上下文摘要查询增加延迟 | 摘要查库 <10ms，可缓存在内存（farm_id 维度，5 分钟过期） |

## Open Questions

1. 确认流程的 `pending_action` 存在哪？内存（快但重启丢失）还是 SQLite（持久但多一次 IO）？→ 倾向内存，用户不会在重启间隙确认
2. 称呼（display_name）从哪来？用户注册时的名字？还是设置页单独填？→ 倾向设置页填，默认用「农友」
3. 多茬口时，每日建议是所有茬口混在一起排序（按 priority），还是按茬口分组？→ 倾向按 priority 混排，因为农户关心的是「今天最该干嘛」，不是「西瓜该干嘛」
