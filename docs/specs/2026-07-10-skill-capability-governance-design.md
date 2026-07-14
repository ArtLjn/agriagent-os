# Skill Capability Governance Design

## 背景

当前农业 AI Agent 的 Skill 已增长到 30 个以上，`backend/app/agent/skills/`
中同时存在 CRUD/API 粒度 Skill 和业务能力粒度 Skill。例如财务领域有
`create_cost_record`、`delete_cost_record`、`get_cost_summary`、
`get_cost_analytics`、`get_debt_summary`、`settle_debt`，而工人领域已经有
较接近能力粒度的 `manage_workers`。

这种混合状态带来几个问题：

- Tool Selection 面对大量相近工具时容易误选。
- Skill 名称混用 `create_*`、`get_*`、`delete_*`、`manage_*`，用户意图和工具名不稳定对应。
- Skill 文档和 Router Registry 中的意图、风险、上下文依赖存在重复维护。
- 后续扩展到 100+ Skill 时，不能依赖一次性暴露全部工具或按目录扫描判断能力边界。

本设计目标是把 Agent 从“一个 API 一个 Skill”演进为“一个业务能力一个
Skill”，并在保持旧 Skill 兼容的前提下建立可长期维护的 Registry、Router、
Retrieval 和治理体系。

## 设计原则

1. Business Capability 优先。Skill 代表用户能完成的一类业务能力，不代表单个 API。
2. Registry 是唯一事实源。目录只承载实现，运行时能力、路由、检索、兼容关系都从 Registry 加载。
3. 旧 Skill 先兼容再下线。历史 tool name、pending action、trace replay 和测试不被一次性破坏。
4. 风险声明到 operation。一个能力 Skill 可以包含读、写、删除、结算等 operation，每个 operation 独立声明风险和确认策略。
5. Router 做收敛和保护，不做业务词库堆叠。常见表达通过 Registry examples、anti_examples、tags 和评测集治理。
6. 渐进式披露。Root Router 先选 domain，再做 Skill Retrieval Top-K，最后只向 LLM 暴露少量候选工具。

## 推荐方案

采用 Registry-first 迁移方案：

```text
User
  -> Intent Router
  -> Domain Router
  -> Skill Registry
  -> Skill Retrieval Top-K
  -> Policy Guard
  -> LLM Tool Selection
  -> Capability Skill
  -> Operation Adapter
  -> Service/API
```

不先做大规模目录搬迁，也不直接删除旧 CRUD Skill。第一阶段先引入统一
`skills.yaml` 和 alias 映射，让 Router 和 Prompt Builder 从 Registry 读取能力定义。
旧目录按能力稳定性逐步收敛；成本分类查询/管理已完成物理合并，只保留
`manage_cost_categories` 目录，旧 `get_cost_categories` 通过 registry alias
映射到 `manage_cost_categories.query_categories`。

## 新 Skill 分类方案

| Domain | Capability Skill | 业务范围 |
| --- | --- | --- |
| finance | `manage_cost` | 记账、查账、删除账务、赊账、还款、债务查询 |
| finance | `analyze_cost` | 收支趋势、同比、环比、成本分析 |
| finance | `manage_cost_categories` | 成本和收入分类查询、创建、删除 |
| crop | `manage_crop_cycle` | 茬口创建、查询、调整、阶段更新、高风险删除 |
| crop | `manage_crop_template` | 作物模板查询、创建、更新、删除、系统模板导入 |
| farm | `manage_planting_units` | 棚、地块、区域等种植单元查询和管理 |
| farm | `get_farm_status` | 农场综合状态聚合查询 |
| operation | `manage_work_orders` | 农事作业单创建、查询、纠正、用工付款信息维护 |
| labor | `manage_workers` | 工人档案查询、创建、更新、停用、恢复 |
| labor | `manage_labor_payment` | 未付人工查询、工资记录、人工结算 |
| log | `manage_farm_logs` | 农事日志记录、查询、编辑、删除 |
| settings | `manage_settings` | 用户显示名、天气城市、经纬度、助手角色设置 |
| external | `get_weather_forecast` | 天气预报和灾害预警 |
| external | `web_search` | 外部实时政策、价格、新闻和市场信息 |

## Skill 合并清单

