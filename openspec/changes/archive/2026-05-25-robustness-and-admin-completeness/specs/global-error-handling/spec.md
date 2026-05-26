## ADDED Requirements

### Requirement: 全局异常处理器
系统 SHALL 注册 FastAPI 全局异常处理器，将所有未捕获异常转换为统一 JSON 格式，不泄漏 Python 堆栈信息。

#### Scenario: 未捕获异常返回 500
- **WHEN** 业务代码抛出未捕获的 Exception
- **THEN** API 返回 500，body 为 `{"detail": "内部服务器错误"}`，完整堆栈仅写入日志

#### Scenario: HTTPException 原样返回
- **WHEN** 代码抛出 HTTPException(status_code=404, detail="未找到")
- **THEN** API 返回 404，body 为 `{"detail": "未找到"}`

#### Scenario: 请求验证错误返回 422
- **WHEN** 请求体不符合 Pydantic 模型
- **THEN** API 返回 422，body 包含 `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}`

#### Scenario: GraphRecursionError 返回 429
- **WHEN** Agent 迭代步数超限抛出 GraphRecursionError
- **THEN** API 返回 429，body 为 `{"detail": "Agent 思考步数超限，请简化问题后重试"}`

### Requirement: 请求限流
系统 SHALL 对所有 API 请求实施基于 IP 的速率限制。全局限制为 30 次/分钟/IP，Agent 相关接口限制为 10 次/分钟/IP。

#### Scenario: 正常请求不被限流
- **WHEN** 用户在 1 分钟内发送 20 个普通请求
- **THEN** 所有请求正常处理

#### Scenario: 超过全局限流
- **WHEN** 同一 IP 在 1 分钟内发送超过 30 个请求
- **THEN** 超出请求返回 429，包含 `Retry-After` header

#### Scenario: 超过 Agent 接口限流
- **WHEN** 同一 IP 在 1 分钟内发送超过 10 个 Agent 请求
- **THEN** 超出请求返回 429

### Requirement: farm_id 统一依赖注入
所有需要 farm_id 的 API 路由 SHALL 通过 `Depends(get_current_farm)` 获取，禁止使用 Query 参数传入 farm_id。

#### Scenario: 通过依赖注入获取 farm_id
- **WHEN** 请求 cost 或 cost_categories 接口
- **THEN** farm_id 从认证上下文自动注入，不接受 Query 参数

#### Scenario: 消除 Query 参数越权
- **WHEN** 攻击者尝试通过 `?farm_id=2` 访问他人数据
- **THEN** Query 参数被忽略，仅使用认证上下文中的 farm_id

### Requirement: 数据库事务回滚保护
所有 service 层的 `db.commit()` 操作 SHALL 包裹在 try/except 中，异常时执行 `db.rollback()`。

#### Scenario: 提交失败自动回滚
- **WHEN** db.commit() 因约束违反抛出异常
- **THEN** 事务回滚，数据库状态不变，API 返回 500 或 400（取决于异常类型）

#### Scenario: 提交成功无影响
- **WHEN** db.commit() 正常完成
- **THEN** 数据正常持久化
