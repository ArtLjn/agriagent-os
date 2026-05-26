## Context

当前 Farm Manager 后端的 LLM 调用链路如下：

```
用户请求 → agent_service → advisor/graph.py → ChatOpenAI.bind_tools(tools) → LLM
```

经 spike 验证确认：
1. **当前模型 `qwen-flash-character` 不支持 Function Calling**（官方文档明确标注，角色扮演专用模型）
2. `bind_tools()` + `tool_choice="required"` 静默失效，LLM 从未调过任何 skill
3. **`qwen3.6-flash` 支持FC，但思考模式下 `tool_choice` 受限**（会返回 400 错误）
4. 关闭思考模式后 FC 正常工作，延迟从 ~5s 降至 ~500ms

关键代码路径：
- `app/core/config.py` — AIConfig 定义模型和 API 配置
- `app/core/llm.py` — `get_llm()` 创建 ChatOpenAI 实例
- `app/agents/graph.py` — `_llm_node` 调用 `bind_tools()`
- `prompts/base.j2` — system prompt（当前措辞"请主动调用"，约束力不足）

## Goals / Non-Goals

**Goals:**
- 让 LLM 能通过标准 function calling 协议调用 skill，获取真实数据
- 配置化控制思考模式开关
- 最小化改动，不改变 LangGraph 图结构
- 确保端到端 tool calling 链路可用

**Non-Goals:**
- 不引入 skillify 意图路由（`handle()` / `fast_match()`）— 属于后续优化
- 不改变 skill 注册机制或 skillify SDK
- 不做多模型路由/策略模式（如天气用 A 模型、闲聊用 B 模型）
- 不改造 LangGraph 图结构（如两阶段意图路由）

## Decisions

### D1: 模型选择 — qwen3.6-flash

**选择**: `qwen3.6-flash-2026-04-16`

**备选方案对比**:
| 模型 | FC | 延迟(思考关) | 上下文 | 费用 |
|------|:--:|:----------:|-------:|:----:|
| qwen3.6-flash | ✅ | ~500ms | 1M | 免费额度 |
| qwen3.6-plus | ✅ | ~800ms | 1M | 免费额度少 |
| qwen-plus(旧) | ✅ | ~600ms | 1M | 免费额度 |

**理由**: qwen3.6-flash 是当前百炼推荐的轻量模型，免费额度充足，1M 上下文，FC 支持完整。对农场管理场景的对话复杂度足够。

### D2: 思考模式控制 — extra_body 传参

**选择**: 通过 `ChatOpenAI` 的 `model_kwargs` 传递 `enable_thinking` 参数

**理由**: DashScope 兼容 OpenAI API，`enable_thinking` 不在 OpenAI 标准参数中，需走 `extra_body` 或 `model_kwargs`。LangChain 的 `ChatOpenAI` 支持 `model_kwargs` 字典透传非标准参数。

**配置方式**:
```yaml
ai:
  model: "qwen3.6-flash-2026-04-16"
  enable_thinking: false
```

### D3: Prompt 强化 — 硬约束措辞

**选择**: 在 `base.j2` 的能力范围段落中，将软性建议改为硬约束指令

**变更**:
```
之前: "请根据用户的问题，主动调用合适的工具获取信息"
之后: "禁止凭记忆回答天气、成本、记录等实时数据。遇到这些信息必须调用工具获取。"
```

**理由**: 即使 FC 机制生效，LLM 仍可能"自信"地直接回答而不调 tool。强化 prompt 是低成本兜底。

### D4: 不使用 tool_choice="required"

**选择**: 保持 `tool_choice` 默认值（不传），依赖 prompt 约束 + FC 能力驱动 LLM 调 tool

**理由**: `tool_choice="required"` 会强制每次都调 tool，闲聊场景也会触发。当前 graph 没有 intent 分类节点来区分"该调 tool"和"自由对话"，全局 required 会破坏体验。

## Risks / Trade-offs

**[角色感弱化]** → qwen-flash-character 有角色扮演能力，切换后"农友"语气可能减弱。→ 通过 system prompt 中的角色定义和语气要求补偿。

**[思考模式未来可能需要]** → 部分复杂推理（如跨周期分析）可能受益于思考模式。→ 当前设计通过配置开关保留可能性，后续可按场景动态切换。

**[tool_choice 仍可能被忽略]** → 即使 FC 生效 + prompt 强化，LLM 仍有概率不调 tool。→ 后续可引入 skillify fast_match 预路由作为第二层保障（不在本次范围）。

**[延迟回归]** → 任何模型变更都可能影响响应时间。→ spike 数据表明 qwen3.6-flash 关闭思考后 ~500ms，优于当前 character 模型的 ~3-5s。