| 新能力 Skill | 合并旧 Skill |
| --- | --- |
| `manage_cost` | `create_cost_record`、`delete_cost_record`、`get_cost_summary`、`get_debt_summary`、`settle_debt` |
| `analyze_cost` | `get_cost_analytics` |
| `manage_cost_categories` | `get_cost_categories`（alias）、`manage_cost_categories` |
| `manage_crop_cycle` | `create_crop_cycle`、`get_crop_cycles`、`get_crop_cycle_info`、`update_crop_cycle`、`update_crop_stage`（legacy alias）、`delete_crop_cycle` |
| `manage_crop_template` | `create_crop_template`、`get_crop_templates`、`manage_crop_templates` |
| `manage_planting_units` | `get_planting_units`、`manage_planting_units` |
| `manage_work_orders` | `create_operation_work_order`、`get_operation_work_orders`、`update_operation_work_order` |
| `manage_workers` | `get_workers`、`manage_workers` |
| `manage_labor_payment` | `get_labor_payables`、`settle_labor_payment`、`manage_wages` |
| `manage_farm_logs` | `log_farm_activity`、`get_recent_farm_logs`、`manage_farm_logs` |
| `manage_settings` | `get_user_settings`、`manage_user_settings` |

`get_weather_forecast` 和 `web_search` 暂不合并，因为它们是外部网络能力，权限、缓存、失败策略和稳定性边界独立。

## 新目录结构

目标目录结构：

```text
backend/app/agent/skills/
  registry/
    skills.yaml
    aliases.yaml
    domains.yaml

  capabilities/
    finance/
      manage_cost/
        skill.md
        schema.py
        handler.py
        operations.py
      analyze_cost/
      manage_cost_categories/
    crop/
      manage_crop_cycle/
      manage_crop_template/
    farm/
      manage_planting_units/
      get_farm_status/
    operation/
      manage_work_orders/
    labor/
      manage_workers/
      manage_labor_payment/
    log/
      manage_farm_logs/
    settings/
      manage_settings/
    external/
      get_weather_forecast/
      web_search/

  legacy/
    create-cost-record/
    delete-cost-record/
    # 其他旧 CRUD/API 粒度 Skill 保留原名，直到 alias 使用量和回归指标达标后再下线。
```

迁移早期可以不移动旧目录，只新增 `registry/`，并让 `aliases.yaml` 指向现有旧实现。
目录搬迁必须晚于 Registry、Router、评测和 pending action 兼容完成。

## Metadata 设计

每个 Capability Skill 必须声明统一 metadata：

```yaml
name: manage_cost
domain: finance
capability: cost_management
description: 管理农场账务，支持新增、查询、删除、赊账和还款。
examples:
  - 今天买了100元化肥
  - 删除昨天那笔支出
  - 这个月花了多少钱
  - 把老王农资店的账结清
anti_examples:
  - 给老王补付300人工
  - 查询作业单
tags:
  - 成本
  - 支出
  - 收入
  - 赊账
  - 农资
  - 化肥
version: v2
owner: agent-platform
status: active
context_dependencies:
  - farm
  - cost_records
  - cost_categories
cache_invalidation:
  - cost_records
  - cost_summary
  - debt_summary
operations:
  create_record:
    risk: write_confirm
    legacy_aliases:
      - create_cost_record
  query_summary:
    risk: read
    legacy_aliases:
      - get_cost_summary
      - get_debt_summary
  delete_record:
    risk: write_high
    legacy_aliases:
      - delete_cost_record
  settle_debt:
    risk: write_confirm
    legacy_aliases:
      - settle_debt
```

Metadata 字段约束：

| 字段 | 要求 |
| --- | --- |
| `name` | snake_case，采用 `verb_object` |
| `domain` | 必须来自 `domains.yaml` |
| `capability` | 稳定能力 ID，用于评测和治理 |
| `description` | 描述用户意图，不描述 API |
| `examples` | 至少 5 条正例，覆盖高频表达 |
| `anti_examples` | 至少 5 条反例，覆盖易误选表达 |
| `tags` | 中文业务词、实体词、同义词 |
| `operations` | 每个 operation 独立声明风险、别名、确认策略 |
| `owner` | 负责团队或模块 |
| `status` | `active`、`deprecated`、`hidden`、`removed` |

