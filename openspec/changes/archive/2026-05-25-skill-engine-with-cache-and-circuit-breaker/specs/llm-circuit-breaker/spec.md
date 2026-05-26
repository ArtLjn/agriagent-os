## Requirements

### R1: 熔断器实现
- 三态机：CLOSED（正常）→ OPEN（熔断）→ HALF_OPEN（探测）
- CLOSED 状态：正常调用，连续 `failure_threshold` 次失败后转 OPEN
- OPEN 状态：直接抛出 `CircuitOpenError`，不发起实际调用
- HALF_OPEN 状态：放行 1 次探测，成功转 CLOSED，失败转 OPEN
- `recovery_timeout` 秒后从 OPEN 转 HALF_OPEN

### R2: 重试机制
- 调用失败时指数退避重试，最多 `retry_max` 次
- 退避间隔：`retry_backoff_base * 2^attempt` 秒
- 超时错误和认证错误都触发重试
- 重试耗尽后抛出最后一次的异常

### R3: 与 LLM 集成
- 包装 `ChatOpenAI` 的 invoke/stream 方法
- 熔断状态变化时打印日志（CLOSED→OPEN / OPEN→HALF_OPEN / HALF_OPEN→CLOSED）
- HALF_OPEN 探测时记录结果

### R4: 参数配置
- 通过 `config.yaml` 可配置熔断参数
- 默认值：failure_threshold=3, recovery_timeout=30, retry_max=3, retry_backoff_base=2

## Acceptance Criteria
- [ ] DashScope 连续不可用时，第 4 次请求快速失败（不等待超时）
- [ ] 30s 后探测请求成功时恢复正常调用
- [ ] 日志记录熔断状态变化和重试过程
