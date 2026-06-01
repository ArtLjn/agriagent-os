# 农业记账功能优化 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 优化农业记账模块，补齐赊账双向标记、记录编辑、搜索、支付方式等缺失功能。

**Architecture:** 在现有 CostRecord 数据模型上扩展，前端复用现有组件模式，后端新增 PUT 端点。赊账逻辑复用 `record_subtype` + `counterparty` 字段。

**Tech Stack:** React Native + TypeScript + Zustand (前端) / FastAPI + SQLAlchemy + SQLite (后端)

---

### Task 1: 后端 — 添加 payment_method 字段和 PUT 端点

**Files:**
- Modify: `backend/app/models/cost.py` — 加 `payment_method` 列
- Modify: `backend/app/schemas/cost.py` — 加 `payment_method` 字段
- Modify: `backend/app/api/cost.py` — 加 PUT 端点
- Modify: `backend/app/services/cost_service.py` — 加 `update_record` 函数

- [ ] **Step 1: CostRecord 模型加 payment_method 列**

在 `backend/app/models/cost.py` 的 `CostRecord` 类中，`parent_record_id` 下方加：

```python
    payment_method = Column(String(20), nullable=True)
```

- [ ] **Step 2: Schema 加 payment_method 字段**

在 `backend/app/schemas/cost.py` 中：

`CostRecordBase` 加：
```python
    payment_method: str | None = Field(None, max_length=20)
```

`CostRecordUpdate` 加：
```python
    payment_method: str | None = Field(None, max_length=20)
```

- [ ] **Step 3: cost_service 加 update_record 函数**

在 `backend/app/services/cost_service.py` 中，`delete_record` 函数之前加：

```python
def update_record(db: Session, record_id: int, farm_id: int, data) -> CostRecord | None:
    record = (
        db.query(CostRecord)
        .filter(CostRecord.id == record_id, CostRecord.farm_id == farm_id)
        .first()
    )
    if not record:
        return None
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(record, field, value)
    try:
        db.commit()
        db.refresh(record)
    except Exception:
        db.rollback()
        raise
    return record
```

`__all__` 列表加 `"update_record"`。

- [ ] **Step 4: API 路由加 PUT 端点**

在 `backend/app/api/cost.py` 中，`delete_record` 路由之前加：

```python
from app.schemas.cost import CostRecordUpdate

@router.put("/{record_id}", response_model=CostRecordResponse)
def update_record(
    record_id: int,
    record: CostRecordUpdate,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    updated = cost_service.update_record(db, record_id, farm_id=farm.id, data=record)
    if not updated:
        raise HTTPException(status_code=404, detail="记录不存在")
    return updated
```

- [ ] **Step 5: 数据库迁移**

```bash
cd backend && alembic revision --autogenerate -m "add payment_method to cost_records" && alembic upgrade head
```

如果没有 alembic 配置，直接删库重建（开发阶段）或手动加列：
```sql
ALTER TABLE cost_records ADD COLUMN payment_method VARCHAR(20);
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/cost.py backend/app/schemas/cost.py backend/app/api/cost.py backend/app/services/cost_service.py
git commit -m "feat: add payment_method field and PUT endpoint for cost records"
```

---

### Task 2: 后端 — 赊账查询支持 receivable 类型

**Files:**
- Modify: `backend/app/services/debt_service.py` — 支持查询 payable 和 receivable
- Modify: `backend/app/api/debt.py` — 加 query 参数

- [ ] **Step 1: debt_service 支持双向查询**

修改 `backend/app/services/debt_service.py`：

`_build_debt_base_query` 函数加 `subtype` 参数：

```python
def _build_debt_base_query(db: Session, farm_id: int, counterparty: str | None = None, subtype: str | None = None):
    query = (
        db.query(CostRecord)
        .filter(CostRecord.farm_id == farm_id)
        .filter(CostRecord.record_subtype.isnot(None))
        .filter(CostRecord.record_subtype != "")
        .filter(CostRecord.settled_at.is_(None))
        .filter(CostRecord.deleted_at.is_(None) if hasattr(CostRecord, 'deleted_at') else True)
    )
    if subtype:
        query = query.filter(CostRecord.record_subtype == subtype)
    else:
        query = query.filter(CostRecord.record_subtype.in_([SUBTYPE_DEBT, "payable", "receivable"]))
    if counterparty is not None:
        query = query.filter(CostRecord.counterparty.like(f"%{counterparty}%"))
    return query
```