## Registry 设计

Registry 由三个文件组成：

```text
skills.yaml   # 业务能力定义
aliases.yaml  # 旧 tool name 到新 capability/operation 的映射
domains.yaml  # domain、owner、默认上下文、默认风险策略
```

Loader 负责生成四类运行时对象：

- `SkillCatalog`：供 Router 和 Retriever 使用。
- `ToolSchema`：供 LLM tool binding 使用。
- `LegacyAliasMap`：兼容旧 tool name、pending action、trace replay。
- `GovernanceReport`：检查 metadata 完整性、命名、重复能力和风险声明。

Registry 不依赖目录名判断 Skill 能力。目录移动、实现拆分和 handler 重构不应影响对外能力名。

## Router 与 Skill Retrieval 架构

路由分四层：

```text
Root Router
  -> Domain Shortlist
  -> Skill Retrieval
  -> Policy Guard
  -> Tool Binding
```

### Root Router

识别输入是否需要工具、是否为写意图、是否包含多意图、是否需要外部网络。
闲聊、解释类和无数据查询类请求可以不绑定工具。

### Domain Shortlist

基于 Registry 中的 domain、tags、examples、entities 选出 1 到 3 个候选 domain。
例如“今天买了100元化肥”进入 `finance`，“西瓜进膨大期了”进入 `crop`。

### Skill Retrieval

在候选 domain 内做 Top-K：

- 第一阶段使用 Registry lexical match：examples、anti_examples、tags、entities。
- 第二阶段可接入 embedding retrieval。
- Retrieval 返回 capability，不返回旧 CRUD tool。

默认预算：

| 场景 | 工具数量上限 |
| --- | --- |
| 普通读请求 | 1 到 2 |
| 复杂读请求 | 最多 5 |
| 写请求 | 1 个写能力 Skill，加必要读上下文 |
| 不确定写请求 | 不绑定写工具，先澄清 |
| 最终回复轮 | 默认不重新绑定工具 |

### Policy Guard

Policy Guard 在绑定工具前执行：

- 禁止 fallback all。
- 禁止读意图暴露写 operation。
- 写 operation 必须进入确认链路。
- `write_high` 必须展示影响范围并二次确认。
- disabled Skill 不进入候选。
- schema token 超预算时裁剪或澄清。
- 多意图写操作生成 pending plan，不覆盖上一条 pending action。

## Skill 路由选择设计

现有 `SkillRouter` 已经具备规则意图帧、候选工具裁剪和 schema token 预算能力。
本次重构不推翻这条链路，而是把“规则写死到 Python”升级为“Registry 驱动的可解释选择”。
路由输出必须能回答三个问题：

1. 为什么选择这个 domain。
2. 为什么选择这个 capability。
3. 为什么选择这个 operation，或为什么交给 LLM 在候选 operation 中选择。

### 路由输入

Router 每轮接收：

```json
{
  "message": "今天买了100元化肥",
  "session_context": {
    "pending_plan": null,
    "recent_tool_results": [],
    "conversation_summary": ""
  },
  "available_capabilities": ["manage_cost", "manage_crop_cycle"],
  "runtime_flags": {
    "external_network_enabled": false,
    "write_enabled": true
  }
}
```

`available_capabilities` 来自 Registry Loader，而不是目录扫描结果。旧工具名通过
`LegacyAliasMap` 解析成 capability 和 operation。

### IntentFrame 抽取

Root Router 先把用户输入拆成一个或多个 `IntentFrame`：

```yaml
domain_hint: finance
intent_type: write
risk_hint: write_confirm
entities:
  amount: 100
  item: 化肥
  date: today
action_hint: create_record
confidence: 0.86
evidence:
  matched_examples:
    - 今天买了100元化肥
  matched_tags:
    - 化肥
    - 支出
```

IntentFrame 只做轻量抽取，不直接等同最终工具选择。它的职责是给后续检索提供
domain、risk、entity 和 action 线索。

### Domain 选择

Domain 选择采用可解释打分：

