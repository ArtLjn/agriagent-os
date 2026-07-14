## Context

当前 `backend/prompts/base.j2` 是一个 65 行的单体 prompt，承载了 6 种不同关注点：语言规则、角色定义、回复格式、回复风格、能力范围、工具调用规则。其中 12 条工具触发规则与 `tool_selector.py` 的三层过滤（regex → keyword → LLM intent）完全重复，【农场状态查询】段与 `TOOL_CHAIN_MAP` 链式扩展重复。三个段落各自标注"最高优先级"互相矛盾。

Spike 验证已确认：移除 12 条工具触发规则后 70 个测试全通过。现在需要系统性重构。

关键约束：
- `PromptRegistry` 和 `PromptRenderer` 已稳定运行，不宜重写
- `tool_selector.py` 三层过滤 + `Tool.description` 自动注入已覆盖工具路由
- `TOOL_CHAIN_MAP` 已覆盖查询工具到 `get_farm_status` 的链式扩展

## Goals / Non-Goals

**Goals:**
- 将单体 base.j2 拆分为可组合的 snippet，每个 snippet 职责单一
- 消除 prompt 中的工具路由冗余（已由 tool_selector + Tool.description 覆盖）
- 用 Priority Stack 替代三个互相矛盾的"最高优先级"标注
- 消除 cost_parse.j2 / crop_template_parse.j2 / cycle_parse.j2 中重复的语言规则块
- 保持向后兼容：现有 API 行为不变

**Non-Goals:**
- 不重写 PromptRegistry / PromptRenderer（已稳定）
- 不修改 tool_selector.py 的三层过滤逻辑
- 不引入新的外部依赖
- 不改变 Skill 的 description 编写方式

## Decisions

### Decision 1: Snippet 文件组织方式

**选择**: `prompts/snippets/` 目录，每个 snippet 一个 `.j2` 文件，文件名即 snippet 名

**替代方案**:
- A) 单个 YAML 文件存储所有 snippet — 可读性差，merge conflict 多
- B) Python dict 硬编码 snippet — 违反 prompt-management spec（禁止硬编码超过 20 字）

**理由**: 文件系统是最自然的组织方式，支持热加载（复用现有 `PromptRegistry.reload()`），每个文件职责清晰。

### Decision 2: Composer 组合机制

**选择**: 新增 `PromptComposer` 类，按场景配置 snippet 组合列表，调用 `render_prompt` 渲染每个 snippet 后拼接

**替代方案**:
- A) Jinja2 include 机制 — 需要在模板内控制 include 顺序，模板耦合片段
- B) 在 PromptRegistry 层增加组合逻辑 — 侵入现有稳定模块

**理由**: Composer 是纯新增层，不修改 Registry/Renderer，符合开闭原则。场景配置放在 `config.yaml` 的 `compositions` 段。

### Decision 3: Priority Stack 替代"最高优先级"

**选择**: 在 snippet 文件中标注优先级层级，Composer 按优先级排序拼接

层级定义：
- P1 Safety（安全护栏）：语言规则、工具调用约束
- P2 Accuracy（准确性）：角色定义、能力范围
- P3 Format（格式）：回复格式、回复风格
- P4 Context（上下文）：时间信息、用户信息

**理由**: 明确的优先级层级消除了三个"最高优先级"的矛盾，且在 token 有限时可以按优先级截断。

### Decision 4: 工具触发规则完全移除

**选择**: 不在 prompt 中保留任何工具路由规则

**理由**: Spike 验证通过。`tool_selector.py` 三层过滤 + `Tool.description` 自动注入 + `TOOL_CHAIN_MAP` 链式扩展已完全覆盖。保留行为约束（"禁止编造数据"）但移除路由规则（"用户提到天气 → 调用 weather"）。

## Risks / Trade-offs

- **[Risk] LLM 无 prompt 引导时可能跳过工具调用** → 通过 `Tool.description` 的质量来缓解：每个 Skill 的 description 包含触发词和场景描述。Spike 已验证有效。
- **[Risk] Composer 增加一层间接性** → Composer 逻辑简单（读取配置 → 按 priority 排序 → 渲染拼接），不超过 50 行。
- **[Trade-off] Snippet 粒度选择** → 过细（每个规则一个 snippet）增加管理成本，过粗失去组合灵活性。选择按关注点（concern）拆分，约 6-7 个 snippet。

## Migration Plan

1. 新增 `snippets/` 目录和 snippet 文件（增量，无破坏性）
2. 新增 `PromptComposer` 类（增量）
3. 在 `config.yaml` 新增 `compositions` 配置
4. 切换 `advisor.py` 从 `render_prompt` 到 `composer.compose`
5. 移除 base.j2 中的冗余段（已在 Spike 中完成）
6. 更新测试
7. **回滚**: 恢复 base.j2 原始内容，`advisor.py` 改回 `render_prompt`

## Open Questions

- snippet 的 Jinja2 变量注入方式：是每个 snippet 独立注入，还是 Composer 统一注入后分发给各 snippet？倾向于后者，减少重复渲染开销。
