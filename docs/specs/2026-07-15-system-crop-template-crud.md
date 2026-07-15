---
last_updated: 2026-07-15
status: draft
---

# 系统作物模版 CRUD 补全

## 文档信息

| 项 | 内容 |
| --- | --- |
| 路径 | [docs/specs/2026-07-15-system-crop-template-crud.md](./2026-07-15-system-crop-template-crud.md) |
| 创建日期 | 2026-07-15 |
| 状态 | draft（待评审） |
| 关联后端 | [backend/app/api/crop.py](../../backend/app/api/crop.py)、[backend/app/services/crop_service.py](../../backend/app/services/crop_service.py) |
| 关联前端 | [admin-web/src/pages/CropTemplates/SystemLibrary.tsx](../../admin-web/src/pages/CropTemplates/SystemLibrary.tsx)、[admin-web/src/api/crops.ts](../../admin-web/src/api/crops.ts) |

---

## 1. 背景

### 1.1 现状

系统作物模版（`crop_templates.farm_id IS NULL`）目前只能通过改 Python seed 代码维护：

- 数据来源：[backend/app/seed/system_crop_templates.py](../../backend/app/seed/system_crop_templates.py) 硬编码 10 种作物
- 数据生命周期：写代码 → Alembic 迁移 → 灌库；运营/农艺师无法在 admin-web 自助维护

### 1.2 现有 API 能力盘点

[backend/app/api/crop.py](../../backend/app/api/crop.py) 当前接口：

