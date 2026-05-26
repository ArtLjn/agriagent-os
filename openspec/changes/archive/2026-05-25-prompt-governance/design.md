## Context

当前 Agent 系统的提示词以硬编码 Python 字符串分散在 `graph.py`、`report.py`、`api/cost.py`、`services/agent_service.py` 四个文件中。这种设计在 MVP 早期阶段快速迭代时有效，但现在暴露出三个阻碍生产化的问题：

1. **语言漂移**：同一指令 "使用中文回答" 重复出现在多处，但都放在 system prompt 末尾，容易被后续内容冲淡，导致 LLM 偶发输出英文单词
2. **时间幻觉**：记账解析 prompt 未注入当前日期，LLM 只能凭训练数据猜测，导致日期默认错误（如 2023 年）
3. **创建脆弱**：`cost.py` `/parse` 接口直接信任 LLM 输出的 JSON，无 Schema 校验、无幂等保护、无事务回滚，偶发创建失败或脏数据

系统约束：2h2g 服务器、SQLite 数据库、3-4 个农户用户、OpenAI API 调用。

## Goals / Non-Goals

**Goals:**
- 所有 Agent prompt 集中到 `prompts/` 目录，支持热加载（无需重启服务）
- System Prompt 重构：语言规则置顶为"最高优先级"，消除英文输出
- 客户端注入当前日期，后端 Schema 范围校验，记账日期 100% 准确
- 创建类操作具备 Pydantic 校验 + 幂等键 + 事务保护，零失败
- Guardrails 拦截记录持久化到数据库，为 admin-web 监控提供数据源

**Non-Goals:**
- 多语言支持（MVP 只做中文）
- Prompt A/B 测试框架（只支持版本切换，不做流量分配）
- 自动 Prompt 优化（Auto-Prompt）
- 英文自动翻译（检测拦截即可，不调用翻译 API）
- RAG / 知识库（农业知识继续写死在 prompt 里）
- 移动端 UI 改动（只改请求头注入）

## Decisions

### Decision 1: Jinja2 + YAML 作为 Prompt 管理方案

**选择**: 使用 Jinja2 模板引擎 + YAML 配置文件管理 prompt，替代硬编码字符串。

**理由**:
- Jinja2 是 Python 生态标准模板引擎，项目已依赖 Python，无额外安装成本
- 支持变量注入（`{{ current_date }}`）、条件判断、循环，满足时间校准和动态内容需求
- YAML 人类可读，运维人员可直接编辑

**替代方案**: 数据库存储 prompt。拒绝理由：增加写操作和缓存复杂度，2h2g 场景下文件系统更轻量。

### Decision 2: Prompt 版本注册表（内存 + 文件）

**选择**: 内存中的 `PromptRegistry` 类，启动时从 `prompts/` 目录加载，提供 `get(name, version)` 接口。

**理由**:
- 简单，无外部依赖
- 支持热加载：编辑文件后调用 registry.reload() 即可生效
- MVP 阶段不需要数据库持久化版本历史

**替代方案**: Redis / 数据库版本表。拒绝理由：过度设计，MVP 阶段 prompt 变更频率低，文件系统足够。

### Decision 3: 三层防英文机制

**选择**: System Prompt 强约束（第一层）+ 输出层正则检测（第二层）+ Guardrails 拦截日志（第三层）。

**架构**:
```
用户输入 → Guardrails 输入检测 → LLM 调用 → 输出文本
                                          ↓
                                    filter_output()
                                          ↓
                                    ┌─────────────┐
                                    │ PII 过滤    │  （已有）
                                    │ 英文检测    │  （新增）
                                    └─────────────┘
                                          ↓
                                    返回用户 / 拦截告警
```

**英文检测策略**: 正则匹配连续 3+ 个英文单词。命中时不自动翻译，而是记录拦截日志并返回预设中文提示（"系统异常，请重试"），避免引入翻译 API 的复杂性和成本。

### Decision 4: 时间校准 — 客户端注入 + 后端校验

**选择**: 移动端在每个 HTTP 请求头注入 `X-Current-Date: 2026-05-25`，后端读取后注入 prompt 模板变量，同时对 LLM 输出做范围校验。

**理由**:
- 客户端时间比服务端推断更可靠（服务端不知道用户时区）
- 双层保险：prompt 告知"今天是 X" + Schema 拒绝越界日期
- 支持"昨天"、"3 天前"等相对日期（LLM 基于注入的当前日期推算）

