# 农业记账功能优化设计

## 定位

记事本式记账，不是财务软件。核心是"记录"和"查看"，不做复杂的财务管理。

## 现有功能（保持不变）

- 收支记录 CRUD（创建、列表、删除）
- 月度资产卡片（收入/支出/结余）
- 分类管理
- AI 智能记账（自然语言解析）
- 利润统计（按种植周期）

## 新增功能

### 1. 赊账标记优化

**现状：** 只有支出能标记赊账，且赊账入口与独立 DebtCreate 页面重叠。

**改动：**
- 支出和收入都能标记"赊账"
  - 支出赊账 = "我欠别人的钱"（应付）
  - 收入赊账 = "别人欠我的钱"（应收）
- 标记赊账时填写：对方名字（counterparty）、到期日（due_date，可选）、备注
- 赊账记录用 `record_subtype` 字段标记 `"payable"` 或 `"receivable"`
- 还款时：创建一笔反向记录（应付→创建一笔支出标记已还；应收→创建一笔收入标记已收），通过 `parent_record_id` 关联

**前端改动：**
- `CostCreateScreen.tsx`：赊账开关对收入类型也生效，收入赊账标记为 `"receivable"`
- 移除独立的 `DebtCreateScreen`，统一在创建记录时标记

### 2. 赊账一览

**现状：** 赊账入口隐蔽，只能从 CycleDetail 或 ProfileScreen 间接进入。

**改动：**
- `CostListScreen` 顶部加第二个 Tab「赊账」，与「全部」并列
- 赊账 Tab 内容：
  - 顶部汇总卡片：应付总额 / 应收总额
  - 列表按对方名字分组，每组显示：对方名、应付/应收金额、最近一笔日期
  - 点击分组展开该对方名下的所有赊账记录
  - 每条记录显示：金额、日期、备注、是否已还
  - 已还清的记录灰色标记
- 数据来源：复用现有 `/debts` API，加上 `record_subtype="receivable"` 查询

**前端改动：**
- `CostListScreen.tsx`：加 Tab 切换逻辑
- 新增 `DebtTabView` 组件（替代现有 `DebtListScreen`）
- 可保留 `DebtListScreen` 但从导航中移除独立入口

### 3. 记录编辑

**现状：** 只能创建和删除，无法编辑已有记录。后端已有 `CostRecordUpdate` schema。

**改动：**
- 长按记录 → 弹出操作菜单（编辑 / 删除），替代目前只有删除
- 编辑页面复用 `CostCreateScreen`，传入已有记录数据作为初始值
- 编辑时调用 PUT `/costs/{id}`（需后端新增此端点）

**改动文件：**
- `RecordItem.tsx`：长按弹窗改为操作菜单
- `CostCreateScreen.tsx`：支持编辑模式（接收 record 参数，提交时调 PUT）
- 后端 `app/api/cost.py`：新增 PUT 端点

### 4. 搜索

**现状：** 无法按关键词搜索记录。

**改动：**
- `CostListScreen` 顶部加搜索图标，点击展开搜索框
- 搜索范围：备注（note）、对方名字（counterparty）、分类名（category）
- 前端本地过滤（已有数据在 store 中），不需要后端新 API
- 搜索结果复用现有 RecordItem 列表

**改动文件：**
- `CostListScreen.tsx`：加搜索状态和过滤逻辑

### 5. payment_method 字段

**现状：** 记录不区分支付方式。

**改动：**
- `CostRecord` 模型加 `payment_method` 字段，可选值：`cash`（现金）、`wechat`（微信）、`bank_card`（银行卡）、`debt`（赊账）
- 创建记录时默认选中上次使用的支付方式
- 记录列表项显示支付方式图标

**改动文件：**
- 后端 `app/models/cost.py`：加字段
- 后端 `app/schemas/cost.py`：加字段
- 前端 `api/types.ts`：加字段
- 前端 `CostCreateScreen.tsx`：加支付方式选择
- 前端 `RecordItem.tsx`：显示支付方式图标

## 数据模型变更

### CostRecord 新增字段

| 字段 | 类型 | 说明 |
|------|------|------|
| payment_method | String(20), nullable | 支付方式：cash/wechat/bank_card/debt |

`record_subtype` 已有字段，新增值：`"receivable"`（现有值为 `"debt"`/`"payable"`，统一为 `"payable"` 和 `"receivable"`）

## 不做的事情

- 独立账户体系 / 转账功能
- 年度汇总报表 / 图表
- 到期推送提醒
- 预算管理
- CSV/Excel 导出
- 双式记账

## 实现优先级

1. **payment_method 字段** — 后端 + 前端，最小改动
2. **记录编辑** — 高频需求
3. **赊账标记优化** — 核心痛点
4. **赊账一览** — 核心痛点
5. **搜索** — 体验提升

## 涉及文件

### 后端
- `app/models/cost.py` — 加 payment_method 字段
- `app/schemas/cost.py` — 加 payment_method 字段
- `app/api/cost.py` — 新增 PUT 端点
- `app/services/cost_service.py` — 支持更新逻辑

### 前端
- `src/screens/cost/CostListScreen.tsx` — Tab 切换 + 搜索
- `src/screens/cost/CostCreateScreen.tsx` — 编辑模式 + 赊账优化 + 支付方式
- `src/screens/cost/components/RecordItem.tsx` — 操作菜单 + 支付方式图标
- `src/screens/cost/components/DebtTabView.tsx` — 新建，赊账一览
- `src/api/types.ts` — 加 payment_method 类型
- `src/stores/costStore.ts` — 加编辑 action
- `src/api/client.ts` — 加 PUT 方法
- `src/navigation/AppNavigator.tsx` — 可选：移除独立 Debt 路由
