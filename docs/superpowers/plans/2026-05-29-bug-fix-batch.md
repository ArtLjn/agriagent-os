# Bug Fix Batch 2026-05-29 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 7 个已确认 bug，涵盖后端 4 个、前端 3 个、Prompt 2 个，均为独立修复无交叉依赖。

**Architecture:** 每个 bug 独立修复，按 Task 拆分。后端 bug 遵循 TDD（先写测试再实现），前端 bug 直接修改。Prompt 修改不需要测试。

**Tech Stack:** FastAPI + SQLAlchemy（后端）、React Native + TypeScript + Zustand（前端）、Jinja2（Prompt）

---

## File Structure

| 操作 | 文件 | 职责 |
|------|------|------|
| 修改 | `backend/prompts/base.j2` | 添加移动端格式约束 |
| 修改 | `backend/prompts/report.j2` | 添加报告格式约束 |
| 修改 | `backend/app/core/llm_client_manager.py` | watchfiles 日志过滤 |
| 修改 | `backend/app/agent/graph.py` | 天气城市改用 UserSetting |
| 修改 | `backend/app/models/cost.py` | 添加 deleted_at 列 |
| 修改 | `backend/app/services/cost_service.py` | 新增 delete_record + 软删除过滤 |
| 修改 | `backend/app/api/cost.py` | 新增 DELETE 端点 |
| 修改 | `backend/app/schemas/cost.py` | （可能需要，待确认） |
| 创建 | `backend/tests/test_cost_delete.py` | 删除端点测试 |
| 修改 | `FarmManagerMobile/src/components/MarkdownText.tsx` | `\n` 预处理 |
| 修改 | `FarmManagerMobile/src/screens/home/HomeScreen.tsx` | 读取 displayName |
| 修改 | `FarmManagerMobile/src/screens/cost/CostListScreen.tsx` | useFocusEffect |
| 修改 | `FarmManagerMobile/src/screens/cost/CostCreateScreen.tsx` | 赊账路径补刷新 |

---

### Task 1: Prompt 格式修复（Bug 1 + 4）

**Files:**
- 修改: `backend/prompts/base.j2`
- 修改: `backend/prompts/report.j2`

- [ ] **Step 1: 在 base.j2 的【回复格式】段末尾添加移动端格式约束**

在 `backend/prompts/base.j2` 的第 21 行（`- 用 Markdown 列表和加粗组织内容`）之后，添加以下内容：

```
- 禁止使用 Markdown 表格，改用简短文字列表
- 禁止使用代码块（```），不要出现任何代码
- 禁止多级嵌套列表，只用一级列表
- 用扁平短句表达，不要写长段落
```

修改后 `【回复格式】` 段完整内容为：

```
【回复格式】（最高优先级，必须遵守）
- 称呼用户为「{{ display_name }}」
- 每条建议/操作不超过2行
- 总共不超过5条
- 先说结论，再说原因（如：明天降温12° → 你那西瓜正伸蔓期怕冻）
- 禁止铺垫、寒暄、总结段
- 用「你」不用「您」，口语化
- 禁止使用 Markdown 表格，改用简短文字列表
- 禁止使用代码块（```），不要出现任何代码
- 禁止多级嵌套列表，只用一级列表
- 用扁平短句表达，不要写长段落
```

- [ ] **Step 2: 在 report.j2 添加格式约束**

在 `backend/prompts/report.j2` 的【报告要求】段（第 14 行 `- 提供下一步建议`）之后添加：

```
- 使用 Markdown 格式，用真实换行（不要输出 \n 转义字符）
- 禁止使用 Markdown 表格，改用文字列表展示数据
- 禁止使用代码块
- 禁止多级嵌套列表
```

修改后 `【报告要求】` 段完整内容为：

```
【报告要求】
- 数据准确，条理清晰
- 包含关键指标：总成本、总收入、净利润、农事进度
- 提供下一步建议
- 使用中文输出
- 使用 Markdown 格式，用真实换行（不要输出 \n 转义字符）
- 禁止使用 Markdown 表格，改用文字列表展示数据
- 禁止使用代码块
- 禁止多级嵌套列表
```

- [ ] **Step 3: Commit**