**范围校验规则**:
- `record_date` 必须 ≥ 2020-01-01（农业记录不会更早）
- `record_date` 必须 ≤ 当前日期 + 1 天（允许明天预录入）
- 不满足时自动替换为今天

### Decision 5: 创建操作兜底 — Pydantic 校验 + 幂等键

**选择**: `cost.py` `/parse` 接口在现有 JSON 解析后增加 Pydantic `CostParseResult` 模型校验，客户端生成 `idempotency_key` 放请求头，服务端用 SQLite 唯一索引去重。

**理由**:
- Pydantic 已在项目中使用（schemas），无新依赖
- 幂等键是 HTTP 标准做法（Stripe/AWS 均采用）
- SQLite 唯一索引轻量且可靠

**幂等键存储**:
```sql
CREATE TABLE idempotency_keys (
    key TEXT PRIMARY KEY,
    response TEXT NOT NULL,  -- JSON 序列化的 CostParseResponse
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
-- 自动清理 24 小时前的记录
```

### Decision 6: Guardrails 拦截日志表

**选择**: 新增 `guardrails_logs` 表，记录每次输入/输出拦截的详细信息。

**Schema**:
```sql
CREATE TABLE guardrails_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farm_id INTEGER NOT NULL,
    trigger_type TEXT NOT NULL,  -- 'input_injection', 'input_sensitive', 'output_english', 'output_pii'
    trigger_detail TEXT,
    source_text TEXT,  -- 被拦截的原文（脱敏后）
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|---------|
| Jinja2 模板语法错误导致服务启动失败 | 启动时验证所有模板，错误时回退到内置默认 prompt |
| 英文检测正则误伤（如英文品种名"Watermelon"） | 白名单机制：农业术语表中的英文单词放行 |
| 客户端时间被篡改（用户手机时间错误） | 后端用 NTP 时间做软校验，偏差 > 7 天时使用服务端时间 |
| 幂等键表无限增长 | Celery/定时任务清理 24h 前记录；MVP 阶段用 SQLite 事件或启动时清理 |
| Prompt 热加载并发安全 | 注册表操作加 threading.RLock，读取无锁 |

## Migration Plan

1. **创建 `prompts/` 目录和模板文件**（零停机）
2. **新增数据库表** `guardrails_logs`、`idempotency_keys`（Alembic 迁移或手动 SQL）
3. **部署后端**：新代码兼容旧硬编码 prompt（fallback 机制），验证无问题后删除旧代码
4. **更新移动端**：发版注入 `X-Current-Date` 请求头
5. **Admin-web**：在后续 `admin-web-ops` change 中消费 `guardrails_logs` 数据

**Rollback**: 若新 prompt 系统异常，registry 自动回退到代码内置的默认 prompt。

## 借鉴设计（product-agent 参考）

以下设计来自思必驰产品级 Agent 项目（`~/Desktop/aispeech/product-agent`），经评估可直接融入本 change，不增加额外依赖。

### 借鉴 1: Prompt 动态拼装模式

**参考代码**:
- `~/Desktop/aispeech/product-agent/src/prompts/system_prompt.py:66-88` — `build_system_prompt()` 动态替换占位符
- `~/Desktop/aispeech/product-agent/src/prompts/master.md` — 基础模板含 `{{PERSONA}}`、`{{CAPABILITIES}}` 占位符

**他们的做法**:
```python
# system_prompt.py
def build_system_prompt(ctx: AgentContext) -> str:
    version = get_prompt_version()  # 从 config.yaml 读取
    master_prompt = load_file(f"master_{version}.md")

    prompt = master_prompt
    if "{{PERSONA}}" in prompt:
        prompt = prompt.replace("{{PERSONA}}", _get_persona_prompt(ctx.persona))
    if "{{ENV_INFO}}" in prompt:
        prompt = prompt.replace("{{ENV_INFO}}", _get_env_info(ctx))
    if "{{CAPABILITIES}}" in prompt:
        prompt = prompt.replace("{{CAPABILITIES}}", _get_capabilities_section(ctx))
    return prompt
