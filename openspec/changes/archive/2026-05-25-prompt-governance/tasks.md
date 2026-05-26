## 1. Prompt 模板基础设施

- [ ] 1.1 创建 `prompts/` 目录结构，添加 `__init__.py`
- [ ] 1.2 创建 `prompts/base.j2` — 包含语言规则置顶的 system prompt 模板
- [ ] 1.3 创建 `prompts/cost_parse.j2` — 记账解析模板（注入 current_date + 时间规则）
- [ ] 1.4 创建 `prompts/report.j2` — 报告生成模板
- [ ] 1.5 创建 `prompts/config.yaml` — 模板元数据配置（版本映射、默认变量）
- [ ] 1.6 实现 `app/core/prompt_registry.py` — PromptRegistry 类（注册/获取/切换/热加载）
- [ ] 1.7 实现 `app/core/prompt_renderer.py` — render_prompt() 函数（Jinja2 + 内置变量注入）
- [ ] 1.8 服务启动时自动加载 `prompts/` 目录到 registry
- [ ] 1.9 模板语法错误时回退到内置默认 prompt

## 2. 后端 Agent Prompt 迁移

- [ ] 2.1 修改 `app/agents/graph.py` — 移除硬编码 SYSTEM_PROMPT，改为 `registry.get("system_base")`
- [ ] 2.2 修改 `app/agents/report.py` — 移除硬编码 REPORT_SYSTEM_PROMPT，改用模板渲染
- [ ] 2.3 修改 `app/services/agent_service.py` — 移除硬编码 prompt，改用模板
- [ ] 2.4 修改 `app/api/cost.py` — `/parse` 接口 prompt 改用 `prompts/cost_parse.j2`
- [ ] 2.5 确保所有 `render_prompt()` 调用注入 `current_date`、`current_time`、`current_weekday`

## 3. 时间校准

- [ ] 3.1 修改移动端 API client — 每个请求注入 `X-Current-Date` 请求头
- [ ] 3.2 后端中间件读取 `X-Current-Date`，存放到请求上下文
- [ ] 3.3 后端兜底逻辑：缺失请求头时使用服务端时间；偏差 > 7 天使用服务端时间
- [ ] 3.4 `schemas/cost.py` 增加 `record_date` 范围校验器（≥2020-01-01，≤今天+1天）
- [ ] 3.5 记账解析接口：日期越界时自动替换为今天，并记录日志

## 4. 防英文机制

- [ ] 4.1 重构 `app/core/guardrails.py` — 在 `filter_output()` 中增加英文句子检测（正则：连续 3+ 英文单词）
- [ ] 4.2 创建 `app/core/term_whitelist.py` — 农业术语英文白名单（Watermelon 等）
- [ ] 4.3 英文检测命中时返回预设中文提示 "系统异常，请重试"
- [ ] 4.4 重构 system prompt：语言规则置顶，标注 "【语言规则】（最高优先级）"
- [ ] 4.5 所有模板中的 "使用中文回答" 统一改为强约束措辞

## 5. Guardrails 拦截日志

- [ ] 5.1 数据库迁移：创建 `guardrails_logs` 表（id, farm_id, trigger_type, trigger_detail, source_text, created_at）
- [ ] 5.2 修改 `guardrails.py` — `check_input()` 拦截时写入 guardrails_logs
- [ ] 5.3 修改 `guardrails.py` — `filter_output()` 英文/PII 拦截时写入 guardrails_logs
- [ ] 5.4 新增 `app/api/admin.py` — `/admin/guardrails-logs` 查询接口（支持分页、按类型过滤）
- [ ] 5.5 定时清理：启动时删除 30 天前的 guardrails_logs 记录

## 6. 创建操作兜底