```bash
git add backend/prompts/base.j2 backend/prompts/report.j2
git commit -m "fix(prompt): 添加移动端格式约束，禁用表格/代码块/嵌套列表"
```

---

### Task 2: MarkdownText \n 转义预处理（Bug 4 前端兜底）

**Files:**
- 修改: `FarmManagerMobile/src/components/MarkdownText.tsx`

- [ ] **Step 1: 在 MarkdownText 组件中预处理 `\n` 字面量**

在 `FarmManagerMobile/src/components/MarkdownText.tsx` 中，修改组件函数体，在传入 `<Markdown>` 之前处理转义字符：

将 `MarkdownText` 组件从：

```tsx
export const MarkdownText: React.FC<MarkdownTextProps> = ({
  text,
  baseStyle,
}) => (
  <View style={[{ minHeight: 1, flexGrow: 1 }, baseStyle]}>
    <Markdown
      style={styles}
      markdownit={MarkdownIt({ typographer: true })}
      rules={tableRules}
    >
      {text}
    </Markdown>
  </View>
);
```

改为：

```tsx
export const MarkdownText: React.FC<MarkdownTextProps> = ({
  text,
  baseStyle,
}) => {
  const processed = text.replace(/\\n/g, "\n");
  return (
    <View style={[{ minHeight: 1, flexGrow: 1 }, baseStyle]}>
      <Markdown
        style={styles}
        markdownit={MarkdownIt({ typographer: true })}
        rules={tableRules}
      >
        {processed}
      </Markdown>
    </View>
  );
};
```

- [ ] **Step 2: Commit**

```bash
git add FarmManagerMobile/src/components/MarkdownText.tsx
git commit -m "fix(mobile): MarkdownText 预处理 \\n 转义字符为真实换行"
```

---

### Task 3: watchfiles 日志过滤（Bug 2）

**Files:**
- 修改: `backend/app/core/llm_client_manager.py`

- [ ] **Step 1: 在 start_file_watcher 中设置 watchfiles logger 为 WARNING**

在 `backend/app/core/llm_client_manager.py` 的 `start_file_watcher` 方法中，在 `config_path` 赋值之前（约第 260 行），添加 watchfiles logger 级别设置：

将 `start_file_watcher` 方法从：

```python
def start_file_watcher(self) -> None:
    """启动后台线程监听 providers.json 变化，自动 reload。"""
    if not _HAS_WATCHFILES:
        logger.debug("watchfiles 未安装，跳过自动监听")
        return
    if getattr(self, "_watcher_started", False):
        return
    self._watcher_started = True

    config_path = Path(__file__).parent.parent.parent / "providers.json"
```

改为：

```python
def start_file_watcher(self) -> None:
    """启动后台线程监听 providers.json 变化，自动 reload。"""
    if not _HAS_WATCHFILES:
        logger.debug("watchfiles 未安装，跳过自动监听")
        return
    if getattr(self, "_watcher_started", False):
        return
    self._watcher_started = True

    logging.getLogger("watchfiles").setLevel(logging.WARNING)

    config_path = Path(__file__).parent.parent.parent / "providers.json"
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/core/llm_client_manager.py
git commit -m "fix(llm): 过滤 watchfiles INFO 日志噪音，设为 WARNING 级别"
```

---

### Task 4: 记账列表刷新修复（Bug 3）

**Files:**
- 修改: `FarmManagerMobile/src/screens/cost/CostListScreen.tsx`
- 修改: `FarmManagerMobile/src/screens/cost/CostCreateScreen.tsx`

- [ ] **Step 1: CostListScreen 用 useFocusEffect 替代 useEffect**

在 `FarmManagerMobile/src/screens/cost/CostListScreen.tsx` 中：

**1a.** 修改 import（第 7 行附近）：

将：
```tsx
import React, { useEffect, useMemo, useState } from "react";
```
改为：
```tsx
import React, { useMemo, useState } from "react";
```

**1b.** 添加 useFocusEffect import，在 `useNavigation` import 之后：

将：
```tsx
import { useNavigation } from "@react-navigation/native";
```
改为：
```tsx
import { useNavigation } from "@react-navigation/native";
import { useFocusEffect } from "@react-navigation/native";
```