| 接口 | 系统模版可用 | 说明 |
| --- | --- | --- |
| `POST /crops/templates` | 否 | 强制绑定当前 `farm.id`，只能创建农场副本 |
| `GET /crops/templates/system` | 是 | 列表只读 |
| `POST /crops/templates/system/{id}/import` | 是 | 导入到当前农场 |
| `GET /crops/templates/{id}` | 是 | 详情 |
| `PUT /crops/templates/{id}` | **403 拒绝** | [crop.py:127-128](../../backend/app/api/crop.py#L127-L128) 显式拦系统模版 |
| `DELETE /crops/templates/{id}` | **403 拒绝** | [crop.py:144-145](../../backend/app/api/crop.py#L144-L145) 显式拦系统模版 |

**缺口**：系统模版的**新建、编辑、删除** 3 个写操作无任何入口。

### 1.3 前端能力盘点

[admin-web/src/pages/CropTemplates/SystemLibrary.tsx](../../admin-web/src/pages/CropTemplates/SystemLibrary.tsx)：

- 工具栏（[:141-167](../../admin-web/src/pages/CropTemplates/SystemLibrary.tsx#L141-L167)）：只有「分类筛选 / 导入所选 / 刷新」3 个动作
- 表格列（[:101-133](../../admin-web/src/pages/CropTemplates/SystemLibrary.tsx#L101-L133)）：ID / 名称 / 分类 / 品种 / 生长阶段；**无操作列**
- [admin-web/src/api/crops.ts](../../admin-web/src/api/crops.ts) 只声明了 `listSystemCropTemplates` 和 `importSystemCropTemplate`

**缺口**：admin-web 完全没有系统模版写操作 UI 和 API 调用函数。

### 1.4 为什么现在做

- 每加一种作物都要改 Python 代码 + 跑迁移 → 农艺师无法自助
- 改一个错别字也要走研发流程 → 摩擦大
- seed 文件越来越长 → 维护成本线性增长

---

## 2. 设计目标

| 目标 | 衡量标准 |
| --- | --- |
| **后端 3 个写接口** | 系统模版的新建 / 编辑 / 删除均能通过 API 完成 |
| **前端 3 个入口** | SystemLibrary 页面有「新建」「编辑」「删除」按钮且功能跑通 |
| **不破坏现有约束** | 农场副本的写接口继续拒绝系统模版（403 边界保留） |
| **删除安全性** | 已被农场导入的系统模版不可直接物理删除 |
| **复用现有表单** | 编辑表单与农场副本编辑表单保持一致体验 |

---

## 3. 详细设计

### 3.1 后端接口

新增 3 个端点（命名与现有 `system` 子路径一致）：

#### `POST /crops/templates/system`

创建系统模版，`farm_id=NULL`。

```python
@router.post("/templates/system", response_model=CropTemplateResponse, status_code=201)
def create_system_template(template: CropTemplateCreate, db: Session = Depends(get_db)):
    duplicate = crop_service.find_system_template_duplicate(db, name=template.name, variety=template.variety)
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="同名同品种的系统模版已存在")
    return crop_service.create_crop_template(db, template, farm_id=None)
```

去重检查复用现有索引 `ix_crop_templates_farm_name_variety`（`farm_id IS NULL` + `name` + `variety`）。

#### `PUT /crops/templates/system/{template_id}`

修改系统模版（含 stages 全量替换）。

```python
@router.put("/templates/system/{template_id}", response_model=CropTemplateResponse)
def update_system_template(template_id: int, template: CropTemplateCreate, db: Session = Depends(get_db)):
    if crop_service.get_system_template(db, template_id) is None:
        raise HTTPException(status_code=404, detail="系统模版不存在")
    return crop_service.update_crop_template(db, template_id, template, farm_id=None)
```

注意 [crop_service.update_crop_template](../../backend/app/services/crop_service.py) 当前签名要求 `farm_id`，需要支持 `farm_id=None` 的系统模版分支。

#### `DELETE /crops/templates/system/{template_id}`

删除系统模版。

```python
@router.delete("/templates/system/{template_id}")
def delete_system_template(template_id: int, db: Session = Depends(get_db)):
    if crop_service.get_system_template(db, template_id) is None:
        raise HTTPException(status_code=404, detail="系统模版不存在")
    # 检查是否已被农场导入
    farm_count = crop_service.count_farm_imports(db, system_template_id=template_id)
    if farm_count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"已有 {farm_count} 个农场导入了该模版，禁止删除；请先通知相关农场改用其他模版"
        )
    crop_service.delete_crop_template(db, template_id, farm_id=None)
    return {"message": "删除成功"}
```

**删除策略选择**：采用「已被导入则拒绝」而非级联删除，避免影响已使用该模版的农场计划。统计"农场副本"的依据是 `name + variety + farm_id IS NOT NULL`（导入逻辑生成的副本会保留同名同品种）。

#### 关于鉴权

现有 `/templates/system` GET 接口和 `/templates/system/{id}/import` POST 接口都没有管理员鉴权（仅靠 `get_current_farm` 取当前管理员的农场身份）。本次新增的 3 个写接口**沿用相同策略**，不引入新的鉴权层。

理由：

- admin-web 整体是运营后台，登录即可视为有权限
- 鉴权模型独立演进，不耦合本次 CRUD
- 后端 `users.role` 字段已有 admin/普通用户二分，未来如需收口，统一加 dependency 即可

### 3.2 Service 层

[crop_service.py](../../backend/app/services/crop_service.py) 需要的改动：

| 方法 | 改动 |
| --- | --- |
| `create_crop_template(db, template, farm_id)` | 已存在，确认支持 `farm_id=None` |
| `update_crop_template(db, template_id, template, farm_id)` | 当前按 `farm_id` 过滤，需增加 `farm_id=None` 分支 |
| `delete_crop_template(db, template_id, farm_id)` | 同上 |
| `find_system_template_duplicate(db, name, variety)` | **新增**，用于 POST 去重 |
| `count_farm_imports(db, system_template_id)` | **新增**，用于 DELETE 前置检查（按 name+variety 匹配农场副本） |
| `get_system_template` | 已存在 |

### 3.3 前端 API 层

[admin-web/src/api/crops.ts](../../admin-web/src/api/crops.ts) 新增 3 个函数：

```typescript
export async function createSystemTemplate(payload: CropTemplatePayload): Promise<CropTemplate> {
  const res = await httpClient.post('/crops/templates/system', payload);
  return res.data;
}

export async function updateSystemTemplate(id: number, payload: CropTemplatePayload): Promise<CropTemplate> {
  const res = await httpClient.put(`/crops/templates/system/${id}`, payload);
  return res.data;
}

export async function deleteSystemTemplate(id: number): Promise<void> {
  await httpClient.delete(`/crops/templates/system/${id}`);
}
```

### 3.4 前端页面

[SystemLibrary.tsx](../../admin-web/src/pages/CropTemplates/SystemLibrary.tsx) 改造：

#### 工具栏新增「新建系统模版」按钮

```tsx
<Button type="primary" icon={<PlusOutlined />} onClick={openCreateModal}>
  新建模版
</Button>
```

#### 表格新增「操作」列

```tsx
{
  title: '操作',
  key: 'action',
  width: 160,
  render: (_, record) => (
    <Space>
      <Button size="small" onClick={() => openEditModal(record)}>编辑</Button>
      <Popconfirm title="确认删除？" onConfirm={() => handleDelete(record.id)}>
        <Button size="small" danger>删除</Button>
      </Popconfirm>
    </Space>
  ),
}
```

#### 抽离共享表单组件

当前农场模版编辑表单内联在 [pages/Crops/index.tsx:222-272](../../admin-web/src/pages/Crops/index.tsx#L222-L272) 的 Modal 中。抽离为 `pages/CropTemplates/TemplateForm.tsx`，被 `Crops/index.tsx` 和 `SystemLibrary.tsx` 共同复用。

字段保持现有 5 个（name / variety / category / stages[name, duration_days, order_index, key_tasks]），不引入新字段。

#### 删除失败的提示

后端返回 409 时，前端 `message.error` 显示后端 detail 文案，让运营知道"已有 N 个农场导入"的具体阻塞原因。

### 3.5 不在本次范围

- 字段扩展（温湿度/光照/施肥等）——属于独立的"模版能力升级"需求
- 数据来源 / 审核状态 / 版本号 ——属于独立的"数据治理"需求
- 移动端改造 ——系统模版管理只走 admin-web
- 鉴权模型升级（admin/普通用户区分）——独立需求
- seed 脚本废弃 ——保留作为初稿数据，CRUD 上线后增量维护

---

## 4. 实施步骤

| Step | 内容 | 验收 |
| --- | --- | --- |
| **S1** | service 层：新增 `find_system_template_duplicate`、`count_farm_imports`；改造 `update/delete_crop_template` 支持 `farm_id=None` | 单测覆盖系统模版分支 |
| **S2** | API 层：新增 3 个 `/templates/system` 写端点 | pytest 接口测试通过 |
| **S3** | 前端 API：`crops.ts` 新增 3 个函数 | 类型检查通过 |
| **S4** | 抽离 `TemplateForm.tsx` 共享表单组件，改造 `Crops/index.tsx` 引用 | 农场副本编辑功能回归通过 |
| **S5** | `SystemLibrary.tsx`：新建按钮、操作列、删除二次确认 | 手测新建/编辑/删除全链路通过 |
| **S6** | 文档同步：[docs/reference/api-spec.yaml](../reference/api-spec.yaml) + `bash scripts/check-doc-freshness.sh` | 文档新鲜度检查通过 |

预计工作量：**2 天**。

---

## 5. 验收标准

### 5.1 后端

- [ ] `POST /crops/templates/system` 能创建系统模版，重复创建返回 409
- [ ] `PUT /crops/templates/system/{id}` 能修改系统模版（含 stages 全量替换）
- [ ] `DELETE /crops/templates/system/{id}` 能删除未被导入的系统模版
- [ ] `DELETE` 已被导入的系统模版返回 409，detail 提示农场数量
- [ ] 农场副本接口 `PUT/DELETE /templates/{id}` 对系统模版仍然返回 403（不破坏现有约束）
- [ ] pytest 单测覆盖以上分支

### 5.2 前端

- [ ] SystemLibrary 页面工具栏有「新建模版」按钮
- [ ] 表格每行有「编辑」「删除」操作
- [ ] 新建/编辑表单字段与农场副本编辑一致
- [ ] 删除二次确认，删除失败有明确文案
- [ ] Crops 农场副本编辑功能回归正常（抽离组件未破坏原逻辑）

### 5.3 文档与规则

- [ ] [docs/reference/api-spec.yaml](../reference/api-spec.yaml) 新增 3 个系统模版写接口
- [ ] `bash scripts/check-doc-freshness.sh` 通过
- [ ] `bash scripts/check-layer-deps.sh` 通过
- [ ] `bash scripts/check-complexity-budget.sh` 通过

---

## 6. 风险与回滚

| 风险 | 缓解 | 回滚 |
| --- | --- | --- |
| 误删已导入的系统模版 | 删除前 `count_farm_imports` 检查，已导入则 409 | 删除是软兜底，真删需运营手动确认 |
| 抽离共享表单组件影响农场副本编辑 | S4 单独成步，单独回归 | 回滚 `TemplateForm.tsx` 抽离 |
| service 改造影响农场副本分支 | 单测覆盖 `farm_id=None` 和 `farm_id=<farm>` 两条路径 | 保留旧分支逻辑，新分支用 if 区分 |

---

## 7. 开放问题

| # | 问题 | 默认决策 |
| --- | --- | --- |
| 1 | 系统模版是否需要"软删除"标记而非物理删除？ | 默认物理删除（已被导入的场景由 409 拦住） |
| 2 | 编辑系统模版后，已导入到农场的副本是否同步更新？ | 默认不同步（副本独立，避免影响农场既有计划） |
| 3 | 是否记录"谁创建/修改了系统模版"的审计日志？ | 本次不做，依赖结构化日志兜底 |