- [ ] 6.1 数据库迁移：创建 `idempotency_keys` 表（key PRIMARY KEY, response TEXT, created_at）
- [ ] 6.2 `schemas/cost.py` 新增 `CostParseResult` Pydantic 模型（带校验规则）
- [ ] 6.3 修改 `api/cost.py` `/parse` — 增加 Pydantic 输出校验（非法值用默认值替换）
- [ ] 6.4 修改 `api/cost.py` `/parse` — 读取 `X-Idempotency-Key` 请求头
- [ ] 6.5 实现幂等逻辑：先查 idempotency_keys，命中则直接返回缓存
- [ ] 6.6 幂等缓存写入：解析成功后缓存结果到 idempotency_keys
- [ ] 6.7 启动时清理 24 小时前的 idempotency_keys 记录
- [ ] 6.8 移动端 API client — 发送 `/parse` 请求时携带 `X-Idempotency-Key`（UUID v4）

## 7. JSON 解析容错

- [ ] 7.1 提取 `api/cost.py` 中的 JSON 解析逻辑到独立函数
- [ ] 7.2 支持自动提取 Markdown ```json 代码块内容
- [ ] 7.3 JSON 解析失败时返回 422，附带原文前 100 字符用于调试

## 8. 事务回滚保护

- [ ] 8.1 审查 `cost_service.py` — 所有写操作确保有 try/except/rollback
- [ ] 8.2 审查 `agent_service.py` — 所有写操作确保有 try/except/rollback
- [ ] 8.3 统一异常处理：创建失败时返回含 code 字段的结构化错误

## 9. 测试

- [ ] 9.1 单元测试：`prompt_registry.py` — 注册/获取/切换/热加载
- [ ] 9.2 单元测试：`prompt_renderer.py` — 变量注入、模板渲染
- [ ] 9.3 单元测试：`guardrails.py` — 英文检测（命中/白名单/正常中文）
- [ ] 9.4 单元测试：日期范围校验器（正常/过早/过晚/空值）
- [ ] 9.5 单元测试：幂等键逻辑（首次/重复/过期）
- [ ] 9.6 集成测试：完整记账解析流程（含 LLM mock）
- [ ] 9.7 集成测试：模板语法错误时回退到默认 prompt

## 10. 借鉴设计实现（product-agent 参考）

- [ ] 10.1 Prompt 动态拼装 — 拆分 `base.j2` + `role.j2` + `skills.j2`，`render_prompt()` 注入变量后拼接（参考: `~/Desktop/aispeech/product-agent/src/prompts/system_prompt.py:66-88` + `master.md`）
- [ ] 10.2 micro_compact 上下文压缩 — `_llm_node()` 调用前保留最近 3 个完整 tool result，旧的替换为 `[已执行 {skill_name}]` 占位符（参考: `~/Desktop/aispeech/product-agent/src/tools/compact.py:30-50`）
- [ ] 10.3 JSON 自动修复 — `api/cost.py` 解析流程加入 `_repair_json()`，补全括号 + 删除末尾多余逗号（参考: `~/Desktop/aispeech/product-agent/src/tools/todo.py:45-80`）
- [ ] 10.4 工具注册表 — 启动时注册 Skill 到全局 `SkillRegistry`，运行时直接查表，避免重复实例化（参考: `~/Desktop/aispeech/product-agent/src/agent/agent_context.py:75-95`）
- [ ] 10.5 埋点监控 — 新增 `agent_traces` 表，记录 LLM/Tool 调用耗时、token、入出参摘要（参考: `~/Desktop/aispeech/product-agent/src/monitoring/trace_collector.py:40-80`）

## 11. 集成与验证

- [ ] 11.1 本地启动后端，验证所有模板正确加载
- [ ] 11.2 移动端连接本地后端，测试记账 20 次（日期准确率）
- [ ] 11.3 移动端连接本地后端，测试 AI 聊天 20 次（中文准确率）
- [ ] 11.4 验证 Guardrails 日志正确写入数据库
- [ ] 11.5 验证 idempotency_keys 去重生效
- [ ] 11.6 验证 micro_compact 压缩后 token 减少
- [ ] 11.7 验证 JSON 修复提高解析成功率
- [ ] 11.8 2h2g 服务器部署验证（内存占用 < 500MB）
- [ ] 11.9 ruff check + ruff format 通过
