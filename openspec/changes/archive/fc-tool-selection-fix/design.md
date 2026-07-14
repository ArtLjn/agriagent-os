## Context

FC 迁移移除了 skillify 预路由后，所有对话请求依赖 LLM 的 Function Calling 能力来选择 tool。当前使用 qwen3.6-flash 模型，其 tool selection 能力有限——明确的 skill 请求（如"我的余额"、"帮我创建春茬种植西瓜"）直接文本回复而不触发 tool call。

**当前 tool description 格式：**
```
获取未来7天天气预报和灾害预警。触发词: 天气、预报、降雨
```
这种"功能说明+触发词列表"格式对小模型不友好——LLM 需要从 description 中理解"用户意图→应该调这个 tool"的映射关系，但当前格式侧重描述 tool 功能而非用户场景。

**当前 system prompt（base.j2）：**
只说"禁止凭记忆回答实时数据，必须先调用对应工具"，但从未列出有哪些工具、各自处理什么场景。小模型需要更明确的指引。

**受影响 Skills（10 个）：**
| Tool Name | 当前 description 问题 |
|-----------|----------------------|
| `get_cost_summary` | 缺少"余额"、"花了多少"、"账"等口语词 |
| `create_crop_cycle` | 缺少"创建"、"种植"、"春茬"、"秋茬" |
| `weather` | 基本可用，但可增强 |
| `create_cost_record` | 触发词较多，相对完善 |
| 其余 6 个 | 均需审查补充 |

## Goals / Non-Goals

**Goals:**
- 优化所有 10 个 Python Skill 的 description，覆盖用户实际口语表达
- 在 system prompt 中注入可用工具映射表，明确告知 LLM 各 tool 的用途
- 确保 qwen3.6-flash 对典型 skill 请求的 tool selection 准确率 ≥ 90%
- 修改后所有现有测试通过

**Non-Goals:**
- 不修改 LangGraph 图结构或 FC 路由机制
- 不引入额外的预路由/关键词匹配层（保持 FC 架构纯净）
- 不修改 model 配置或更换 model
- 不修改 tool 的参数 schema

## Decisions

### D1: description 格式从"功能+触发词"改为"意图场景描述"

**选择：** 将 description 改为"当用户说/问 X 时使用此工具获取/执行 Y"的格式

**理由：** 小模型的 FC 能力依赖 description 中是否包含用户输入的关键词。当前格式"查询农场成本与收入汇总"不包含"余额"，所以"我的余额"无法匹配。新格式直接描述用户意图场景，LLM 能更准确地将用户输入映射到 tool。

**示例：**
```
# Before
查询农场成本与收入汇总，支持按周期、日期范围、分类、记录类型筛选。触发词: 成本、收入、利润、收支

# After
查询农场收支汇总数据。当用户问余额、花了多少、赚了多少、收支情况、成本多少、利润、账单、近期收支时，调用此工具获取真实数据。支持按日期、分类筛选和分组。
```

**替代方案：**
- A) 在 system prompt 中列举所有触发词 → 会大幅增加 prompt token，且维护成本高
- B) 加一层轻量关键词兜底 → 违背 FC 迁移的架构目标
- C) 换更强的模型 → 不可控，且成本更高

### D2: system prompt 注入工具映射表

**选择：** 在 base.j2 的工具调用规则中新增一个【可用工具】段落，列出所有 tool 名称和对应意图

**理由：** 当前 prompt 只说"必须调用对应工具"但从未告知有哪些工具。小模型无法凭空知道 `get_cost_summary` 可以回答"余额"问题。明确列出映射关系后，LLM 能将用户意图与 tool name 关联。

**格式：**
```
【可用工具】
- weather: 天气、预报、降雨、温度
- get_cost_summary: 余额、收支、成本、利润、花了多少
- get_cost_analytics: 趋势、对比、比去年、比上月
- create_cost_record: 记账、花了、买了、卖了、赊账
- create_crop_cycle: 创建茬口、种植、种西瓜、春茬
- get_crop_cycle_info: 周期状态、当前阶段、茬口详情
- get_recent_farm_logs: 农事记录、最近操作、日志
- log_farm_activity: 记农事、浇水、施肥、打药
- update_crop_stage: 进苗期了、到开花期了、阶段更新
- settle_debt: 还钱、还账、清账、还款
```

**替代方案：**
- A) 动态生成映射表 → 需要改代码，且运行时额外消耗 token
- B) 不改 prompt → 不解决根本问题

### D3: 只改 description 文本和 prompt，不改 tool 参数 schema

**选择：** 修改范围限定在 Skill 类的 `description` 属性和 `base.j2` 模板

**理由：** 参数 schema 是 tool 的功能契约，不应因模型能力问题而修改。保持 schema 不变确保 LangGraph 的 FC 路由、pending action 拦截等机制不受影响。

## Risks / Trade-offs

**[Risk] description 变长增加 token 消耗** → 每条 description 从 ~30 字增加到 ~60 字，10 个 tool 总共多 ~300 token/请求，影响可忽略

**[Risk] 触发词覆盖不全仍有遗漏场景** → 这是 FC 架构的固有风险，后续可通过分析 trace 数据迭代优化 description

**[Risk] prompt 工具表需要手动维护** → 新增/修改 skill 时需同步更新 prompt。可通过 CI 检查 skill 列表与 prompt 一致性来缓解

**[Trade-off] 不引入关键词兜底层** → 保持架构纯净，但短期内如果某些边缘场景仍无法命中，需要继续优化 description 而非回退到关键词匹配
