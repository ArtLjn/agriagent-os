## Why

Admin-web 只有 Create/Read，缺 Edit/Delete，功能不完整；后端 Agent 无 Max Steps 限制可无限循环、无输入/输出审核、零认证、无全局异常处理、LLM 输出未校验直接入库；整个系统无可观测性（只有 stdout 日志），无法追踪 Agent 决策路径和 Token 成本。这些问题在生产环境下会导致账单爆炸、数据污染、安全漏洞。

## What Changes

- **BREAKING**: Agent 图增加 recursion_limit 限制最大迭代步数，超限强制终止
- 后端新增全局异常处理器，统一错误响应格式，防止堆栈泄漏
- 后端新增请求限流中间件（Rate Limiting）
- Schema 层强化校验：ChatRequest 消息长度限制、CostRecord 枚举/金额范围校验、各字段 min/max 约束
- cost_service.parse_record 增加 JSON 解析保护和 LLM 输出字段二次校验
- farm_id 统一通过 `Depends(get_current_farm)` 注入，消除 Query 参数越权风险
- Agent 输入增加基础敏感词/注入检测，输出增加 PII 正则过滤
- 引入 LangSmith 可观测性：自动追踪 Agent 每步决策、Token 消耗、延迟拆解
- 后端数据库操作增加事务回滚保护（try/except + rollback）
- Admin-web 补全所有 CRUD 页面的 Edit/Delete 功能
- Admin-web 列表页增加分页支持
- Admin-web 统一错误处理风格，补全 TypeScript 类型定义

## Capabilities

### New Capabilities

- `agent-safety-guard`: Agent 安全防护——Max Steps 限制、输入 Guardrails（注入检测/敏感词）、输出 PII 过滤、Token 消耗上限
- `global-error-handling`: 全局异常处理器 + 统一错误响应格式 + 请求限流
- `langsmith-observability`: LangSmith 接入——自动 trace 上报、Token/成本统计、Agent 决策路径可视化
- `admin-crud-completion`: Admin-web CRUD 补全——所有页面增加 Edit/Delete、列表分页、类型补全、错误处理统一

### Modified Capabilities

（无现有需要修改的 capability）

## Impact

- **后端 Agent**: graph.py 编译参数变更（增加 recursion_limit），advisor.py/report.py 增加安全拦截
- **后端 API**: 所有路由 farm_id 注入方式统一；新增中间件层（异常处理、限流）
- **后端 Schema**: 多个 Pydantic 模型增加字段校验规则（BREAKING for 非法输入）
- **后端依赖**: 新增 langsmith pip 包
- **后端配置**: config.yaml 新增 langsmith 和 rate_limiting 配置段
- **前端 Admin-web**: 8 个页面组件修改（增加 Edit/Delete 交互），API 层增加 PUT/DELETE 方法，TypeScript 类型补全
