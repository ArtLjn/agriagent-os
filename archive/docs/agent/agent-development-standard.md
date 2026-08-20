---
last_updated: 2026-07-17
status: active
---

# Agent 开发规范

本文是 farm-manager Agent 平台开发的硬性规范。目标不是让代码“看起来工程化”，而是让每次 Agent 改动都可解释、可回放、可验证、可回滚。

凡修改 `backend/app/agent/`、`backend/app/application/`、`backend/app/skills/`、`backend/app/prompt/`、`backend/app/context/`、`backend/app/memory/`、`backend/app/evaluation/`、`backend/app/infra/trace*` 或相关测试，均必须遵守本文。

## 1. 核心原则

1. 简单优先：能用现有边界解决，不新增框架；能用模型基于 schema 选择，不堆规则词库；能局部修复，不跨层重构。
2. 工具优先：Agent 不能声称查了数据，除非本轮真实调用了对应只读工具，或明确说明没有查询。
3. 证据优先：所有工具选择、拒绝、澄清、写入确认、反思判定都必须进入 trace 或可从测试复现。
4. 回归优先：任何修 prompt、router、tool binding、context 的改动，都必须补多轮回归测试。
5. 边界优先：Runtime 只执行图和节点协议，不承载 Prompt、Context、Memory、业务数据访问或工具策略治理。

## 2. 禁止行为

以下行为一律禁止：

- 在 `classifier.py`、`tool_selector.py` 或 prompt 中继续堆业务关键词词库来修单个 case。
- 为了让某句话命中工具，新增“财务、账务、茬口、库存、天气”等领域词到通用分类器。
- 让规则层长期承担“用户意图 -> 具体业务工具”的主判断；只读工具选择应优先交给模型基于工具 schema 和上下文决定。
- 让 Agent 在没有工具调用结果时编造“已查询数据库、已写入、已更新、已获取实时天气”等事实。
- 写操作缺少确认链路时直接落库。
- 在 Runtime 节点中直接查询数据库、直接读写 Memory store、直接拼接 Prompt 模板或直接访问 Context selector。
- 为单个 bug 新增抽象层、Manager、Protocol、Hook、Plugin、mini classifier。
- 新增未使用代码、兼容空壳目录、临时脚本、dead code。
- 用 `print`、`console.log` 或临时文件调试生产链路。
- 测试只覆盖成功路径，不覆盖误触发、无工具、缺参、写入确认、多轮上下文。

## 3. 模块边界

| 模块 | 允许职责 | 禁止职责 |
| --- | --- | --- |
| `application/` | Chat/SSE/use case 编排、会话保存、Context/Memory/Runtime 组装 | HTTP 细节、模型节点实现、直接写底层表 |
| `agent/runtime/` | LangGraph 节点、消息压缩、模型调用、工具执行循环、流事件 | Prompt 治理、Context selector、Memory store、业务查询 |
| `agent/router/` | 粗粒度风险门禁、写入澄清、候选工具预算、只读工具池暴露 | 长期维护业务词库、硬编码每个业务意图到工具 |
| `skills/` | 单一业务能力的参数 schema、权限、执行适配 | 跨流程编排、Prompt 拼接、会话状态管理 |
| `prompt/` | Prompt 版本、片段、组合、渲染、回放 | 查询数据库、选择业务上下文 |
| `context/` | ContextBundle、selector、预算、压缩、缓存 | Runtime 执行、工具调用、副作用写入 |
| `memory/` | 短时/长期记忆接口、observation、检索端口 | API 路由、Runtime 状态机 |
| `evaluation/` | replay、case、指标、报告、回归门禁 | 生产副作用、人工标注真值静默生成 |
| `infra/trace*` | 链路记录、查询、清理、观测适配 | 业务决策、工具选择策略 |

## 4. Router 与工具选择

Router 的职责是保护系统，不是替模型思考。

必须遵守：

- 只读请求默认优先暴露可用只读工具池，并使用 `tool_choice=auto`。
- 工具是否调用、调用哪个只读工具，由模型根据用户输入、会话上下文和工具 schema 决定。
- 规则层只能承担这些职责：
  - 写操作风险识别和确认。
  - 明显寒暄、教程类、代码排查类输入的无工具保护。
  - 高风险操作拒绝或澄清。
  - schema token 预算和工具数量预算。
- 每新增一条确定性规则，必须同时写清：
  - 为什么不能交给模型。
  - 误触发边界是什么。
  - 对应正向和负向测试。
  - 是否有过期条件。