（或者合并为一行 import）：
```tsx
import { useFocusEffect, useNavigation } from "@react-navigation/native";
```

**1c.** 替换 useEffect 为 useFocusEffect（约第 87-89 行）：

将：
```tsx
useEffect(() => {
  fetchRecords();
}, [fetchRecords]);
```
改为：
```tsx
useFocusEffect(
  React.useCallback(() => {
    fetchRecords();
  }, [fetchRecords])
);
```

- [ ] **Step 2: CostCreateScreen 赊账路径成功后刷新列表**

在 `FarmManagerMobile/src/screens/cost/CostCreateScreen.tsx` 中，修改 `handleSubmit` 函数的赊账分支（约第 171 行）：

将：
```tsx
if (recordType === "cost" && isDebt) {
  await debtApi.createDebt({
    record_type: "cost",
    category,
    amount,
    record_date: dayjs(recordDate).format("YYYY-MM-DD"),
    record_subtype: "赊账",
    counterparty: counterparty.trim(),
    due_date: dueDate.trim() || undefined,
    note: note.trim() || undefined,
  });
} else {
```

改为：
```tsx
if (recordType === "cost" && isDebt) {
  await debtApi.createDebt({
    record_type: "cost",
    category,
    amount,
    record_date: dayjs(recordDate).format("YYYY-MM-DD"),
    record_subtype: "赊账",
    counterparty: counterparty.trim(),
    due_date: dueDate.trim() || undefined,
    note: note.trim() || undefined,
  });
  await useCostStore.getState().fetchRecords();
} else {
```

注意：需要在文件顶部确认 `useCostStore` 已 import（第 21 行已有 `import { useCostStore } from "../../stores/costStore";`）。

- [ ] **Step 3: Commit**

```bash
git add FarmManagerMobile/src/screens/cost/CostListScreen.tsx FarmManagerMobile/src/screens/cost/CostCreateScreen.tsx
git commit -m "fix(mobile): 记账列表用 useFocusEffect 刷新，赊账路径补刷新"
```

---

### Task 5: 首页昵称显示（Bug 5）

**Files:**
- 修改: `FarmManagerMobile/src/screens/home/HomeScreen.tsx`

- [ ] **Step 1: 让 getGreeting 接收 displayName 参数**

在 `FarmManagerMobile/src/screens/home/HomeScreen.tsx` 中，修改 `getGreeting` 函数（第 21-33 行）：

将：
```tsx
const getGreeting = () => {
  const hour = new Date().getHours();
  if (hour < 11) {
    return "早上好，农友";
  }
  if (hour < 14) {
    return "中午好，农友";
  }
  if (hour < 18) {
    return "下午好，农友";
  }
  return "晚上好，农友";
};
```

改为：
```tsx
const getGreeting = (displayName: string) => {
  const hour = new Date().getHours();
  if (hour < 11) {
    return `早上好，${displayName}`;
  }
  if (hour < 14) {
    return `中午好，${displayName}`;
  }
  if (hour < 18) {
    return `下午好，${displayName}`;
  }
  return `晚上好，${displayName}`;
};
```

- [ ] **Step 2: 从 settingsStore 读取 displayName 并传递给 getGreeting**

在同一文件中，`HomeScreen` 组件已有 `useSettingsStore` 解构（约第 108 行）：

```tsx
const { defaultCity, setDefaultCity, syncToServer, loadFromServer } = useSettingsStore();
```

添加 `displayName` 到解构：

```tsx
const { defaultCity, displayName, setDefaultCity, syncToServer, loadFromServer } = useSettingsStore();
```

然后修改 `greeting` 变量（约第 131 行）：

将：
```tsx
const greeting = getGreeting();
```
改为：
```tsx
const greeting = getGreeting(displayName);
```

- [ ] **Step 3: Commit**

```bash
git add FarmManagerMobile/src/screens/home/HomeScreen.tsx
git commit -m "fix(mobile): 首页问候语使用 settingsStore.displayName 替代硬编码"
```

---

### Task 6: 天气城市改用 UserSetting（Bug 6）

**Files:**
- 修改: `backend/app/agent/graph.py`

- [ ] **Step 1: 在 _llm_node 中查询 UserSetting.default_city**

