# 农事日志、用工与发薪统计业务边界设计

> 状态：设计中 | 日期：2026-07-28 | 关联：`manage_farm_logs`、`manage_work_orders`、`manage_labor_payment`、`workers`、`labor_entries`

## 1. 背景

农场里“今天干了什么活”和“这个工人该发多少钱”经常在自然语言里混在一起。典型输入包括：

- “今天 3 号棚打药了”
- “张三今天打药了”
- “张三今天打药一天 180”
- “安排张三明天去 3 号棚打药”
- “这个月每个工人应该发多少钱”

如果把这些全部归到农事日志，会导致发薪统计缺少稳定工资台账；如果把这些全部归到工资 Skill，又会把普通农事记录误写成应付工资。因此必须明确三类主账边界。

## 2. 业务主账

| 主账 | 表/Skill | 记录什么 | 不记录什么 |
| --- | --- | --- | --- |
| 农事事实账 | `farm_logs` / `manage_farm_logs` | 农事操作事实：浇水、打药、施肥、除草、翻地、阶段变化备注 | 不自动生成工资、不承诺发薪 |
| 作业用工账 | `operation_work_orders` / `manage_work_orders` | 某次作业安排或执行范围、日期、参与工人、作业类型 | 不负责结清工资 |
| 工资应付账 | `labor_entries` / `manage_labor_payment` | 工人、日期、计薪方式、数量、单价、应付、已付、未付 | 不作为农事日志全文记录 |

结论：**发薪统计以 `labor_entries` 为准，不以 `farm_logs` 为准。**

## 3. 三类 Skill 的边界

### 3.1 `manage_farm_logs`

用于记录农事事实。

适用输入：

- “今天浇水了”
- “3 号棚今天打药了”
- “昨天给西瓜施肥了”
- “最近 7 天农事日志”

可选关联：

- `worker_ids` / `worker_names`：参与人，仅作为事实备注和追溯信息。
- `work_order_id`：如果该日志来自某个作业单，可做来源引用。

禁止行为：

- 不因为出现工人姓名就自动生成工资。
- 不因为出现“打药/浇水/施肥”就推断应付工资。
- 不结算人工，不更新 `paid_amount`。

### 3.2 `manage_work_orders`

用于记录“作业 + 范围 + 用工”的执行单或安排单，是农事和工资之间的桥。

适用输入：

- “安排张三明天去 3 号棚打药”
- “今天李树去 6 号棚收水稻”
- “把 5 号棚采收作业改到明天”
- “查询最近玉米授粉作业”

工资相关规则：

- 如果输入包含工人和明确计薪字段，如“一天 180”“3 天”“每小时 20”，创建作业单时同步生成 `labor_entries`。
- 如果输入只包含工人但没有工资字段，优先使用工人档案的 `default_pay_type/default_unit_price`；无法唯一确定时进入确认或追问。
- 作业单可以派生农事日志或关联农事日志，但工资统计仍以 `labor_entries` 为准。

### 3.3 `manage_labor_payment`

用于工资台账、未付人工查询和结算。

适用输入：

- “张三今天来了一天”
- “给李海记 15 天压瓜工资每天 180”
- “老王这个月工资多少”
- “这个月每个工人应该发多少钱”
- “把所有员工工资结了”

核心 operation：

- `manage_wage`：新增或更新工资记录。
- `query_payables`：查询未付人工和应发工资。
- `settle_payment`：结算或补付工资。

禁止行为：

- 不创建普通农事日志。
- 不把“张三今天打药了”这种无工资信号的事实句强行写成工资记录。

## 4. 发薪日统计策略

发薪日查询不需要依赖农事日志是否完整。系统按以下来源统计：

1. `labor_entries`：工资应付明细，作为唯一应发工资来源。
2. `workers.default_pay_type/default_unit_price`：缺省计薪规则，用于创建新工资记录或作业单时推断。
3. `operation_work_orders`：工资记录的作业来源，用于说明“哪天做了什么活”。
4. `farm_logs`：仅作辅助佐证，不能直接纳入应发金额。

查询输出建议：

```text
7 月未付人工汇总：
- 张三：18 天 × 180 = 3240，已付 0，待付 3240
- 李四：15 天 × 160 = 2400，已付 500，待付 1900
合计：应付 5640，已付 500，待付 5140
```

如果用户忘记登记农事日志，但登记过出勤或工资：

```text
张三今天来了
李四今天上工一天
王五这个月来了 18 天
```

这些都应该进入 `manage_labor_payment.manage_wage`，发薪日可正常统计。

如果用户既忘记农事日志，也没有登记出勤或工资，系统不能凭空推断工资，只能提供缺口提示：

```text
未找到张三在 7 月的工资记录。可补录“张三 7 月来了 18 天，每天 180”后再统计。
```

## 5. 路由判定表

