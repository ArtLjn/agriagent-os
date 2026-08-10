# 工人工资管理业务设计

> Spec ID: 2026-08-10-worker-wage-management
> 状态: implemented
> 关联文件: business/services/labor_service.py, business/tools/work_orders.py, agent/skills/manage-work-orders/skill.md

## 1. 问题分析

### 1.1 Session 暴露的三个问题

从 `v2/tmp/session.json` 的"查询工人工资"对话中发现：

| 作业单 | 工人 | 计薪 | 数量 | 单价 | 应付 | 问题 |
|--------|------|------|------|------|------|------|
| #21 育苗 | 朱哥 | - | - | - | 0 | labor_entries 为空，add_labor 未被调用 |
| #22 育苗 | 王阿毛 | daily | 1天 | **0** | **0** | unit_price 未传时默认 0，未从工人档案读取 default_unit_price=100 |
| #23 采摘 | 张三 | hourly | 3小时 | 15 | 45 | 正确（LLM 传了 unit_price） |

**根因**：`labor_service._apply_labor_values` 中 `unit_price` 缺省为 `Decimal("0")`，不从工人档案 `default_unit_price` 回填。

### 1.2 工资查询能力缺失

用户需求：
- "查询本月未结款" — 看当前谁还有多少没付
- "查看历史账单" — 按月份查询已结/未结
- "张三 6-8 月一共给了多少工资" — 按工人+时段汇总

当前 `manage_work_orders` 只有 `query`（查作业单列表）和 `settle`（结算），缺少工资汇总查询。

## 2. 业务概念

### 2.1 三层数据模型

```
┌─────────────────────────────────────────────────┐
│  作业单 OperationWorkOrder                       │
│  ├─ operation_type: 育苗/采摘/浇水...            │
│  ├─ operation_date: 2026-08-10                   │
│  └─ cycle_id: 关联茬口                           │
│       │                                          │
│       ├─ 用工明细 LaborEntry (1:N)               │
│       │   ├─ worker_name: 朱哥                   │
│       │   ├─ pay_type: daily / hourly / piece    │
│       │   ├─ quantity: 1 (天/小时/件)            │
│       │   ├─ unit_price: 100 (日薪/时薪/件薪)    │
│       │   ├─ payable_amount: 100 (应得)          │
│       │   ├─ paid_amount: 0 (已付)               │
│       │   └─ settlement_status: unpaid/partial/settled │
│       │                                          │
│       └─ 人工成本账单 CostRecord (1:1 聚合)       │
│           ├─ amount: 100 (总应付)                │
│           ├─ settled_amount: 0 (已结算)          │
│           └─ settlement_status: unpaid           │
└─────────────────────────────────────────────────┘
```

### 2.2 工资 vs 财务记账（关键区分）

| 维度 | 工时记录 (LaborEntry) | 财务记账 (CostRecord) |
|------|----------------------|----------------------|
| **本质** | 出勤记录：今天干了，应得多少 | 实际收支：钱进出 |
| **何时产生** | add_labor 时由系统自动创建 | add_labor 时同步生成（unpaid） |
| **支付状态** | unpaid → partial → settled | unpaid → partial → settled |
| **何时变为 settled** | settle 操作支付后 | 同左（联动更新） |
| **手动记账** | 不走 manage_cost | 走 manage_cost（买化肥/卖菜等） |

**核心原则**：工人工资不通过 `manage_cost` 手动记账。工时记录 → 系统自动生成 unpaid CostRecord → 月底 settle 联动更新为 settled。

### 2.3 日结工 vs 时薪工 vs 件薪工

| 类型 | pay_type | quantity 含义 | unit_price 含义 | payable 计算 |
|------|----------|--------------|----------------|-------------|
| 日结工 | daily | 天数 | 日薪 | quantity × unit_price |
| 时薪工 | hourly | 小时数 | 时薪 | quantity × unit_price |
| 件薪工 | piece | 件数 | 件薪 | quantity × unit_price |

三种类型计算公式相同：`payable_amount = quantity × unit_price`。

## 3. 修复方案

### 3.1 P0: unit_price 自动回填（bug 修复）

**文件**: `business/services/labor_service.py`

**问题**: `_apply_labor_values` 中 `unit_price` 缺省为 `Decimal("0")`，不从工人档案读取。

**修复**: `build_labor_entry` 在调用 `_apply_labor_values` 前，如果 `data` 中没有 `unit_price`，从 `worker.default_unit_price` 回填；如果没有 `pay_type`，从 `worker.default_pay_type` 回填。

```python
# build_labor_entry 中，解析 worker 后：
if data.get("unit_price") is None:
    data = {**data, "unit_price": float(worker.default_unit_price or 0)}
if data.get("pay_type") is None:
    data = {**data, "pay_type": worker.default_pay_type or "daily"}
```

**效果**: 王阿毛 add_labor 时不传 unit_price → 自动从档案读取 100 → payable_amount=100。

### 3.2 P1: 工资查询操作

**文件**: `business/tools/work_orders.py`, `agent/skills/manage-work-orders/skill.md`

新增 `operation="wages"` 操作，支持三种查询模式：

#### 查询模式 A：本月未结款

```
operation="wages", query_mode="unpaid"
→ 返回每个工人的未结金额汇总
```

**示例返回**:
```json
{
  "mode": "unpaid",
  "as_of_date": "2026-08-10",
  "summary": {
    "total_unpaid": 145.0,
    "worker_count": 2
  },
  "workers": [
    {"worker_id": 24, "worker_name": "朱哥", "entry_count": 1, "total_payable": 100.0, "total_paid": 0, "total_unpaid": 100.0},
    {"worker_id": 25, "worker_name": "张三", "entry_count": 1, "total_payable": 45.0, "total_paid": 0, "total_unpaid": 45.0}
  ]
}
```