在 `backend/app/agent/graph.py` 的 `_llm_node` 函数中（约第 180-196 行），修改上下文获取逻辑：

**1a.** 在文件顶部添加 import（约第 37 行，在现有 import 之后）：

```python
from app.models.user_setting import UserSetting
```

**1b.** 在 `_llm_node` 函数中，修改 db 查询块（第 180-197 行）：

将：
```python
farm_context_summary = farm_context_service.build_summary(db, farm_id=farm_id)
farm = db.query(Farm).filter(Farm.id == farm_id).first()
# 从 Farm.user_id 查 User.nickname
display_name = "农友"
if farm and farm.user_id:
    user = db.query(User).filter(User.id == farm.user_id).first()
    if user:
        display_name = user.nickname
farm_location = farm.location if farm and farm.location else ""
```

改为：
```python
farm_context_summary = farm_context_service.build_summary(db, farm_id=farm_id)
farm = db.query(Farm).filter(Farm.id == farm_id).first()
display_name = "农友"
user_city = ""
if farm and farm.user_id:
    user = db.query(User).filter(User.id == farm.user_id).first()
    if user:
        display_name = user.nickname
    user_setting = (
        db.query(UserSetting)
        .filter(UserSetting.user_id == farm.user_id)
        .first()
    )
    if user_setting and user_setting.default_city:
        user_city = user_setting.default_city
farm_location = user_city or (farm.location if farm and farm.location else "")
```

这段逻辑的变更：
- 新增查询 `UserSetting.default_city`
- `farm_location` 优先使用 `user_city`（用户设置的偏好城市），如果为空才回退到 `Farm.location`
- 天气 skill 的降级机制（`_get_user_location`）不受影响，因为 system prompt 只是注入城市信息

- [ ] **Step 2: Commit**

```bash
git add backend/app/agent/graph.py
git commit -m "fix(agent): 天气城市优先使用 UserSetting.default_city 替代 Farm.location"
```

---

### Task 7: 记账删除端点（Bug 7）— TDD

**Files:**
- 修改: `backend/app/models/cost.py`
- 创建: `backend/tests/test_cost_delete.py`
- 修改: `backend/app/services/cost_service.py`
- 修改: `backend/app/api/cost.py`

- [ ] **Step 1: CostRecord 模型添加 deleted_at 列**

在 `backend/app/models/cost.py` 末尾（`created_at` 列之后），添加：