| 用户输入 | 主 Skill | Operation | 原因 |
| --- | --- | --- | --- |
| 今天浇水了 | `manage_farm_logs` | `create_log` | 农事事实，无工人、无工资 |
| 3 号棚今天打药了 | `manage_farm_logs` | `create_log` | 农事事实，无工资 |
| 张三今天打药了 | `manage_farm_logs` | `create_log` | 可记录参与人，但无工资信号 |
| 张三今天打药一天 180 | `manage_labor_payment` 或 `manage_work_orders` | `manage_wage` / `create_work_order` | 出现工人、天数、单价，形成应付工资；若有明确作业范围则优先作业单 |
| 安排张三明天去 3 号棚打药 | `manage_work_orders` | `create_work_order` | 安排动作 + 工人 + 作业范围 |
| 张三今天来了一天 | `manage_labor_payment` | `manage_wage` | 出勤/工资台账，不是农事事实 |
| 老王这个月工资多少 | `manage_labor_payment` | `query_payables` | 发薪统计 |
| 这个月每个工人应该发多少钱 | `manage_labor_payment` | `query_payables` | 按工资台账汇总 |
| 给老王补付 300 人工 | `manage_labor_payment` | `settle_payment` | 支付/结算 |

## 6. 字段设计建议

### 6.1 `farm_logs`

短期不强制改表。若后续要支持参与人追溯，建议增加轻量关联，而不是直接内嵌工资字段：

```text
farm_log_workers
- farm_log_id
- worker_id
- role/note
```

或在日志 payload 中保留只读展示字段：

```text
worker_names?: string[]
work_order_id?: int
```

这些字段只用于追溯，不参与发薪金额计算。

### 6.2 `labor_entries`

工资统计必须包含：

- `worker_id`
- `work_date`
- `pay_type`
- `quantity`
- `unit_price`
- `payable_amount`
- `paid_amount`
- `unpaid_amount`
- `settlement_status`
- `work_order_id?`
- `client_request_id`

建议保持 `client_request_id` 幂等键，避免用户重复说“张三今天来了一天”时重复记工资。

## 7. Skill Router 原则

路由不应通过不断堆规则解决该边界，而应按业务信号分流：

| 信号 | 路由倾向 |
| --- | --- |
| 农事动作，无工人/工资 | `manage_farm_logs.create_log` |
| 农事动作 + 工人，无计薪字段 | `manage_farm_logs.create_log`，可选参与人 |
| 安排/派/叫/让 + 工人 + 作业 | `manage_work_orders.create_work_order` |
| 工人 + 天数/小时/单价/工资/日薪 | `manage_labor_payment.manage_wage` |
| 发薪/应发/未付/结清 | `manage_labor_payment.query_payables` / `settle_payment` |

规则分类器只负责高置信直达和安全护栏；模糊写入进入 `BM25 + QuillRAG vector + lexical prior` 的 operation 级混合召回。

## 8. 验收样本

应加入 Skill Router 回归集：

| Case | Expected |
| --- | --- |
| 记录今天育苗 | `manage_farm_logs.create_log` |
| 3 号棚今天打药了 | `manage_farm_logs.create_log` |
| 张三今天打药了 | `manage_farm_logs.create_log` |
| 张三今天打药一天 180 | `manage_labor_payment.manage_wage` 或 `manage_work_orders.create_work_order`，取决于是否识别到作业范围 |
| 安排张三明天去 3 号棚打药 | `manage_work_orders.create_work_order` |
| 张三今天来了一天 | `manage_labor_payment.manage_wage` |
| 这个月每个工人应该发多少钱 | `manage_labor_payment.query_payables` |
| 把所有员工工资结了 | `manage_labor_payment.settle_payment` |

## 9. 改动影响范围

这不是单纯的 Skill 文档或 Router 规则调整，而是一项跨业务主账、领域 service、Skill 契约、上下文和前端展示的能力改造。实现时必须按层拆开，避免把工资逻辑塞进农事日志 Skill。

### 9.1 数据模型

必须确认或补齐：

- `workers.default_pay_type/default_unit_price`：工人默认计薪方式和默认日薪。
- `labor_entries.work_date/quantity/unit_price/payable_amount/paid_amount/unpaid_amount/settlement_status`：发薪统计主字段。
- `labor_entries.client_request_id`：出勤和工资补录的幂等键。
- `operation_work_orders -> labor_entries`：作业单与工资明细的来源关系。

可选增强：

- `farm_log_workers`：农事日志参与人关联表。
- `farm_logs.work_order_id`：农事日志来源作业单。

不建议：

- 不在 `farm_logs` 中直接增加 `payable_amount/paid_amount/unpaid_amount`。
- 不让农事日志表承担工资主账职责。

### 9.2 领域 service

需要修改或确认的 service 边界：

| Service | 改动点 |
| --- | --- |
| `labor_service` | 支持独立出勤/工资补录，按工人默认日薪生成 `LaborEntry`，保持幂等。 |
| `planting_read_service` | 增强工资汇总查询，按周期、日期范围、工人汇总应付/已付/未付。 |
| `planting_service` | 作业单创建/更新时，按工人和计薪字段同步 `labor_entries`。 |
| `farm_log_service` | 只记录农事事实；如果支持参与人，只写关联，不生成工资。 |
| `cost_service` | 工资记录生成或更新时同步人工成本账单，保持与 `labor_entries` 回链一致。 |