```

**我们的应用**:
将现有硬编码 `SYSTEM_PROMPT` 拆分为 `base.j2` + `role.j2` + `skills.j2`，通过 `render_prompt()` 注入变量后拼接。语言规则放在 `base.j2` 最顶部，确保最高优先级。

### 借鉴 2: micro_compact 上下文压缩

**参考代码**:
- `~/Desktop/aispeech/product-agent/src/tools/compact.py:30-50` — `micro_compact()` 方法

**他们的做法**:
```python
# compact.py
KEEP_RECENT = 5

def micro_compact(self, messages):
    tool_results = [(i, msg) for i, msg in enumerate(messages)
                    if msg.get("role") == "tool"]
    if len(tool_results) <= self.KEEP_RECENT:
        return messages

    # 旧的 tool result 替换成占位符
    for idx, (i, msg) in enumerate(tool_results[:-self.KEEP_RECENT]):
        content = msg.get("content", "")
        if len(content) > 100:
            tool_name = msg.get("name", "unknown")
            messages[i] = {**msg, "content": f"[已执行 {tool_name}]"}
    return messages
```

**我们的应用**:
在 `graph.py` 的 `_llm_node()` 调用前增加 `micro_compact(messages)`，只保留最近 3 个完整 tool result，旧的替换为 `[已执行 {skill_name}]` 占位符。防止长对话导致 token 爆炸。

### 借鉴 3: JSON 自动修复

**参考代码**:
- `~/Desktop/aispeech/product-agent/src/tools/todo.py:45-80` — `_repair_json()` 方法

**他们的做法**:
```python
# todo.py
def _repair_json(self, json_str: str) -> str:
    s = json_str.strip()
    open_braces = s.count('{')
    close_braces = s.count('}')
    missing_braces = open_braces - close_braces

    # 补全缺失的括号
    if missing_braces > 0:
        s += '}' * missing_braces

    # 移除末尾多余逗号
    s = re.sub(r',\s*([}\]])', r'\1', s)
    return s
```

**我们的应用**:
在 `api/cost.py` `/parse` 接口的 JSON 解析流程中，加入 `_repair_json()` 步骤。在 `json.loads()` 失败时先尝试修复，再重试解析。提高 LLM 输出容错率。

### 借鉴 4: 工具注册表模式

**参考代码**:
- `~/Desktop/aispeech/product-agent/src/agent/agent_context.py:75-95` — `ExecutionState.toolbox` 工具箱
- `~/Desktop/aispeech/product-agent/src/agent/core.py:55-58` — 主 Agent 工具注册

**他们的做法**:
```python
# agent_context.py
class ExecutionState:
    toolbox: dict[str, str] = field(default_factory=dict)  # original_name -> full_name

    def add_tool(self, original_name: str, full_name: str):
        self.toolbox[original_name] = full_name

    def get_tool_full_name(self, original_name: str) -> str | None:
        return self.toolbox.get(original_name)
```

**我们的应用**:
当前 `get_langchain_tools()` 每次调用都重新实例化所有 Skill。改为启动时注册到全局 `SkillRegistry`，运行时直接查表。减少重复初始化开销。

### 借鉴 5: 埋点监控设计

**参考代码**:
- `~/Desktop/aispeech/product-agent/src/monitoring/trace_collector.py:40-80` — `record()` 方法

**他们的做法**:
```python
# trace_collector.py
async def record(self, node_type, node_name, input_data, output_data,
                 start_time, end_time, error_message):
    trace = get_trace()
    self._output_logbus(trace, node_type, node_name, ...)
    # node_type: llm_call / tool_call / http_call / mongo_call / redis_call
```

**我们的应用**:
扩展现有的 `guardrails_logs`，增加 `agent_traces` 表记录 LLM 调用和 Tool 调用的耗时、token 消耗、入出参摘要。admin-web 用这些数据展示 Agent 决策链路。结构：
```sql
CREATE TABLE agent_traces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farm_id INTEGER NOT NULL,
    session_id TEXT,
    node_type TEXT NOT NULL,  -- 'llm_call', 'tool_call'
    node_name TEXT,
    input_summary TEXT,
    output_summary TEXT,
    duration_ms INTEGER,
    tokens_used INTEGER,
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

## Open Questions

1. 农业英文术语白名单需要包含多少词条？（MVP 阶段先人工维护一个小列表）
2. 移动端 `X-Current-Date` 用设备本地时间还是网络时间？（建议本地时间，偏差大时后端兜底）
3. Guardrails 日志保留多久？（建议 30 天，admin-web 展示最近 7 天）