| 信号 | 分值 | 说明 |
| --- | --- | --- |
| 正例相似度 | 0 到 0.35 | 与 `examples` 的 lexical 或 embedding 相似度 |
| tag 命中 | 0 到 0.20 | 命中 domain 或 capability tags |
| entity 命中 | 0 到 0.20 | 金额、作物、工人、地块、日期等实体类型 |
| operation 动词命中 | 0 到 0.15 | 新增、查询、修改、删除、结算、分析 |
| 上下文延续 | 0 到 0.10 | pending plan、上一轮查询结果、用户追问 |
| 反例惩罚 | -0.30 到 0 | 命中 `anti_examples` 或冲突 domain |

选择规则：

- `domain_score >= 0.65`：进入 domain shortlist。
- 最高分和次高分差值 `< 0.12`：保留两个 domain，交给 capability retrieval 继续裁决。
- 所有 domain 都 `< 0.45`：不绑定工具，除非是明确只读查询，可进入只读安全候选池。
- 写意图 domain 不确定时，不绑定写能力，返回澄清问题。

示例：

| 输入 | domain shortlist | 理由 |
| --- | --- | --- |
| 今天买了100元化肥 | `finance` | 金额 + 化肥 + 买了，命中成本记录正例 |
| 西瓜进膨大期了 | `crop` | 作物 + 阶段变化，命中茬口阶段更新 |
| 给老王补付300人工 | `labor`、`finance` | 金额和支付命中 finance，人工/工人命中 labor，后续由 operation 风险裁决 |

### Capability Retrieval

在 domain shortlist 内检索 capability。每个候选 capability 计算：

```text
capability_score =
  0.30 * example_similarity
  + 0.20 * tag_score
  + 0.20 * entity_score
  + 0.15 * operation_fit
  + 0.10 * context_fit
  + 0.05 * historical_success
  - anti_example_penalty
```

字段来源：

| 信号 | Registry 字段 |
| --- | --- |
| `example_similarity` | `examples` |
| `anti_example_penalty` | `anti_examples` |
| `tag_score` | `tags` |
| `entity_score` | `entities` 或 operation schema |
| `operation_fit` | `operations.*.verbs`、`operations.*.examples` |
| `context_fit` | `context_dependencies` 与会话上下文 |
| `historical_success` | eval/trace 聚合指标，第一阶段可置 0 |

选择规则：

- Top-1 `capability_score >= 0.70` 且领先 Top-2 `>= 0.12`：直接选择 Top-1。
- Top-1 `0.55 到 0.70`：保留 Top-2 或 Top-3 给 LLM tool selection。
- Top-1 `< 0.55`：不绑定工具或进入只读安全候选池。
- 命中强反例时，即使正例分高也要降权或拒绝。

Capability Retrieval 返回结构：

```yaml
candidates:
  - capability: manage_cost
    score: 0.88
    candidate_operations:
      - create_record
    evidence:
      examples: ["今天买了100元化肥"]
      tags: ["化肥", "支出"]
      entities: ["amount", "cost_item"]
  - capability: manage_labor_payment
    score: 0.31
    rejected_reason: "未命中人工、工资或工人结算实体"
```

### Operation 选择

Capability Skill 内部 operation 通过 action、risk、schema 和上下文选择。
operation 选择发生在 tool binding 之前，用于决定是否需要确认、是否需要澄清、
是否可以缩小给 LLM 的 schema。

| 用户意图 | capability | operation | 风险 |
| --- | --- | --- | --- |
| 今天买了100元化肥 | `manage_cost` | `create_record` | `write_confirm` |
| 这个月花了多少 | `manage_cost` | `query_summary` | `read` |
| 删除昨天那笔支出 | `manage_cost` | `delete_record` | `write_high` |
| 把老王的账结清 | `manage_cost` | `settle_debt` | `write_confirm` |
| 这个月比上个月多花多少 | `analyze_cost` | `compare_period` | `read` |

operation 选择规则：

- 明确写动词命中写 operation 时，只暴露该 capability，不暴露同 domain 其他写能力。
- 读 operation 和写 operation 同属一个 capability 时，Router 必须把 `operation_hint`
  写入 `RouterDecision`，避免 LLM 把查询误解成写入。
- 删除、级联删除、结清、批量支付等 operation 标记为 `write_high` 或带风险说明的 `write_confirm`。
- 缺少必填字段时不绑定写 operation，返回澄清；只读 operation 可以用默认时间范围，但必须记录默认值。