关键约束：

- 发薪统计只能从 `labor_entries` 汇总。
- `farm_logs` 可以作为佐证来源，但不能参与金额计算。
- 自动推断工资前必须有明确计薪字段，或能从工人默认工资唯一推断，并进入写确认。

### 9.3 Skill 层

| Skill | 改动范围 |
| --- | --- |
| `manage_farm_logs` | 支持可选参与人/来源作业单展示；不创建工资记录。 |
| `manage_work_orders` | 作业 + 工人 + 计薪字段时同步工资明细；缺工资策略时追问或使用默认工资。 |
| `manage_labor_payment` | 增强 `query_payables` 为发薪汇总；支持 `manage_wage` 处理“今天来了/上工一天/本月来了 N 天”。 |

建议新增或增强的 operation 语义：

```text
manage_labor_payment.query_payables
  - 支持 worker/start_date/end_date/group_by_worker/include_paid
  - 返回每个工人应付、已付、待付、明细数量

manage_labor_payment.manage_wage
  - 支持 action=save/update
  - 支持 work_date/quantity/unit_price/pay_type
  - 支持从 worker 默认工资推断 unit_price
```

### 9.4 Skill Router

Router 改动不是“补更多规则”，而是让业务信号进入正确候选池：

- 农事事实句进入 `manage_farm_logs.create_log`。
- 作业安排句进入 `manage_work_orders.create_work_order`。
- 出勤/工资/日薪/天数句进入 `manage_labor_payment.manage_wage`。
- 发薪/应发/未付/结清句进入 `manage_labor_payment.query_payables` 或 `settle_payment`。
- 模糊写入继续走 `BM25 + QuillRAG vector + lexical prior` 混合召回。

Trace 中必须保留：

- `source_of_activity = farm_logs | operation_work_orders`
- `source_of_payroll = labor_entries`
- `route_key`
- `candidate_scores`
- `payroll_summary_source`

### 9.5 Context / Trace / DataFlywheel

需要补齐：

- Context 中的 `unpaid_labor` 要能支撑发薪日问答。
- Trace 中要明确本次回复的工资数据来自 `labor_entries`，不是农事日志。
- DataFlywheel 应收集三类混淆样本：农事日志误进工资、工资误进日志、作业单和独立工资记录混淆。

### 9.6 前端与移动端

需要影响的界面：

- 工人工资汇总页：按工人展示应付、已付、待付。
- 工资明细页：展示来源作业单、日期、作业类型、数量、单价。
- 结算确认流：支持按单个工人、日期范围、全部未付结算。
- 农事日志详情：可选展示参与人和来源作业单，但不展示为工资主账。
- 作业单详情：展示关联工人和工资明细。

## 10. 分阶段落地

### Phase 1：不改表，先修发薪主链路

目标：先解决“发薪日每个工人应该发多少钱”。

范围：

1. 增强 `manage_labor_payment.query_payables`，支持日期范围和按工人汇总。
2. 支持“张三今天来了/上工一天”的 `manage_wage` 补录。
3. 使用 `workers.default_unit_price` 推断日薪，缺失时追问。
4. 加 Skill Router 回归样本。
5. Trace 标注 `source_of_payroll=labor_entries`。

不做：

- 不新增 `farm_log_workers`。
- 不让农事日志自动生成工资。

### Phase 2：增强作业单与工资联动

目标：让“安排/作业 + 工人 + 工资”形成完整作业用工链路。

范围：

1. `manage_work_orders.create_work_order` 稳定生成 `operation_work_orders + labor_entries`。
2. 更新作业单时同步调整工资明细。
3. 作业单查询返回工资状态摘要。
4. 结算工资时可按作业单范围结清。

### Phase 3：可选增强农事日志参与人

目标：让农事日志可追溯谁参与，但仍不承担工资主账。

范围：

1. 评估是否新增 `farm_log_workers`。
2. 农事日志创建支持 `worker_names/worker_ids`。
3. 农事日志详情展示参与人。
4. 报表中允许并列展示农事事实和工资来源，但金额仍来自 `labor_entries`。

## 11. 后续实现建议

1. 增强 `manage_labor_payment.query_payables` 为发薪汇总视图，支持 `start_date/end_date/worker`。
2. 增加“出勤补录”输入解析，把“张三今天来了”转成 `manage_wage(action=save, quantity=1)`。
3. 若业务确认需要在农事日志展示参与人，再增加 `farm_log_workers` 关联表。
4. 在 Trace 中区分 `source_of_payroll=LaborEntry` 和 `source_of_activity=FarmLog/WorkOrder`。
5. 把本设计样本加入 `skill_route_cases.json`，防止后续路由把日志和工资再次混淆。