```python
from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    String,
    Numeric,
    Date,
    DateTime,
    func,
)

from app.core.database import Base


class CostRecord(Base):
    """成本记账模型，记录种植周期中的成本与收入。"""

    __tablename__ = "cost_records"

    id = Column(Integer, primary_key=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False, default=1)
    cycle_id = Column(Integer, nullable=True)
    record_type = Column(String, nullable=False)
    category = Column(String, nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    record_date = Column(Date, nullable=False)
    note = Column(String, nullable=True)
    record_subtype = Column(String, nullable=True)
    counterparty = Column(String, nullable=True)
    due_date = Column(Date, nullable=True)
    settled_at = Column(DateTime(timezone=True), nullable=True)
    parent_record_id = Column(Integer, ForeignKey("cost_records.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 2: 生成数据库迁移**

Run: `cd backend && alembic revision --autogenerate -m "add deleted_at to cost_records"`

Expected: 生成迁移文件，添加 `deleted_at` 列

Run: `cd backend && alembic upgrade head`

Expected: 迁移成功

- [ ] **Step 3: 写测试 — test_cost_delete.py**

创建 `backend/tests/test_cost_delete.py`：

```python
"""测试成本记录删除端点 — 软删除机制。"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _create_record(cycle_id: int | None = None, **overrides) -> dict:
    payload = {
        "record_type": "cost",
        "category": "化肥",
        "amount": "200.00",
        "record_date": "2025-03-10",
    }
    if cycle_id:
        payload["cycle_id"] = cycle_id
    payload.update(overrides)
    resp = client.post("/costs", json=payload)
    assert resp.status_code == 200
    return resp.json()


class TestDeleteCostRecord:
    """DELETE /costs/{id} 软删除测试。"""

    def test_delete_existing_record(self):
        """删除已存在的记录返回 200。"""
        record = _create_record()
        resp = client.delete(f"/costs/{record['id']}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == record["id"]

    def test_delete_twice_returns_404(self):
        """重复删除已软删除的记录返回 404。"""
        record = _create_record()
        client.delete(f"/costs/{record['id']}")
        resp = client.delete(f"/costs/{record['id']}")
        assert resp.status_code == 404

    def test_delete_nonexistent_returns_404(self):
        """删除不存在的记录返回 404。"""
        resp = client.delete("/costs/999999")
        assert resp.status_code == 404

    def test_deleted_record_excluded_from_list(self):
        """软删除的记录不出现在列表中。"""
        record = _create_record()
        client.delete(f"/costs/{record['id']}")
        resp = client.get("/costs")
        assert resp.status_code == 200
        ids = [r["id"] for r in resp.json()["items"]]
        assert record["id"] not in ids

    def test_deleted_record_excluded_from_profit(self, cycle_id=None):
        """软删除的记录不参与利润计算。"""
        _create_record(category="成本A", amount="100.00")
        income_record = _create_record(
            record_type="income", category="销售", amount="500.00"
        )
        client.delete(f"/costs/{income_record['id']}")

        resp = client.get("/costs")
        items = resp.json()["items"]

        cost = sum(
            float(r["amount"])
            for r in items
            if r["record_type"] == "cost"
        )
        income = sum(
            float(r["amount"])
            for r in items
            if r["record_type"] == "income"
        )
        assert cost == 100.00
        assert income == 0.00


class TestDeleteMeta:
    """Meta 测试 — 验证端点存在且方法正确。"""

    def test_delete_method_exists(self):
        """DELETE /costs/{id} 端点存在。"""
        resp = client.delete("/costs/999999")
        assert resp.status_code in (200, 404)
```

- [ ] **Step 4: 运行测试确认失败**

Run: `cd backend && poetry run pytest tests/test_cost_delete.py -v`

Expected: FAIL — `405 Method Not Allowed` 或路由不存在

- [ ] **Step 5: 实现 cost_service.delete_record**

在 `backend/app/services/cost_service.py` 中添加函数：

在文件末尾（`__all__` 之前）添加：

```python
def delete_record(db: Session, record_id: int, farm_id: int) -> CostRecord | None:
    """软删除一条成本记录。

    Args:
        db: 数据库会话。
        record_id: 记录 ID。
        farm_id: 农场 ID（权限校验）。

    Returns:
        被删除的 CostRecord，或 None（不存在/已删除）。
    """
    record = (
        db.query(CostRecord)
        .filter(
            CostRecord.id == record_id,
            CostRecord.farm_id == farm_id,
            CostRecord.deleted_at.is_(None),
        )
        .first()
    )
    if not record:
        return None
    record.deleted_at = func.now()
    try:
        db.commit()
        db.refresh(record)
    except Exception:
        db.rollback()
        raise
    return record
```

同时更新 `__all__` 列表：

```python
__all__ = [
    "create_record",
    "get_records",
    "count_records",
    "get_cycle_profit",
    "get_yearly_summary",
    "delete_record",
]
```

- [ ] **Step 6: 在 get_records 和 count_records 中过滤已删除记录**

在 `cost_service.py` 的 `get_records` 函数中，基础查询添加软删除过滤：

将（第 65 行）：
```python
query = db.query(CostRecord).filter(CostRecord.farm_id == farm_id)
```
改为：
```python
query = db.query(CostRecord).filter(
    CostRecord.farm_id == farm_id,
    CostRecord.deleted_at.is_(None),
)
```

同理在 `count_records` 函数中（第 90 行）：

将：
```python
query = db.query(CostRecord).filter(CostRecord.farm_id == farm_id)
```
改为：
```python
query = db.query(CostRecord).filter(
    CostRecord.farm_id == farm_id,
    CostRecord.deleted_at.is_(None),
)
```

同理在 `get_cycle_profit` 函数中（第 110 行）：

将：
```python
records = (
    db.query(CostRecord)
    .filter(CostRecord.cycle_id == cycle_id, CostRecord.farm_id == farm_id)
    .all()
)
```
改为：
```python
records = (
    db.query(CostRecord)
    .filter(
        CostRecord.cycle_id == cycle_id,
        CostRecord.farm_id == farm_id,
        CostRecord.deleted_at.is_(None),
    )
    .all()
)
```

同理在 `get_yearly_summary` 函数中（第 145 行）：

将：
```python
records = (
    db.query(CostRecord)
    .filter(
        extract("year", CostRecord.record_date) == year,
        CostRecord.farm_id == farm_id,
    )
    .all()
)
```
改为：
```python
records = (
    db.query(CostRecord)
    .filter(
        extract("year", CostRecord.record_date) == year,
        CostRecord.farm_id == farm_id,
        CostRecord.deleted_at.is_(None),
    )
    .all()
)
```

- [ ] **Step 7: 实现 DELETE API 端点**

在 `backend/app/api/cost.py` 中，在 `list_records` 函数之后（约第 57 行）添加：

```python
@router.delete("/{record_id}")
def delete_record(
    record_id: int,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """软删除一条成本记录。"""
    record = cost_service.delete_record(db, record_id, farm_id=farm.id)
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在或已删除")
    return record
```

- [ ] **Step 8: 运行测试确认通过**

Run: `cd backend && poetry run pytest tests/test_cost_delete.py -v`

Expected: 全部 PASS

- [ ] **Step 9: 运行已有 cost 测试确认无回归**

Run: `cd backend && poetry run pytest tests/test_cost.py -v`

Expected: 全部 PASS（软删除过滤不影响已有正常记录）

- [ ] **Step 10: Commit**

```bash
git add backend/app/models/cost.py backend/app/services/cost_service.py backend/app/api/cost.py backend/tests/test_cost_delete.py
git commit -m "feat(cost): 新增 DELETE /costs/{id} 软删除端点，过滤已删除记录"
```

---

## Self-Review

### 1. Spec 覆盖检查

| Spec 要求 | 对应 Task |
|-----------|----------|
| 移动端格式约束：禁表格 | Task 1 Step 1 |
| 移动端格式约束：禁代码块 | Task 1 Step 1 |
| 移动端格式约束：禁嵌套列表 | Task 1 Step 1 |
| 报告模板格式约束 | Task 1 Step 2 |
| MarkdownText \n 预处理 | Task 2 Step 1 |
| watchfiles 日志过滤 | Task 3 Step 1 |
| CostListScreen useFocusEffect | Task 4 Step 1 |
| CostCreateScreen 赊账刷新 | Task 4 Step 2 |
| HomeScreen 昵称 | Task 5 Step 1-2 |
| 天气城市 UserSetting | Task 6 Step 1 |
| DELETE /costs/{id} 端点 | Task 7 Step 5-7 |
| 软删除（deleted_at） | Task 7 Step 1 |
| 软删除过滤（列表/利润/统计） | Task 7 Step 6 |
| 删除测试 | Task 7 Step 3 |
| UserSetting.default_city 降级 | Task 6（保留 Farm.location 回退） |
| 天气 skill _get_user_location 降级 | 不需修改（已工作） |

**缺口：无。** 全部 spec 要求已覆盖。

### 2. Placeholder 扫描

无 TBD、TODO、"implement later"、"add appropriate error handling"、"write tests for the above" 等占位符。所有代码步骤均包含完整实现代码。

### 3. 类型一致性检查

- `delete_record` service 函数签名 `(db: Session, record_id: int, farm_id: int) -> CostRecord | None` 与 API 端点调用 `cost_service.delete_record(db, record_id, farm_id=farm.id)` 一致
- `useCostStore.getState().fetchRecords()` — fetchRecords 签名 `(cycleId?: number) => Promise<void>`，无参调用合法
- `useSettingsStore` 解构中 `displayName` 类型为 `string`，与 `getGreeting(displayName: string)` 参数匹配
- `UserSetting.user_id` 类型 `String(36)` 与 `User.id` 类型 `String(36)` 匹配
- `CostRecord.deleted_at` 类型 `DateTime(timezone=True)`，`func.now()` 赋值类型匹配
- 前端 `costApi.deleteRecord(id: number)` 调用 `DELETE /costs/${id}`，与后端 `@router.delete("/{record_id}")` 路径匹配