### 多意图选择

用户一句话可能包含多个业务动作，例如：

```text
招了一个工人王大妈工资100一天，早上让她去5号棚收水稻
```

Router 应拆成多个 frame：

```yaml
frames:
  - domain: labor
    capability: manage_workers
    operation: create_worker
    risk: write_confirm
    params_hint:
      name: 王大妈
      default_pay_type: daily
      default_unit_price: 100
  - domain: operation
    capability: manage_work_orders
    operation: create_work_order
    risk: write_confirm
    depends_on:
      - create_worker
    params_hint:
      workers: 王大妈
      unit_names: 5号棚
      operation_type: 采收
```

多意图策略：

- 多个读意图可以同时进入 Top-K，但总工具数不超过复杂请求预算。
- 多个写意图不直接绑定多个写工具，而是生成 pending plan。
- 后续 step 依赖前置 step 的新 ID 时，必须声明 `depends_on`。
- 任一步缺关键参数时，整个写入 plan 进入澄清，不执行部分写入。

### 歧义和冲突处理

| 场景 | 处理 |
| --- | --- |
| 读写冲突 | 优先识别是否有明确写动作；没有明确写动作时按读处理 |
| domain 冲突 | 保留 Top-2，只绑定只读能力；写能力必须澄清 |
| operation 冲突 | 让用户选择具体动作，例如“是新增账单还是还款？” |
| 高风险目标不唯一 | 展示候选目标，要求用户选择 |
| 外部网络禁用 | 不绑定 `web_search`，说明当前无法搜索实时外部信息 |
| pending action 存在 | 优先处理确认、取消、修改 pending action，再处理新请求 |

### RouterDecision 输出

目标 `RouterDecision` 需要从“工具列表”升级为“可解释选择结果”：

```yaml
frames:
  - domain: finance
    intent: create_cost_record
    risk: write_confirm
    capability: manage_cost
    operation: create_record
    confidence: 0.88
    params_hint:
      amount: 100
      category: 化肥
selected_tools:
  - manage_cost
selected_operations:
  manage_cost:
    - create_record
context_dependencies:
  - farm
  - cost_categories
tool_choice: auto
fallback: null
reason: 金额、化肥、买了命中 manage_cost.create_record
rejected_tools:
  - analyze_cost
policy_violations: []
schema_token_estimate: 620
```

Trace 中必须记录：

- domain score。
- capability score。
- operation score。
- 命中的 examples、tags、entities。
- 被拒绝候选和拒绝原因。
- fallback 或澄清原因。
- 最终暴露给 LLM 的 tool schema 数量和 token 估算。

### 第一阶段实现边界

第一阶段不要求立刻接入 embedding，也不要求 Router 完全替代 LLM tool selection。
优先完成：

1. Registry 中补齐 examples、anti_examples、tags、operations。
2. Router 基于 Registry 生成 domain 和 capability Top-K。
3. Policy Guard 严格禁止 fallback all 和读意图暴露写 operation。
4. Trace 记录可解释证据。
5. 建立 Router eval，用真实对话样本验证 Top-1、Top-3、误暴露率。

## 执行模型

Capability Skill 接收统一输入：

```json
{
  "operation": "create_record",
  "params": {
    "amount": 100,
    "category": "化肥",
    "record_type": "cost"
  },
  "original_input": "今天买了100元化肥"
}
```

内部由 operation adapter 转发到现有 service 或旧 Skill handler：

```text
manage_cost.create_record
  -> legacy adapter create_cost_record
  -> cost service
```

这样可以先统一对外能力名和 Router，再逐步重构内部实现。

## 兼容迁移方案

### Phase 0：冻结新增 CRUD Skill

新增能力必须先判断是否能并入现有 Capability Skill。确需新增时，必须先写 Registry 条目。

### Phase 1：Registry 引入

新增 `backend/app/agent/skills/registry/skills.yaml`、`aliases.yaml`、`domains.yaml`。
从现有 `backend/app/agent/router/registry.py` 和 `skill.md` 迁移 metadata。
这一阶段不改变工具执行逻辑。

### Phase 2：Router 读取 Registry