更新 `get_debt_records`、`count_debt_records`、`get_debt_summary` 函数签名，透传 `subtype` 参数。

`get_debt_summary` 按 `record_subtype` 分组，分别统计应付和应收。

- [ ] **Step 2: debt API 加 subtype 参数**

修改 `backend/app/api/debt.py` 的 `list_debts`：

```python
@router.get("", response_model=DebtListResponse)
def list_debts(
    counterparty: str | None = Query(None, description="按债权人筛选"),
    subtype: str | None = Query(None, description="payable 或 receivable"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> DebtListResponse:
    skip = (page - 1) * size
    items = debt_service.get_debt_records(
        db, farm_id=farm.id, counterparty=counterparty, subtype=subtype, skip=skip, limit=size
    )
    total = debt_service.count_debt_records(
        db, farm_id=farm.id, counterparty=counterparty, subtype=subtype
    )
    summary = debt_service.get_debt_summary(db, farm_id=farm.id)
    return DebtListResponse(items=items, total=total, summary=summary)
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/debt_service.py backend/app/api/debt.py
git commit -m "feat: debt query supports payable and receivable subtypes"
```

---

### Task 3: 前端 — API 类型和 Store 更新

**Files:**
- Modify: `FarmManagerMobile/src/api/types.ts` — 加 `payment_method` 类型
- Modify: `FarmManagerMobile/src/api/client.ts` — 加 PUT 方法、更新 debt 查询参数
- Modify: `FarmManagerMobile/src/stores/costStore.ts` — 加 `updateRecord` action

- [ ] **Step 1: types.ts 加字段**

在 `CostRecord` 类型中加：
```typescript
  payment_method?: string;
```

在创建记录的参数类型中加：
```typescript
  payment_method?: string;
```

- [ ] **Step 2: client.ts 加 updateRecord 和 debt 查询参数**

在 `costApi` 对象中加：
```typescript
    updateRecord: (id: number, data: any) =>
      apiClient.put(`/costs/${id}`, data),
```

在 `debtApi` 的 `getDebts` 方法中加可选 `subtype` 参数：
```typescript
    getDebts: (params?: { counterparty?: string; subtype?: string }) =>
      apiClient.get("/debts", { params }),
```

- [ ] **Step 3: costStore 加 updateRecord**

在 `useCostStore` 中加 action：
```typescript
  updateRecord: async (id: number, data: any) => {
    try {
      set({ loading: true, error: null });
      await costApi.updateRecord(id, data);
      await get().fetchRecords();
    } catch (err: any) {
      set({ error: err.message || "更新失败" });
      throw err;
    } finally {
      set({ loading: false });
    }
  },
```

- [ ] **Step 4: Commit**

```bash
git add FarmManagerMobile/src/api/types.ts FarmManagerMobile/src/api/client.ts FarmManagerMobile/src/stores/costStore.ts
git commit -m "feat: add payment_method type, updateRecord API and store action"
```

---

### Task 4: 前端 — CostCreateScreen 支持编辑模式和赊账双向标记

**Files:**
- Modify: `FarmManagerMobile/src/screens/cost/CostCreateScreen.tsx`

- [ ] **Step 1: 接收编辑参数**

组件支持通过 route params 接收 `editRecord`：
```typescript
const editRecord = route.params?.editRecord as CostRecord | undefined;
```

如果 `editRecord` 存在，用其值初始化所有 state（category, amount, recordDate, note, isDebt, counterparty, dueDate, paymentMethod）。

- [ ] **Step 2: 加 payment_method 选择**

在表单中加支付方式选择（在"日期"行下方）：

```tsx
<TouchableOpacity style={styles.fieldRow} onPress={togglePaymentPicker}>
  <Text style={styles.fieldLabel}>支付方式</Text>
  <View style={styles.fieldRight}>
    <Text style={styles.fieldValue}>
      {paymentMethod === "cash" ? "现金" :
       paymentMethod === "wechat" ? "微信" :
       paymentMethod === "bank_card" ? "银行卡" : "请选择"}
    </Text>
    <Icon name="chevron-right" size={18} color={colors.textTertiary} />
  </View>
</TouchableOpacity>
```

- [ ] **Step 3: 赊账标记支持收入类型**