禁止：

- 用 `if "财务" in message`、`if "账务" in message` 这类业务词映射工具。
- 用一组 `like` 字符串替代工具 schema、few-shot 或数据飞轮。
- 为每个新用户表达都改 classifier。
- 把读操作路由成写操作候选。

## 5. Skill 开发规范

每个 Skill 必须是一个清晰业务能力，不是一个小 Agent。

必须包含：

- 稳定工具名，使用 snake_case。
- `skill.md` frontmatter 的能力名和类型标记。
- 明确 `read` / `write_confirm` / `write_high` 风险级别。
- 参数 JSON Schema，必填字段不能靠模型猜默认值。
- 正向示例和反向示例。
- 缺参策略。
- 失败策略。
- 只读缓存策略或明确不缓存。
- 测试覆盖正常、缺参、权限/农场隔离、服务异常。

`skill.md` frontmatter 规范：

- `type` 只允许 `read` 或 `write`，禁止继续使用历史值 `read-only`。
- `type: read` 表示不改变系统状态；它可以依赖上下文、权限或外部只读数据，但不应进入 pending 确认。
- `type: write` 表示 capability 具有写风险，会创建、更新、删除、结算、同步成本或修改设置，默认进入 pending 确认或由 operation-aware metadata 决策。
- 聚合 Skill 只要包含任何写 operation，frontmatter 必须使用 `type: write`；如果同一聚合 Skill 也包含查询 operation，必须通过 runtime metadata 或 Registry operation risk 推断，确保具体 read operation 降级为 read/no pending。
- `skill.md type` 是治理和文档层标记；真正执行时以 runtime metadata、Registry operation risk 和 pending action 白名单共同决定。
- 如果目录使用 kebab-case 能力名，frontmatter `name` 应与目录一致；runtime LangChain tool 仍需保持 snake_case 兼容名时，必须显式声明 `tool_name`。

写操作 Skill 额外要求：

- 默认进入 pending action 或确认链路。
- 回复中必须明确待确认的对象、动作、关键字段。
- 确认前不得落库。
- 确认后必须记录 trace、pending action 状态和缓存失效目标。

只读 Skill 额外要求：

- 返回结构化结果，不只返回自然语言。
- 无数据时必须返回“无数据”语义，不允许编造样例。
- 数据范围必须受 `farm_id`、`user_id` 或权限上下文限制。

## 6. Prompt 规范

Prompt 是行为契约，不是兜底脚本。

必须遵守：

- Prompt 只描述角色、边界、工具使用原则和输出格式。
- 不把业务数据硬编码进 prompt。
- 不用 prompt 伪造工具结果。
- 不用 prompt 弥补缺失的 Skill schema 或权限校验。
- Prompt 改动必须有 replay 或至少有 targeted regression。

涉及工具使用的 Prompt 必须明确：

- 有工具结果时基于工具结果回答。
- 没有工具结果时不得声称已经查询。
- 对能力询问，应基于当前可用工具说明可查询范围。
- 写操作必须先确认。

## 7. Context 与 Memory 规范

Context 只给模型必要信息，不能把数据库整包塞进上下文。

必须遵守：

- 通过 `ContextBuilder` 和 selector 构造 `ContextBundle`。
- 每个 ContextBlock 必须有来源、预算和裁剪策略。
- 多轮依赖必须来自会话历史、summary、pending action 或明确 memory view。
- Runtime 不直接调用 selector。
- Memory observation 只能记录可沉淀事实，不能记录用户临时情绪、推测或工具失败幻觉。

禁止：

- 为了解决一次多轮问题，把完整历史或全量业务表直接注入 Prompt。
- 在 Memory 中保存未确认写操作。
- 把模型猜测结果写入长期记忆。

## 8. 多轮对话规范

凡涉及“上一轮说过”“继续查”“给我几个选项”“那你可以查啥”“查询我的财务”等上下文依赖问题，必须按多轮问题处理。

必须覆盖：

- 上一轮能力说明影响下一轮工具选择。
- 用户纠正 Agent 时，下一轮必须吸收纠正。
- 用户从泛问切到具体查询时，必须重新进入工具选择。
- 用户要求选项时，选项应来自可用工具/能力或真实数据，不得编造系统没有的能力。

回归测试至少包含：

- 会话历史输入。
- Router decision。
- 绑定工具列表。
- 最终回复是否与工具调用一致。

## 9. Trace 与排查规范

Agent 问题不得靠猜。

排查必须优先收集：