`SkillCatalog` 从 YAML Registry 构建，Python dict 只保留为兼容兜底。
Router trace 增加 capability、operation、legacy_alias、retrieval_score。

### Phase 3：低风险能力合并

优先合并读写边界清楚、影响小的能力：

- `manage_workers`
- `manage_settings`
- `manage_planting_units`
- `manage_cost_categories`

### Phase 4：高风险能力合并

再合并涉及删除、结算、级联影响的能力：

- `manage_cost`
- `manage_crop_cycle`
- `manage_crop_template`
- `manage_labor_payment`
- `manage_work_orders`

这些能力必须先补齐 pending plan、确认展示、回滚和 trace replay。

### Phase 5：旧 Skill 下线

旧 Skill 经历以下状态：

```text
active -> deprecated -> hidden -> removed
```

下线前必须满足：

- 生产 trace 中旧 alias 使用量低于阈值。
- Router eval 中 Top-1 和 Top-3 指标达标。
- pending action 和历史 trace replay 可通过 alias 解析。
- 对应旧 Skill 的正反例已迁移到新 capability。

## 改造文件边界

本节用于评估改造规模。边界原则是先让 Registry 和 Router 接管“选择与治理”，再逐步收敛
Skill 执行入口。第一阶段只做元数据、路由、兼容映射和测试，不重写业务服务。

### 第一阶段必须改造

| 文件或目录 | 改造内容 | 影响面 |
| --- | --- | --- |
| `backend/app/agent/skills/registry/skills.yaml` | 新增 Capability Skill 定义、examples、anti_examples、tags、operations、风险和上下文依赖 | 新增文件，Registry 事实源 |
| `backend/app/agent/skills/registry/aliases.yaml` | 新增旧 tool name 到 capability/operation 的映射 | 新增文件，兼容旧 Skill |
| `backend/app/agent/skills/registry/domains.yaml` | 新增 domain 枚举、owner、默认上下文和风险策略 | 新增文件，治理基础 |
| `backend/app/agent/router/models.py` | 扩展 `ToolCandidate`、`IntentFrame`、`RouterDecision`，加入 capability、operation、score、evidence、alias 信息 | Router trace 和 runtime 消费结构变化 |
| `backend/app/agent/router/catalog.py` | 从 YAML Registry 构建 catalog，保留现有 Python registry 作为兼容 fallback | Router 候选来源变化 |
| `backend/app/agent/router/registry.py` | 降级为兼容入口或迁移桥，避免继续维护静态大 dict | 旧逻辑兼容 |
| `backend/app/agent/router/service.py` | 编排 domain shortlist、capability retrieval、operation hint 和 policy | 核心路由决策 |
| `backend/app/agent/router/policy.py` | 按 capability/operation 风险执行预算、读写隔离、fallback 禁止、澄清策略 | 安全边界 |
| `backend/app/agent/router/classifier.py` | 第一阶段减少业务硬编码，只保留轻量 frame 抽取和兼容规则 | 降低词库污染 |
| `backend/app/agent/skills/metadata.py` | 让 runtime metadata 可从 Registry 补齐权限、风险、缓存失效和启停状态 | 工具执行权限 |
| `backend/app/agent/skills/__init__.py` | `get_langchain_tools()` 加载 capability 工具或为旧工具附加 alias/capability metadata | Tool binding 入口 |
| `backend/app/agent/runtime/nodes.py` | 消费新的 `RouterDecision`，绑定 capability tools，记录选择 trace，保持 final round 不 fallback all | 主对话链路 |
| `backend/app/agent/runtime/tool_executor.py` | 识别 capability/operation 风险和 alias，写操作继续进入 pending action 或 pending plan | 写操作确认 |
| `backend/app/agent/executor/pending_actions.py` | 让旧 pending action 可通过 alias 映射到新 capability/operation | 历史兼容 |
| `backend/app/agent/skill_coverage.py` | 覆盖矩阵从 API/旧 Skill 映射更新为 capability/operation 映射 | 文档和审计 |

### 第一阶段必须新增或调整测试