把现有的 `{recordType === "cost" && (...)}` 赊账开关改为对收入也生效：

```tsx
<TouchableOpacity style={styles.fieldRow} onPress={() => setIsDebt(!isDebt)}>
  <Text style={styles.fieldLabel}>
    {recordType === "cost" ? "标记为赊账（我欠别人）" : "标记为赊账（别人欠我）"}
  </Text>
  ...
</TouchableOpacity>
```

赊账字段标签也对应修改：
- 支出时：债权人 → "欠谁的钱"
- 收入时：债权人 → "谁欠我的"

- [ ] **Step 4: 提交逻辑区分创建和编辑**

```typescript
if (editRecord) {
  await useCostStore.getState().updateRecord(editRecord.id, payload);
} else {
  // 现有创建逻辑
}
```

赊账记录提交时的 `record_subtype`：
- 支出赊账：`"payable"`
- 收入赊账：`"receivable"`

- [ ] **Step 5: 标题和按钮文案**

编辑模式时标题改为"编辑记录"，按钮改为"保存修改"。

- [ ] **Step 6: Commit**

```bash
git add FarmManagerMobile/src/screens/cost/CostCreateScreen.tsx
git commit -m "feat: CostCreateScreen supports edit mode and bidirectional debt marking"
```

---

### Task 5: 前端 — RecordItem 长按操作菜单

**Files:**
- Modify: `FarmManagerMobile/src/screens/cost/components/RecordItem.tsx`

- [ ] **Step 1: 长按改为操作菜单**

修改 `RecordItem` 的 `onLongPress` 行为：弹出一个操作弹窗（编辑 / 删除），而不是直接删除。

需要改 props 接口：
```typescript
interface RecordItemProps {
  item: CostRecord;
  onPress: () => void;
  onLongPress?: () => void;
  onEdit?: () => void;
}
```

`onLongPress` 改为弹 Alert 菜单：
```typescript
const handleLongPress = () => {
  Alert.alert("操作", `记录：${item.category} ${item.amount}元`, [
    { text: "编辑", onPress: onEdit },
    { text: "删除", style: "destructive", onPress: onLongPress },
    { text: "取消", style: "cancel" },
  ]);
};
```

- [ ] **Step 2: 显示赊账和支付方式标记**

在 RecordItem 卡片中，如果记录有 `record_subtype`（payable/receivable）或 `payment_method`，显示对应标记：

```tsx
{(item.record_subtype === "payable" || item.record_subtype === "receivable" || item.record_subtype === "赊账") && (
  <View style={[styles.debtBadge, { backgroundColor: item.record_subtype === "receivable" ? "#E8F5ED" : "#FFF3E0" }]}>
    <Text style={{ fontSize: 10, color: item.record_subtype === "receivable" ? "#3B8B5C" : "#E65100" }}>
      {item.record_subtype === "receivable" ? "应收" : "应付"}
    </Text>
  </View>
)}
```

- [ ] **Step 3: Commit**

```bash
git add FarmManagerMobile/src/screens/cost/components/RecordItem.tsx
git commit -m "feat: RecordItem shows edit/delete menu and debt/payment badges"
```

---

### Task 6: 前端 — CostListScreen 加赊账 Tab 和搜索

**Files:**
- Modify: `FarmManagerMobile/src/screens/cost/CostListScreen.tsx`
- Create: `FarmManagerMobile/src/screens/cost/components/DebtTabView.tsx`

- [ ] **Step 1: CostListScreen 顶部加 Tab 切换**

在 `MonthlyStats` 和 `AssetCard` 之间加 Tab 栏：「全部」|「赊账」

```tsx
const [activeTab, setActiveTab] = useState<"records" | "debt">("records");
```

Tab 样式参考现有的 filterChip 样式。

- [ ] **Step 2: 新建 DebtTabView 组件**

创建 `DebtTabView.tsx`，调用 `debtApi.getDebts()` 获取所有赊账记录：

结构：
- 顶部汇总卡片：应付总额 / 应收总额
- 按对方名字分组列表
- 每组显示：对方名、应付/应收金额、记录条数
- 点击展开显示该对方名下的所有记录
- 每条记录：金额、日期、分类、备注