#### 查询模式 B：按月份查询历史账单

```
operation="wages", query_mode="monthly", month="2026-08"
→ 返回该月所有工人的工资汇总（含已结/未结）
```

**示例返回**:
```json
{
  "mode": "monthly",
  "month": "2026-08",
  "summary": {
    "total_payable": 145.0,
    "total_paid": 0,
    "total_unpaid": 145.0,
    "worker_count": 2
  },
  "workers": [
    {"worker_id": 24, "worker_name": "朱哥", "entry_count": 1, "total_payable": 100.0, "total_paid": 0, "total_unpaid": 100.0, "status": "unpaid"},
    {"worker_id": 25, "worker_name": "张三", "entry_count": 1, "total_payable": 45.0, "total_paid": 0, "total_unpaid": 45.0, "status": "unpaid"}
  ]
}
```

#### 查询模式 C：按工人+时段查询明细

```
operation="wages", query_mode="worker", worker_name="张三", start_date="2026-06-01", end_date="2026-08-31"
→ 返回张三在 6-8 月的所有工时记录明细
```

**示例返回**:
```json
{
  "mode": "worker",
  "worker_name": "张三",
  "date_range": "2026-06-01 ~ 2026-08-31",
  "summary": {
    "entry_count": 3,
    "total_payable": 135.0,
    "total_paid": 90.0,
    "total_unpaid": 45.0
  },
  "entries": [
    {"work_order_id": 23, "operation_type": "采摘", "operation_date": "2026-08-10", "pay_type": "hourly", "quantity": 3, "unit_price": 15, "payable_amount": 45, "paid_amount": 0, "settlement_status": "unpaid"},
    {"work_order_id": 18, "operation_type": "浇水", "operation_date": "2026-07-15", "pay_type": "hourly", "quantity": 2, "unit_price": 15, "payable_amount": 30, "paid_amount": 30, "settlement_status": "settled"},
    {"work_order_id": 15, "operation_type": "施肥", "operation_date": "2026-06-20", "pay_type": "hourly", "quantity": 4, "unit_price": 15, "payable_amount": 60, "paid_amount": 60, "settlement_status": "settled"}
  ]
}
```

### 3.3 P2: 月底结算优化

**文件**: `business/tools/work_orders.py`

当前 `settle` 操作已支持按 `worker_name` / `start_date` / `end_date` 筛选结算。优化点：

1. **settle 返回值增强**：结算后返回本次结算的汇总（结算了几个工人、总共多少钱）
2. **skill.md 引导**：明确 settle 是"月底统一支付"场景，不是单笔支付

```json
{
  "settled_count": 3,
  "total_settled_amount": 145.0,
  "details": [
    {"worker_name": "朱哥", "settled_amount": 100.0, "entry_count": 1},
    {"worker_name": "张三", "settled_amount": 45.0, "entry_count": 1}
  ]
}
```

## 4. Skill 定义变更

### 4.1 manage_work_orders 新增 wages 操作

```yaml
operations:
  wages:
    tool_name: query_wages
    description: 查询工人工资汇总，支持三种模式：本月未结款/按月查历史/按工人查明细
    risk_level: read
    parameters: [query_mode, worker_name, month, start_date, end_date]
    required: [query_mode]
```

### 4.2 新增参数

```yaml
query_mode:
  type: string
  enum: [unpaid, monthly, worker]
  description: |
    unpaid=查所有工人未结款汇总（如"谁还欠多少""本月未结"）
    monthly=按月份查历史账单（如"8月工资""上个月工资"）
    worker=按工人查明细（如"张三6-8月工资""朱哥的工资明细"）
month:
  type: string
  description: YYYY-MM 月份（monthly 模式必填）
```

## 5. 后端实现

### 5.1 labor_service 新增 query_wages 函数

```python
def query_wages(
    db: Session,
    farm_id: int,
    mode: str,  # unpaid / monthly / worker
    worker_name: str | None = None,
    month: str | None = None,  # "2026-08"
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    """查询工人工资汇总，三种模式。"""
```

**查询逻辑**：
- `unpaid`：`LaborEntry.settlement_status IN ('unpaid', 'partial')`，按 worker_id 分组聚合
- `monthly`：按 `WorkOrder.operation_date` 过滤到指定月份，按 worker_id 分组聚合
- `worker`：按 `worker_name` + 日期范围过滤，返回每条 LaborEntry 明细

### 5.2 work_order_service.settle 返回值增强

当前 settle 返回 `{"settled_count": N}`，改为返回带明细的汇总。

## 6. 验收标准

| 场景 | 预期 |
|------|------|
| add_labor 不传 unit_price | 自动从工人档案读取 default_unit_price |
| add_labor 不传 pay_type | 自动从工人档案读取 default_pay_type |
| 日结工 add_labor(quantity=1) | payable_amount = 1 × 100 = 100 |
| "查询本月未结款" | 返回每个工人未付金额汇总 |
| "8月工资账单" | 返回 8 月所有工人已结+未结汇总 |
| "张三6-8月工资明细" | 返回张三每条工时记录 + 汇总 |
| settle 后再查 unpaid | 已结算的不出现 |
| settle 后按月查 | 显示已结算状态 |

## 7. 实施计划

1. **P0**：修复 `build_labor_entry` 的 unit_price/pay_type 自动回填
2. **P1**：`labor_service.query_wages` + `manage_work_orders` wages 操作 + skill.md
3. **P2**：settle 返回值增强
4. 测试 + lint + skill metadata 校验