| 文件或目录 | 改造内容 |
| --- | --- |
| `backend/tests/agent/router/test_skill_router.py` | 覆盖 domain、capability、operation 选择和 Top-K |
| `backend/tests/agent/router/test_router_policy.py` | 覆盖读写隔离、schema 预算、高风险、fallback 禁止 |
| `backend/tests/agent/router/test_router_models.py` | 覆盖新增 RouterDecision 字段序列化 |
| `backend/tests/agent/router/test_router_trace.py` | 覆盖 score、evidence、rejected candidates trace |
| `backend/tests/agent/test_runtime_router_binding.py` | 覆盖 runtime 只绑定 capability tools，不再全量绑定 |
| `backend/tests/agent/test_select_tools_force_binding.py` | 确认 `select_tools` 兼容薄层仍可用，但不再主导读查询 |
| `backend/tests/agent/test_tool_executor_metadata.py` | 覆盖 Registry metadata 对权限、风险、启停的影响 |
| `backend/tests/agent/test_pending_action_executor.py` | 覆盖旧 tool name pending action 通过 alias 执行 |
| `backend/tests/skills/test_skill_docs.py` | 增加 Registry metadata 必填字段校验 |
| `backend/tests/skills/test_skill_metadata.py` | 覆盖 Skill metadata 从 Registry 合并 |
| `backend/tests/skills/test_skill_coverage_matrix.py` | 覆盖 coverage matrix 与 capability/operation 对齐 |

### 第一阶段建议新增检查脚本

| 文件 | 内容 |
| --- | --- |
| `scripts/check-skill-registry.sh` | 校验 Registry YAML 格式、必填字段、alias 是否能解析到 capability/operation |
| `scripts/check-skill-docs.sh` | 扩展现有检查，确保 `skill.md` 与 Registry 的 name、domain、capability 不冲突 |
| `scripts/harness-check.sh` | 增加 Registry 检查入口 |

### 第二阶段按能力合并时才改造

以下文件在第一阶段不需要重写。只有当某个 capability 真正替代旧 Skill 执行入口时，才按领域逐步改造：

| 目录 | 何时改 |
| --- | --- |
| `backend/app/agent/skills/create-cost-record/` | `manage_cost.create_record` 真正接管写入时 |
| `backend/app/agent/skills/delete-cost-record/` | `manage_cost.delete_record` 接管高风险删除时 |
| `backend/app/agent/skills/cost-summary/` | `manage_cost.query_summary` 接管账务查询时 |
| `backend/app/agent/skills/get-debt-summary/` | `manage_cost.query_debt` 接管欠款查询时 |
| `backend/app/agent/skills/settle-debt/` | `manage_cost.settle_debt` 接管还款时 |
| `backend/app/agent/skills/create-crop-cycle/` | `manage_crop_cycle.create_cycle` 接管建茬口时 |
| `backend/app/agent/skills/crop-cycle/`、`get-crop-cycles/` | `manage_crop_cycle.query*` 接管查询时 |
| `backend/app/agent/skills/update-crop-cycle/`、`delete-crop-cycle/` | `manage_crop_cycle` 接管更新和删除时；`update-crop-stage/` 已物理合并到 `manage-crop-cycle.update_stage` |
| `backend/app/agent/skills/create-operation-work-order/`、`get-operation-work-orders/`、`update-operation-work-order/` | `manage_work_orders` 接管作业单时 |
| `backend/app/agent/skills/get-workers/`、`manage-workers/` | `manage_workers` 统一读写入口时 |
| `backend/app/agent/skills/get-labor-payables/`、`settle-labor-payment/`、`manage-wages/` | `manage_labor_payment` 接管人工结算时 |
| `backend/app/agent/skills/log-farm-activity/`、`farm-logs/` | 已物理合并到 `manage-farm-logs`；旧工具名通过 registry alias 兼容 |
| `backend/app/agent/skills/manage-user-settings/` | `get-user-settings/` 已物理合并到 `manage-user-settings/`；旧工具名通过 registry alias 兼容 |

### 第一阶段明确不改

| 范围 | 原因 |
| --- | --- |
| `backend/app/services/**` | 业务服务保持稳定，避免和路由治理混在一起 |
| `backend/app/api/**` | API 契约不因 Skill Registry 改造变化 |
| `backend/app/models/**` | 不涉及数据模型变更 |
| `backend/app/context/**` | 只消费 `RouterDecision.context_dependencies`，第一阶段不重构 selector |
| `backend/app/memory/**` | 不改变记忆存储和检索语义 |
| 前端目录 | 本次是后端 Agent Skill 治理，不涉及 UI |
| `.git/`、`__pycache__/`、`*.pyc` | 禁止修改或提交生成物 |

