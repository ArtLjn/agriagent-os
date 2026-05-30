## Context

当前 farm-manager 的 LLM 调用链路为：`API endpoint (async)` → `advisor.py (ainvoke/astream)` → `graph.py _llm_node (sync llm.invoke())` → `Ollama/NVIDIA/DashScope API`。

`LLMClientManager` 已有多 provider 路由和指数退避 cooldown，但存在三个生产阻塞问题：
1. `_llm_node` 同步阻塞事件循环，并发请求排队
2. `_get_first_available()` 始终返回优先级最高的同一个模型，无法分散负载
3. cooldown 上限 24h 后重试已死模型，形成失败循环

项目即将面向 3-4 个真实用户。

## Goals / Non-Goals

**Goals:**
- 3-4 用户并发时请求不互相阻塞
- 请求分散到多个 provider/model 组合，避免单点速率限制
- 长期不可用的模型/服务自动跳过，无需人工干预
- 运维可通过配置手动禁用指定模型

**Non-Goals:**
- 不做全局请求队列/排队系统（3-4 用户不需要）
- 不做基于延迟的智能路由（简单轮询足够）
- 不做跨实例的分布式负载均衡（单实例部署）
- 不改 graph 的 LangGraph 结构，只改节点内部实现

## Decisions

### D1: `_llm_node` 改为 async + Semaphore

**选择**：`_llm_node` 改为 `async def`，使用 `await llm.ainvoke()`，外层加 `asyncio.Semaphore(5)` 控制最大并发。

**替代方案**：
- `run_in_executor` 包装同步调用 → 需要额外线程池管理，不如原生异步干净
- 不限制并发 → 3-4 用户同时请求时可能打爆 provider rate limit

**理由**：LangGraph 支持异步节点，`ChatOpenAI` 的 `ainvoke` 已经是原生异步。Semaphore 防止突发请求过多。

### D2: 加权路由（按成本优先）

**选择**：`_get_first_available()` 改为 `_get_next_available()`，按 provider 的 `weight` 字段加权随机选择。跳过 cooldown/DEAD/`enabled:false` 的模型，在可用模型中按权重分配。

providers.json 新增 `weight` 字段：
```json
{
  "providers": [
    {"name": "ollama", "weight": 8, ...},      // 免费，80% 流量
    {"name": "nvidia", "weight": 2, ...},       // 免费 API 额度有限，15% 流量
    {"name": "dashscope", "weight": 1, ...}     // 付费，5% 流量兜底
  ]
}
```

权重含义：`ollama:8` + `nvidia:2` + `dashscope:1` = 总权重 11，ollama 概率 8/11 ≈ 73%。

**替代方案**：
- 纯 Round-Robin → 不区分免费/付费，付费 provider 被等概率调用，浪费成本
- 优先级选择（当前方案）→ 所有流量集中在一个模型，单点压力
- 加权轮询（Weighted Round-Robin）→ 3-4 用户并发量低，随机已足够均匀

**理由**：3-4 用户并发量低（峰值 < 10 RPM），加权随机比分发更简单且效果等价。免费 provider 拿大部分流量，付费只在免费 provider cooldown/DEAD 时才被选中。缺省 weight=1，向后兼容。

### D3: 去掉 LLM_INSTANCE 全局单例缓存

**选择**：`llm.py` 的 `get_llm()` 每次返回新的 `ChatOpenAI` 实例，通过 `_get_next_available()` 获取不同模型。

**替代方案**：
- 保留单例，定期刷新 → 增加复杂度，轮询不生效
- 实例池 → 过度设计

**理由**：`ChatOpenAI` 是轻量对象（只存配置），创建成本可忽略。每次新建才能实现真正的负载均衡。

**注意**：`graph.py` 中的 `graph` 对象也缓存了 LLM 实例，需要改为每次调用时获取新的 LLM。

### D4: 分级熔断策略

**选择**：三级状态，`COOLING → WARMING → DEAD`。

| 状态 | 触发条件 | cooldown | 恢复方式 |
|------|---------|----------|---------|
| COOLING | 1-3 次失败 | 2→4→8 min 指数退避 | 自动 |
| WARMING | 4-9 次失败 | 24h | 自动 |
| DEAD | ≥10 次失败 | 永久 | reload API 或热更新 |

**Provider 级别联动**：同一个 provider 下 ≥50% 的模型处于 WARMING 或 DEAD 时，整个 provider 标记为不可用。

**替代方案**：
- 纯指数退避（当前方案）→ 24h 后重试死模型
- 固定阈值熔断 → 不够灵活

**理由**：分级策略兼顾了瞬时错误容忍和长期故障隔离。10 次连续失败足够判定为长期不可用。

### D5: providers.json `enabled` 字段

**选择**：provider 和 model 级别都支持 `enabled: false`，缺省为 `true`。向后兼容。

```json
{
  "name": "ollama",
  "enabled": true,
  "models": [
    {"id": "gemma4:31b", "priority": 1, "enabled": true},
    {"id": "glm-4.7", "priority": 2, "enabled": false}
  ]
}
```

**理由**：运维可主动禁用问题模型，watchfiles 自动检测变化后生效。

## Risks / Trade-offs

- **每次请求新建 ChatOpenAI** → 有微小性能开销（约 0.1ms）→ 可忽略
- **去掉 LLM_INSTANCE 缓存** → `llm.py` 中 `get_llm()` 的调用方需要适配 → 改动范围可控（graph.py、skills/）
- **加权随机** → 3-4 用户并发量低时分布可能不够均匀 → 可接受，用户无感知
- **Semaphore 大小** → 设为 5 是经验值，Ollama 免费账号约 10 RPM/key，2 个 key = 20 RPM → 5 并发合理
- **DEAD 状态需手动恢复** → 可能遗漏 → 提供了 reload API 和 watchfiles 两种恢复路径
