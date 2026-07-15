---
last_updated: 2026-07-15
status: draft
---

# 业务运营仪表盘（管理员视角）改造

## 文档信息

| 项 | 内容 |
| --- | --- |
| 路径 | [docs/specs/2026-07-15-admin-operations-dashboard-design.md](./2026-07-15-admin-operations-dashboard-design.md) |
| 创建日期 | 2026-07-15 |
| 状态 | draft（待评审） |
| 关联前端 | `admin-web/src/pages/Dashboard/index.tsx` |
| 关联后端 | `backend/app/api/admin/dashboard.py`（新增） |

---

## 1. 背景

现有 `admin-web/src/pages/Dashboard/index.tsx` 是农户视角（周期数、天气、AI 建议、单农场收支），但 admin 后台农户不使用，**实际受众只有管理员**。需要改为管理员能看的平台运营基础数据。

管理员最基本诉求：**平台有没有人在用、有没有业务在产出**。

---

## 2. 要做的内容（基础功能）

### 2.1 顶部 4 张 KPI 卡

| 卡片 | 数据 | 备注 |
| --- | --- | --- |
| 在管农场数 | `COUNT(farm)` | 业务规模 |
| 注册用户数 | `COUNT(user)` | 用户规模 |
| 今日活跃用户 | `COUNT(user WHERE last_active_at >= today)` | 实时活跃 |
| 今日业务记录数 | `COUNT(log) + COUNT(cost)`（今日） | 业务产出 |

每张卡显示数值即可，不做同比、不做状态色。

### 2.2 一张趋势图

近 7 天每日业务记录数（农事日志 + 成本记账合计），柱状图。

---

## 3. 接口设计

### 3.1 `GET /api/admin/dashboard/summary`

返回 4 张 KPI 卡数据：

```json
{
  "farm_count": 12,
  "user_count": 35,
  "dau_today": 8,
  "records_today": 23
}
```

### 3.2 `GET /api/admin/dashboard/trend?days=7`

返回近 N 天业务记录数：

```json
{
  "days": [
    { "date": "2026-07-09", "count": 18 },
    { "date": "2026-07-10", "count": 22 }
  ]
}
```

---

## 4. 任务清单

- [ ] 后端：新增 `backend/app/api/admin/dashboard.py`，实现 `summary` 和 `trend` 两个接口
- [ ] 后端：补单测（空数据、正常两种场景）
- [ ] 前端：移除 `Dashboard/index.tsx` 中的天气、AI 建议、单农场收支模块
- [ ] 前端：接入 `summary` 接口，渲染 4 张 KPI 卡（复用 `MetricCard`）
- [ ] 前端：接入 `trend` 接口，渲染 7 天柱状图
- [ ] 联调：用 seed 数据验证渲染正常

**预估工时：1-2 天**

---

## 5. 后续（不在本期）

异常监控、治理视图、农场排行、用户角色分布等，等基础版上线观察后再决定是否做。