- `session_id`
- `trace_request_id`
- 用户消息和助手回复。
- `router_diagnostics`
- `selected_tools`
- `skill_calls`
- `pending_actions`
- LLM 调用摘要。
- 反思结果和 policy violation。

修复前必须回答：

- 模型没选工具，还是工具没执行，还是工具结果没进入最终回复。
- 是单轮问题，还是多轮上下文问题。
- 是 Prompt 问题、Router 问题、Skill schema 问题、Context 问题、Reflection 问题，还是数据问题。

禁止未看 trace 就修改 prompt/router。

## 10. 测试门禁

Agent 改动必须按影响面选择测试。不能只跑一个 happy path。

| 改动类型 | 必跑测试 |
| --- | --- |
| Router / classifier / tool binding | `backend/tests/agent/router/test_skill_router.py`、`backend/tests/agent/test_runtime_router_binding.py` |
| Skill schema 或执行 | 对应 `backend/tests/skills/test_*.py`，必要时 API/Service 测试 |
| Prompt 改动 | replay/eval case 或 targeted chat/use case 测试 |
| Context / Memory | context、memory、chat use case、runtime binding 测试 |
| Reflection / guardrails | reflector、runtime reflection、pending action 测试 |
| 前端 Playground trace/debug | 对应前端单测，加一次复制/导出格式回归 |

最小验证命令：

```bash
ruff check backend/app/agent backend/tests/agent
pytest backend/tests/agent/router/test_skill_router.py backend/tests/agent/test_runtime_router_binding.py -q
bash scripts/check-complexity-budget.sh
```

上线前按实际影响面增加：

```bash
bash scripts/check-layer-deps.sh
bash scripts/check-skill-docs.sh
bash scripts/harness-check.sh
```

## 11. 代码复杂度门禁

新增 Agent 代码必须满足：

- 单文件不超过 500 行；超过必须拆分或说明历史债务，不得继续加重。
- 单函数不超过 50 行；超过必须拆步骤。
- 新增抽象必须有两个以上真实调用方，或明确消除已有重复复杂度。
- 不新增一次性兼容入口。
- 不新增未被测试覆盖的分支。
- 删除被替代的旧逻辑，不保留 dead code。

对 `classifier.py`、`tool_selector.py`、`runtime/nodes.py`、`tool_executor.py` 这类已超预算文件，默认只能做瘦身或迁出逻辑；除紧急修复外，禁止继续塞新职责。

## 12. 数据与权限规范

Agent 必须默认不可信，所有业务数据访问必须受权限和租户边界约束。

必须遵守：

- 所有业务读写使用当前 `user_id`、`farm_id` 或明确管理员上下文。
- Skill 不得绕过 service/repository 的权限判断。
- Admin 能力不得暴露给普通用户 Skill。
- 认证、密码、token、密钥、配置热更新默认 `forbidden_for_llm` 或 `admin_skill`。
- 日志和 trace 不得输出明文密钥、数据库密码、用户敏感字段。

## 13. 开发流程

每次 Agent 改动按以下顺序执行：

1. 读 trace 或复现 case。
2. 判定问题层级：Prompt / Router / Tool / Context / Memory / Reflection / Data。
3. 写最小修复方案，说明为什么不走更重方案。
4. 先加或更新失败测试。
5. 实现最小改动。
6. 跑 targeted tests。
7. 跑 lint 和复杂度检查。
8. 清理 `__pycache__`、`.pyc`、`.DS_Store`。
9. 如影响线上，部署并检查服务状态和 `/health`。
10. 在最终说明中列出改动、验证、风险。

## 14. 完成定义

满足以下条件才允许说“完成”：

- 问题根因已说明。
- 改动边界清楚，没有无关重构。
- 新行为有测试覆盖。
- 误触发边界有负向测试。
- lint/test/复杂度检查已运行并记录结果。
- 线上部署已验证，或明确说明未部署。
- trace 或测试能证明 Agent 不再无工具编造结果。

## 15. 评审清单

评审 Agent 改动时逐项检查：

- 是否把模型能做的只读工具选择又写回规则层。
- 是否新增了业务词库或 mini classifier。
- 是否有多轮上下文回归。
- 是否验证无工具时不会声称已查询。
- 是否验证写操作确认链路。
- 是否保持 Prompt、Context、Memory、Runtime 边界。
- 是否新增了未测试分支。
- 是否引入了新的复杂度债务。
- 是否能通过 trace 定位本次行为。

只要以上任一项失败，本次 Agent 改动不得合并或上线。
