## Requirements

### R1: TTL 缓存装饰器
- 提供 `@cached(ttl_seconds, key_fn)` 装饰器，装饰 Skill 的 execute 方法
- `key_fn(params)` 生成缓存 key，默认 `skill_name + hash(params)`
- 缓存命中时直接返回，不执行 Skill 逻辑
- 缓存过期后下次请求重新执行并更新缓存

### R2: 缓存存储
- 内存字典存储，key 为 `(skill_name, cache_key)`，value 为 `(result, expire_timestamp)`
- 每次查询检查 `time.time() > expire_timestamp`，过期则清除
- 无上限淘汰，依赖 TTL 自然过期

### R3: Skill 粒度 TTL
- WeatherSkill: 1800s (30 min)
- CropCycleSkill: 600s (10 min)
- FarmLogSkill: 60s (1 min)
- CostSummarySkill: 300s (5 min)

### R4: 日志和可观测性
- 缓存命中日志：`CACHE HIT skill=xxx age=15s ttl=1800s`
- 缓存未命中日志：`CACHE MISS skill=xxx`
- 不要求缓存命中率统计，但日志应可 grep 分析

## Acceptance Criteria
- [ ] 连续 2 次请求天气，第 2 次日志显示 CACHE HIT 且响应 < 10ms
- [ ] 缓存过期后请求触发 CACHE MISS 并重新执行
- [ ] 不同参数（如不同 cycle_id）各自独立缓存
