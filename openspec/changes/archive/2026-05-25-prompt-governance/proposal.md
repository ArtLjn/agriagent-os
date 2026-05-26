## Why

当前 Agent 的提示词以硬编码字符串分散在 4 个 Python 文件中，导致三个生产级问题：LLM 偶发输出英文单词（同一指令重复但位置弱被冲淡）、自然语言记账时日期默认错误（如选成 2023 年）、创建类操作偶发失败（LLM 输出格式不符或缺少字段校验）。这些问题直接影响农民用户的核心体验，必须在 MVP 阶段根治。

## What Changes

- **BREAKING**: 所有 Agent system prompt 从代码抽离到 `prompts/` 目录，改用 Jinja2 模板 + YAML 配置
- Prompt 注册表支持版本管理，可在线切换活跃版本
- System Prompt 重构：语言规则置顶并标注"最高优先级"，时间信息通过模板变量注入
- 输出层新增英文句子检测拦截，与现有 PII 过滤合并为统一输出审核
- Guardrails 拦截记录写入数据库，供 admin-web 展示
- 记账解析接口增加 Pydantic 输出校验、幂等键去重、事务回滚保护
- 时间校准：客户端注入 `current_date` + Schema 范围校验（拒绝 < 2020 或 > 明天）

## Capabilities

### New Capabilities
- `prompt-template-management`: Prompt 模板集中管理——Jinja2 渲染、YAML 配置、版本注册表、热加载
- `output-language-guard`: 输出语言审核——英文句子检测拦截、Guardrails 拦截记录持久化
- `time-calibration`: 时间自动校准——客户端日期注入、Schema 日期范围校验、默认今天策略
- `create-operation-resilience`: 创建操作兜底——Pydantic 输出校验、幂等键去重、事务保护

### Modified Capabilities
- `user-settings`: 新增用户级 Prompt 版本偏好字段（预留，MVP 阶段后端支持即可）

## Impact

- **后端 Agent**: `graph.py`、`report.py` 移除硬编码 prompt，改为从注册表获取
- **后端 API**: `api/cost.py` `/parse` 接口增加幂等键和输出校验
- **后端 Schema**: `schemas/cost.py` 增加日期范围校验器
- **后端新增目录**: `prompts/`（模板文件）、新增 `core/prompt_registry.py`
- **后端数据库**: 新增 `guardrails_logs` 表（拦截记录）
- **前端移动端**: 请求时注入 `X-Current-Date` 请求头
- **前端 Admin-web**: 新增"语言拦截日志"和"Prompt 版本管理"两个视图（在 admin-web-ops change 中实现）