### 推荐拆分粒度

为方便评估调整大小，建议拆成 4 个可独立验证的小变更：

1. Registry Skeleton：新增 `skills.yaml`、`aliases.yaml`、`domains.yaml` 和校验测试，不接入 runtime。
2. Catalog Loader：让 `SkillCatalog` 从 Registry 读取并生成候选，保持旧 Router 输出不变。
3. Router Decision：加入 domain/capability/operation 选择、score 和 trace，替换静态 registry 选择。
4. Runtime Binding：runtime 消费 capability tools 和 alias，pending action 保持兼容。

如果只做前两步，调整偏小，主要是文档、YAML、loader 和测试；做到第三步开始影响主对话链路；
做到第四步才会触及工具执行和 pending 确认链路。

## 测试与验收

Router 指标：

| 指标 | 目标 |
| --- | --- |
| Top-1 capability accuracy | >= 90% |
| Top-3 capability recall | >= 98% |
| 读意图误暴露写 operation | <= 1% |
| 高风险写误暴露 | 0 |
| 普通请求 selected tools | <= 2 |
| 复杂请求 selected tools | <= 5 |
| fallback all | 0 |

必测场景：

- “今天买了100元化肥”命中 `manage_cost.create_record`。
- “这个月花了多少钱”命中 `manage_cost.query_summary`。
- “这个月比上个月多花多少”命中 `analyze_cost`。
- “西瓜进膨大期了”命中 `manage_crop_cycle.update_stage`。
- “我的工人有哪些”命中 `manage_workers.query`，不暴露写 operation。
- “给老王补付300人工”命中 `manage_labor_payment.settle_payment`。
- “删除这个茬口”进入 `write_high` 确认，不直接执行。
- 工人创建加作业单创建的多意图输入生成 pending plan。

## Skill Governance 规范

### 命名规范

- Capability Skill 使用 `verb_object`。
- 不再新增 `create_*`、`get_*`、`delete_*` API 粒度 Skill，除非该能力天然只有单一业务动作。
- 外部能力可以使用稳定行业名，例如 `web_search`。

### 新增 Skill 准入

新增 Skill 必须回答：

1. 它代表哪个用户业务能力。
2. 为什么不能并入现有 Capability Skill。
3. 它属于哪个 domain。
4. 它有哪些 operation，每个 operation 风险是什么。
5. 它需要哪些上下文和缓存失效。
6. 它的正例、反例、评测样本是什么。

### 文档规范

每个 Skill 文档必须包含：

- 适用用户意图。
- 不适用场景。
- 正向示例。
- 反向示例。
- 参数和缺参策略。
- 风险和确认策略。
- 失败处理。
- 缓存和上下文依赖。

### 评测治理

每个 capability 至少维护：

- 5 条正例。
- 5 条反例。
- 2 条多轮上下文样本。
- 写操作至少 2 条确认链路样本。
- 高风险操作至少 2 条拒绝或澄清样本。

### 月度健康报告

每月输出 Skill 健康报告：

- capability 数量和 operation 数量。
- deprecated alias 使用量。
- Router Top-1 accuracy。
- Router Top-3 recall。
- 平均 selected tools。
- schema token p50/p95。
- 误选高频 case。
- examples/anti_examples 重复和冲突。

## 非目标

- 本设计不要求一次性重写所有 Skill handler。
- 本设计不取消写操作确认链路。
- 本设计不把 Router 变成业务关键词词库。
- 本设计不要求第一阶段引入 embedding retrieval。
- 本设计不删除现有 Skill 目录，删除必须等兼容指标达标。

## 决策摘要

采用 Registry-first、Capability Skill、operation adapter 和 legacy alias 的渐进迁移方案。
短期先建立统一 `skills.yaml` 和治理规则，减少 Tool Selection 混乱；中期让 Router 和
Prompt Builder 只依赖 Registry；长期再按 domain 收敛目录和实现。这样既能支撑 100+
Skill 扩展，也能保护当前生产链路、pending action、trace 和评测资产。