```tsx
export const DebtTabView: React.FC = () => {
  const [debtData, setDebtData] = useState<any>(null);
  const [expandedParty, setExpandedParty] = useState<string | null>(null);

  useFocusEffect(React.useCallback(() => {
    debtApi.getDebts().then(res => setDebtData(res.data));
  }, []));

  // 渲染逻辑...
};
```

- [ ] **Step 3: CostListScreen 加搜索**

在 filterSection 上方加搜索图标按钮。点击后展开搜索框：

```tsx
const [searchVisible, setSearchVisible] = useState(false);
const [searchQuery, setSearchQuery] = useState("");
```

搜索过滤逻辑（本地过滤）：
```typescript
if (searchQuery.trim()) {
  const q = searchQuery.toLowerCase();
  result = result.filter(r =>
    r.note?.toLowerCase().includes(q) ||
    r.counterparty?.toLowerCase().includes(q) ||
    r.category.toLowerCase().includes(q)
  );
}
```

- [ ] **Step 4: 编辑导航集成**

在 `CostListScreen` 中，编辑操作导航到 CostCreate 并传 editRecord：

```typescript
const handleEdit = (record: CostRecord) => {
  setDetailVisible(false);
  navigation.navigate("CostCreate", { editRecord: record });
};
```

传给 `RecordItem` 的 `onEdit` prop。

- [ ] **Step 5: Commit**

```bash
git add FarmManagerMobile/src/screens/cost/CostListScreen.tsx FarmManagerMobile/src/screens/cost/components/DebtTabView.tsx
git commit -m "feat: add debt tab and search to CostListScreen"
```

---

### Task 7: 前端 — RecordDetailModal 显示赊账和支付信息

**Files:**
- Modify: `FarmManagerMobile/src/screens/cost/components/RecordDetailModal.tsx`

- [ ] **Step 1: 显示赊账信息和支付方式**

在详情列表中加赊账相关字段：

```tsx
{record.counterparty && (
  <View style={styles.detailRow}>
    <View style={styles.detailLeft}>
      <Icon name="account-outline" size={18} color={colors.textSecondary} />
      <Text style={styles.detailLabel}>
        {record.record_subtype === "receivable" ? "欠我方" : "欠款方"}
      </Text>
    </View>
    <Text style={styles.detailValue}>{record.counterparty}</Text>
  </View>
)}

{record.payment_method && (
  <View style={styles.detailRow}>
    <View style={styles.detailLeft}>
      <Icon name="credit-card-outline" size={18} color={colors.textSecondary} />
      <Text style={styles.detailLabel}>支付方式</Text>
    </View>
    <Text style={styles.detailValue}>
      {record.payment_method === "cash" ? "现金" :
       record.payment_method === "wechat" ? "微信" :
       record.payment_method === "bank_card" ? "银行卡" : record.payment_method}
    </Text>
  </View>
)}

{record.due_date && (
  <View style={styles.detailRow}>
    <View style={styles.detailLeft}>
      <Icon name="clock-outline" size={18} color={colors.textSecondary} />
      <Text style={styles.detailLabel}>到期日</Text>
    </View>
    <Text style={styles.detailValue}>{dayjs(record.due_date).format("YYYY年M月D日")}</Text>
  </View>
)}
```

- [ ] **Step 2: 加编辑按钮**

在 actions 区域加"编辑"按钮：

```tsx
<TouchableOpacity style={styles.editBtn} onPress={onEdit}>
  <Icon name="pencil-outline" size={18} color={colors.primary} />
  <Text style={styles.editText}>编辑</Text>
</TouchableOpacity>
```

props 加 `onEdit`。

- [ ] **Step 3: Commit**

```bash
git add FarmManagerMobile/src/screens/cost/components/RecordDetailModal.tsx
git commit -m "feat: RecordDetailModal shows debt info, payment method, and edit button"
```

---

### Task 8: 前端 — AppNavigator 支持 editRecord 参数

**Files:**
- Modify: `FarmManagerMobile/src/navigation/AppNavigator.tsx`

- [ ] **Step 1: CostCreate 路由参数加 editRecord**

更新 `RootStackParamList` 中 `CostCreate` 的参数类型：

```typescript
CostCreate: { editRecord?: CostRecord };
```

- [ ] **Step 2: Commit**

```bash
git add FarmManagerMobile/src/navigation/AppNavigator.tsx
git commit -m "feat: CostCreate route accepts editRecord parameter"
```
