## Context

farm-manager App 使用 `/chat/stream` 流式端点，用户已经能看到"实时打字"效果。但**首字延迟（Time To First Token）**仍然长达 3-7 秒，因为写操作需要 2 次 LLM 调用：

```
Round 1: 用户输入 → LLM 推理 → tool_call → tool_node 拦截 → PENDING_MARKER
Round 2: LLM 看到 PENDING_MARKER → 生成确认语 → 用户看到 "确认记账..."
```

确认语是 `"💰 确认记账：化肥 200元（支出），确认吗？"`，这个格式完全由 `build_confirm_message()` 模板决定，**不需要 LLM 再写一遍**。第二轮 LLM 调用是纯浪费。

另外，每次请求都重新渲染 system prompt（查询 farm 信息、日期、季节、坐标、active_crops），这部分计算稳定（同 farm 同一天内不变），可以缓存。

当前所有请求都用同一个 LLM 模型，没有区分任务复杂度。

## Goals / Non-Goals

**Goals:**
- 写操作从 2 次 LLM 调用降为 1 次，首字延迟减半
- system prompt 渲染结果按 farm+date 缓存，减少 100-200ms
- 问候/闲聊走轻量模型，降低平均成本
- LLM 调用期间并行预加载上下文数据
- 高频查询结果本地缓存 5-10 分钟

**Non-Goals:**
- 不改流式响应架构（已可用，无需动）
- 不改仿真测试平台
- 不引入新的 LLM 提供商（用现有 provider list 中的轻量模型）
- 不改数据库表结构

## Decisions

### 1. tool_node 直接返回确认语，跳过第二轮 LLM

**选择**: 在 `_parallel_tool_node` 中，当拦截 write skill 时，直接返回包含 `build_confirm_message()` 结果的 `ToolMessage`，不再让 LLM 看到 PENDING_MARKER 后重新生成。

**理由**: 确认语格式完全由模板决定，LLM 生成没有额外价值。跳过第二轮 LLM 可以直接把延迟从 3-7s 降到 1.5-3s。

**实现**: 修改 `ToolMessage(content=f"{PENDING_MARKER} {confirm_text}", ...)` 中的 content，加入足够的信息让 LLM 第一轮就能输出完整的确认语。或者更简单：让 LLM 的 system prompt 中说明"当 tool 返回 PENDING_MARKER 时，直接把它展示给用户"。

**替代方案**: 完全跳过第二轮 LLM，在 `_parallel_tool_node` 后直接返回 pending action 给前端 —— 需要改 graph 结构，侵入性更大。

### 2. system prompt 按 farm_id + date 缓存

**选择**: 在 `prompt_composer.render()` 层面加缓存，key 为 `farm_id + current_date + template_name`。

**理由**: system prompt 包含 farm 名称、位置、季节、active_crops 等，同一天内不会变化。缓存后减少 DB 查询和模板渲染。

**实现**: 用 `functools.lru_cache` 或 Redis（如已有），TTL 设为 1 小时。

### 3. 模型路由按意图复杂度分级

**选择**: 在 `advisor.py` 入口增加简单规则路由：
- 问候语（"你好"/"在吗"）→ 轻量模型（Qwen-Turbo）
- 简单查询（"今天天气"/"花了多少钱"）→ 标准模型
- 复杂分析（"帮我规划种植"）→ 大模型

**理由**: 不需要额外 LLM 调用做意图分类，用规则匹配足够覆盖 80% 场景。

**风险**: 规则可能误判。缓解：规则覆盖 greetings 和简单关键词，不确定时默认走标准模型。

### 4. 并行预加载在 graph entry 实现

**选择**: 在 graph 调用前，用 `asyncio.gather` 并行启动 LLM 调用和上下文数据加载。

**理由**: LLM 调用（2-5s）和 DB 查询（50ms）时间差异大，并行可以重叠。

**预加载内容**: 最近成本记录、当前天气、活跃茬口。这些数据在 tool 执行时大概率需要。

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| 确认语模板化后不够自然 | A/B 测试模板 vs LLM 生成，如果用户反馈模板生硬再回退 |
| prompt 缓存导致数据过期 | TTL 1 小时，farm 信息修改时手动清除缓存 |
| 模型路由误判复杂任务为简单 | 规则保守：只有明确的 greetings 和关键词才走轻量模型 |
| 预加载数据最终没用到 | 预加载是后台任务，不影响主流程，只是轻微增加 DB 负载 |
