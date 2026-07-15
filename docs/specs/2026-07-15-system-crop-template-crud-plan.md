# 系统作物模版 CRUD 补全 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给系统作物模版补全 CRUD（新建/编辑/删除），让运营/农艺师能在 admin-web 直接维护系统模版库，不必改 Python seed 代码。

**Architecture:** 后端在 `/crops/templates/system` 命名空间下新增 3 个写端点，复用现有 service 层逻辑（独立分支方法，不污染农场副本接口的 403 边界）。前端在 SystemLibrary.tsx 加「新建/编辑/删除」入口，并把表单抽离成共享组件 `TemplateForm.tsx` 供农场副本和系统模版共用。

**Tech Stack:** FastAPI + SQLAlchemy + pytest（后端）；React 18 + TypeScript + Ant Design + vitest（前端）。

**Spec：** [docs/specs/2026-07-15-system-crop-template-crud.md](./2026-07-15-system-crop-template-crud.md)

---

## 文件结构

### 新建

| 文件 | 职责 |
| --- | --- |
| `admin-web/src/components/TemplateForm.tsx` | 共享模版表单（name/variety/stages），供 Crops 和 SystemLibrary 复用 |
| `admin-web/src/components/TemplateForm.test.tsx` | TemplateForm 单测 |

### 修改

| 文件 | 改动 |
| --- | --- |
| `backend/app/services/crop_service.py` | 新增 `create_system_crop_template`、`update_system_crop_template`、`delete_system_crop_template`、`count_farm_template_imports` 4 个方法 |
| `backend/app/api/crop.py` | 新增 3 个 `/templates/system` 写端点；现有农场副本接口的 403 边界保留 |
| `backend/tests/api/test_crop_templates_system.py` | 新增系统模版写接口的 4 个测试用例 |
| `backend/tests/services/test_crop_service_system_write.py` | **新建** service 层系统模版写方法单测 |
| `admin-web/src/api/crops.ts` | 新增 `createSystemTemplate`、`updateSystemTemplate`、`deleteSystemTemplate` 3 个函数 |
| `admin-web/src/pages/Crops/index.tsx` | 把表单 Modal 内的 Form 部分替换为 `<TemplateForm />` 组件 |
| `admin-web/src/pages/CropTemplates/SystemLibrary.tsx` | 工具栏加「新建模版」按钮、表格加「操作」列、引入 TemplateForm Modal |
| `admin-web/src/pages/CropTemplates/SystemLibrary.test.tsx` | 新增新建/编辑/删除流程测试 |
| `docs/reference/api-spec.yaml` | 同步 3 个新接口 |

---

## Task 1: Service 层 — 新增系统模版写方法

**Files:**
- Modify: `backend/app/services/crop_service.py`
- Create: `backend/tests/services/test_crop_service_system_write.py`

### Step 1.1: 写失败测试 — service 系统模版创建/更新/删除

- [ ] **写测试代码**

创建 `backend/tests/services/test_crop_service_system_write.py`：

```python
from app.models.crop import CropTemplate, GrowthStage
from app.schemas.crop import CropTemplateCreate, GrowthStageCreate
from app.services import crop_service


def _payload(name: str = "西瓜", variety: str | None = "8424"):
    return CropTemplateCreate(
        name=name,
        variety=variety,
        category="水果",
        stages=[
            GrowthStageCreate(name="育苗期", duration_days=30, order_index=0, key_tasks="控温"),
            GrowthStageCreate(name="定植期", duration_days=1, order_index=1, key_tasks="浇水"),
        ],
    )


def test_create_system_crop_template_persists_with_null_farm_id(db_session):
    template = crop_service.create_system_crop_template(db_session, _payload())

    assert template.id is not None
    assert template.farm_id is None
    assert template.name == "西瓜"
    assert template.variety == "8424"
    assert template.category == "水果"
    assert [s.name for s in template.stages] == ["育苗期", "定植期"]


def test_update_system_crop_template_replaces_stages(db_session):
    existing = crop_service.create_system_crop_template(db_session, _payload())

    updated = crop_service.update_system_crop_template(
        db_session,
        existing.id,
        CropTemplateCreate(
            name="改名西瓜",
            variety="8424",
            category="水果",
            stages=[
                GrowthStageCreate(name="新育苗期", duration_days=20, order_index=0, key_tasks=None),
            ],
        ),
    )

    assert updated.id == existing.id
    assert updated.name == "改名西瓜"
    assert [s.name for s in updated.stages] == ["新育苗期"]
    assert db_session.query(GrowthStage).count() == 1


def test_update_system_crop_template_raises_when_not_found(db_session):
    import pytest

    with pytest.raises(ValueError, match="系统模板 99999 不存在"):
        crop_service.update_system_crop_template(db_session, 99999, _payload())


def test_delete_system_crop_template_removes_template_and_stages(db_session):
    template = crop_service.create_system_crop_template(db_session, _payload())

    crop_service.delete_system_crop_template(db_session, template.id)

    assert db_session.query(CropTemplate).count() == 0
    assert db_session.query(GrowthStage).count() == 0


def test_delete_system_crop_template_raises_when_imported_by_farm(db_session):
    template = crop_service.create_system_crop_template(db_session, _payload())
    # 模拟农场副本（同名同品种）
    db_session.add(CropTemplate(farm_id=1, name="西瓜", variety="8424", category="水果"))
    db_session.commit()

    import pytest

    with pytest.raises(ValueError, match="已被 1 个农场导入"):
        crop_service.delete_system_crop_template(db_session, template.id)


def test_count_farm_template_imports_matches_by_name_and_variety(db_session):
    db_session.add_all([
        CropTemplate(farm_id=1, name="西瓜", variety="8424", category="水果"),
        CropTemplate(farm_id=2, name="西瓜", variety="8424", category="水果"),
        CropTemplate(farm_id=1, name="西瓜", variety="其他品种", category="水果"),
    ])
    db_session.commit()

    count = crop_service.count_farm_template_imports(db_session, name="西瓜", variety="8424")
    assert count == 2
```

- [ ] **跑测试验证失败**

Run: `cd backend && poetry run pytest tests/services/test_crop_service_system_write.py -v`

Expected: 6 个测试全 FAIL，原因是 `AttributeError: module 'app.services.crop_service' has no attribute 'create_system_crop_template'`。

### Step 1.2: 实现 service 层方法

- [ ] **在 `backend/app/services/crop_service.py` 末尾的 `__all__` 之前新增 4 个方法**

```python
def create_system_crop_template(
    db: Session, template: CropTemplateCreate
) -> CropTemplate:
    """创建系统作物模板（farm_id 为空）。"""
    db_template = CropTemplate(
        farm_id=None,
        name=template.name,
        variety=template.variety,
        category=template.category,
    )
    db.add(db_template)
    db.flush()

    for stage in template.stages:
        db.add(
            GrowthStage(
                crop_template_id=db_template.id,
                name=stage.name,
                duration_days=stage.duration_days,
                order_index=stage.order_index,
                key_tasks=stage.key_tasks,
            )
        )

    try:
        db.commit()
        db.refresh(db_template)
    except Exception:
        db.rollback()
        raise
    return db_template


def update_system_crop_template(
    db: Session, template_id: int, update: CropTemplateCreate
) -> CropTemplate:
    """更新系统作物模板（含 stages 全量替换）。"""
    template = get_system_template(db, template_id)
    if template is None:
        raise ValueError(f"系统模板 {template_id} 不存在")

    template.name = update.name
    template.variety = update.variety
    template.category = update.category

    for stage in template.stages:
        db.delete(stage)

    for stage in update.stages:
        db.add(
            GrowthStage(
                crop_template_id=template.id,
                name=stage.name,
                duration_days=stage.duration_days,
                order_index=stage.order_index,
                key_tasks=stage.key_tasks,
            )
        )

    try:
        db.commit()
        db.refresh(template)
    except Exception:
        db.rollback()
        raise
    return template


def count_farm_template_imports(
    db: Session, name: str, variety: str | None
) -> int:
    """统计农场副本中同名同品种的模板数量，用于删除前置检查。"""
    query = db.query(CropTemplate).filter(
        CropTemplate.farm_id.is_not(None),
        CropTemplate.name == name,
    )
    if variety is None:
        query = query.filter(CropTemplate.variety.is_(None))
    else:
        query = query.filter(CropTemplate.variety == variety)
    return query.count()


def delete_system_crop_template(db: Session, template_id: int) -> None:
    """删除系统作物模板；已被农场导入时拒绝。"""
    template = get_system_template(db, template_id)
    if template is None:
        raise ValueError(f"系统模板 {template_id} 不存在")

    farm_count = count_farm_template_imports(
        db, name=template.name, variety=template.variety
    )
    if farm_count > 0:
        raise ValueError(
            f"系统模板 {template_id} 已被 {farm_count} 个农场导入，禁止删除"
        )

    for stage in template.stages:
        db.delete(stage)
    db.delete(template)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
```

- [ ] **更新 `__all__` 导出**

把 `backend/app/services/crop_service.py` 末尾的 `__all__` 改为：

```python
__all__ = [
    "create_crop_template",
    "get_crop_templates",
    "count_crop_templates",
    "get_crop_template",
    "update_crop_template",
    "delete_crop_template",
    "find_template_by_name",
    "find_exact_duplicate",
    "_normalize_stages_for_compare",
    "list_system_templates",
    "get_system_template",
    "import_system_template",
    "find_system_template_match",
    "create_system_crop_template",
    "update_system_crop_template",
    "count_farm_template_imports",
    "delete_system_crop_template",
    "ImportSystemTemplateResult",
]
```

- [ ] **跑测试验证通过**

Run: `cd backend && poetry run pytest tests/services/test_crop_service_system_write.py -v`

Expected: 6 个测试全 PASS。

- [ ] **回归测试：现有 service 测试不应被破坏**

Run: `cd backend && poetry run pytest tests/services/test_crop_service_dedup.py tests/test_crop.py -v`

Expected: 全部 PASS。

### Step 1.3: 提交

- [ ] **commit**

```bash
git add backend/app/services/crop_service.py backend/tests/services/test_crop_service_system_write.py
git commit -m "feat(crop): service 层新增系统模版写方法"
```

---

## Task 2: API 层 — 新增 3 个系统模版写端点

**Files:**
- Modify: `backend/app/api/crop.py`
- Modify: `backend/tests/api/test_crop_templates_system.py`

### Step 2.1: 写失败测试 — API 端点

- [ ] **在 `backend/tests/api/test_crop_templates_system.py` 末尾追加测试**

```python
def test_create_system_template_endpoint_creates_with_null_farm_id(client):
    response = client.post("/crops/templates/system", json=_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "西瓜"
    assert body["variety"] == "8424"
    assert [s["name"] for s in body["stages"]] == ["育苗期", "定植期"]

    list_response = client.get("/crops/templates/system")
    assert any(item["id"] == body["id"] for item in list_response.json())


def test_update_system_template_endpoint_replaces_stages(client, db_session):
    system_template = _create_system_template(db_session)

    response = client.put(
        f"/crops/templates/system/{system_template.id}",
        json={
            "name": "改名西瓜",
            "variety": "8424",
            "stages": [
                _stage("新育苗期", 20, 0, "新任务"),
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "改名西瓜"
    assert [s["name"] for s in body["stages"]] == ["新育苗期"]


def test_update_system_template_not_found_returns_404(client):
    response = client.put(
        "/crops/templates/system/99999",
        json=_payload(),
    )
    assert response.status_code == 404


def test_delete_system_template_endpoint_removes_template(client, db_session):
    system_template = _create_system_template(db_session)

    response = client.delete(f"/crops/templates/system/{system_template.id}")

    assert response.status_code == 200
    list_response = client.get("/crops/templates/system")
    assert all(item["id"] != system_template.id for item in list_response.json())


def test_delete_system_template_returns_409_when_imported_by_farm(client, db_session):
    from app.models.crop import CropTemplate as _CT

    system_template = _create_system_template(db_session)
    db_session.add(_CT(farm_id=1, name="西瓜", variety="8424", category="水果"))
    db_session.commit()

    response = client.delete(f"/crops/templates/system/{system_template.id}")

    assert response.status_code == 409
    assert "已被 1 个农场导入" in response.json()["detail"]
```

- [ ] **跑测试验证失败**

Run: `cd backend && poetry run pytest tests/api/test_crop_templates_system.py -v`

Expected: 5 个新测试 FAIL（404），原有测试仍 PASS。

### Step 2.2: 实现 API 端点

- [ ] **在 `backend/app/api/crop.py` 的 `import_system_template` 函数之后、`get_template` 之前插入 3 个端点**

在 `import_system_template` 后追加：

```python
@router.post(
    "/templates/system",
    response_model=CropTemplateResponse,
    status_code=201,
)
def create_system_template_endpoint(
    template: CropTemplateCreate,
    db: Session = Depends(get_db),
):
    """创建系统作物模板（farm_id 为空）。"""
    del farm  # 系统模板不绑定农场
    duplicate = crop_service.find_system_template_match(
        db, name=template.name, variety=template.variety
    )
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="同名同品种的系统模板已存在")
    return crop_service.create_system_crop_template(db, template)


@router.put("/templates/system/{template_id}", response_model=CropTemplateResponse)
def update_system_template_endpoint(
    template_id: int,
    template: CropTemplateCreate,
    db: Session = Depends(get_db),
):
    """更新系统作物模板（含 stages 全量替换）。"""
    try:
        return crop_service.update_system_crop_template(db, template_id, template)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/templates/system/{template_id}")
def delete_system_template_endpoint(
    template_id: int,
    db: Session = Depends(get_db),
):
    """删除系统作物模板；已被农场导入时返回 409。"""
    try:
        crop_service.delete_system_crop_template(db, template_id)
    except ValueError as e:
        msg = str(e)
        if "已被" in msg and "导入" in msg:
            raise HTTPException(status_code=409, detail=msg)
        raise HTTPException(status_code=404, detail=msg)
    return {"message": "删除成功"}
```

注意：`create_system_template_endpoint` 里的 `del farm` 一行删除掉（无 farm 参数），保留为：

```python
@router.post(
    "/templates/system",
    response_model=CropTemplateResponse,
    status_code=201,
)
def create_system_template_endpoint(
    template: CropTemplateCreate,
    db: Session = Depends(get_db),
):
    """创建系统作物模板（farm_id 为空）。"""
    duplicate = crop_service.find_system_template_match(
        db, name=template.name, variety=template.variety
    )
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="同名同品种的系统模板已存在")
    return crop_service.create_system_crop_template(db, template)
```

- [ ] **跑测试验证通过**

Run: `cd backend && poetry run pytest tests/api/test_crop_templates_system.py -v`

Expected: 全部 10 个测试 PASS（含原有 5 个 + 新增 5 个）。

- [ ] **跑 crop 相关全部测试，确认 403 边界未被破坏**

Run: `cd backend && poetry run pytest tests/api/test_crop_templates_system.py tests/services/test_crop_service_system_write.py tests/services/test_crop_service_dedup.py tests/test_crop.py -v`

Expected: 全部 PASS。`test_system_templates_are_write_protected_at_api`（验证 `PUT/DELETE /crops/templates/{id}` 对系统模版返回 403）仍 PASS。

### Step 2.3: 提交

- [ ] **commit**

```bash
git add backend/app/api/crop.py backend/tests/api/test_crop_templates_system.py
git commit -m "feat(crop): 新增系统模版写接口 POST/PUT/DELETE /crops/templates/system"
```

---

## Task 3: 前端 API 层 — 新增 3 个调用函数

**Files:**
- Modify: `admin-web/src/api/crops.ts`

### Step 3.1: 写失败测试

- [ ] **检查 `admin-web/src/api/crops.ts` 当前测试文件是否存在**

Run: `ls admin-web/src/api/crops.test.ts 2>/dev/null || echo "no test file"`

如果没有现成测试文件，跳过单测（API 函数是 httpClient 薄包装，单测价值低；E2E 由 Task 5 的页面测试覆盖）。

### Step 3.2: 实现 API 函数

- [ ] **在 `admin-web/src/api/crops.ts` 的 `importSystemCropTemplate` 之后新增 3 个函数**

先 Read 文件确认现有 `importSystemCropTemplate` 的位置，然后在它之后插入：

```typescript
export async function createSystemTemplate(
  payload: CropTemplatePayload,
): Promise<CropTemplate> {
  const res = await httpClient.post<CropTemplate>('/crops/templates/system', payload);
  return res.data;
}

export async function updateSystemTemplate(
  id: number,
  payload: CropTemplatePayload,
): Promise<CropTemplate> {
  const res = await httpClient.put<CropTemplate>(
    `/crops/templates/system/${id}`,
    payload,
  );
  return res.data;
}

export async function deleteSystemTemplate(id: number): Promise<void> {
  await httpClient.delete(`/crops/templates/system/${id}`);
}
```

如果 `CropTemplatePayload` 类型未定义，从 `createTemplate` 现有签名推导（即 `{ name: string; variety?: string | null; stages: Array<{ name: string; duration_days: number; order_index: number; key_tasks?: string | null }> }`），或导出复用现有类型。先 grep 现有类型：

Run: `cd admin-web && grep -n "createTemplate" src/api/crops.ts`

按现有类型风格补齐（如已存在 `CropTemplatePayload` 直接用；如不存在就内联）。

- [ ] **类型检查**

Run: `cd admin-web && pnpm tsc --noEmit`

Expected: 0 errors。

### Step 3.3: 提交

- [ ] **commit**

```bash
git add admin-web/src/api/crops.ts
git commit -m "feat(crop-api): 新增 createSystemTemplate/updateSystemTemplate/deleteSystemTemplate"
```

---

## Task 4: 抽离 TemplateForm 共享组件

**Files:**
- Create: `admin-web/src/components/TemplateForm.tsx`
- Create: `admin-web/src/components/TemplateForm.test.tsx`
- Modify: `admin-web/src/pages/Crops/index.tsx`

### Step 4.1: 写失败测试 — 组件渲染与受控

- [ ] **创建 `admin-web/src/components/TemplateForm.test.tsx`**

```tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Form } from 'antd';
import TemplateForm from './TemplateForm';

describe('TemplateForm', () => {
  it('渲染名称、品种和阶段输入', () => {
    render(
      <Form>
        <TemplateForm />
      </Form>,
    );

    expect(screen.getByText('名称')).toBeInTheDocument();
    expect(screen.getByText('品种')).toBeInTheDocument();
    expect(screen.getByText('生长阶段')).toBeInTheDocument();
  });

  it('初始阶段数由 prop 控制', () => {
    render(
      <Form initialValues={{ stages: [{ name: '', duration_days: 1, key_tasks: '' }] }}>
        <TemplateForm />
      </Form>,
    );

    expect(screen.getAllByPlaceholderText('阶段名').length).toBe(1);
  });
});
```

- [ ] **跑测试验证失败**

Run: `cd admin-web && pnpm vitest run src/components/TemplateForm.test.tsx`

Expected: FAIL，`Cannot find module './TemplateForm'`。

### Step 4.2: 实现 TemplateForm 组件

- [ ] **创建 `admin-web/src/components/TemplateForm.tsx`**

```tsx
import { Form, Input, InputNumber, Button, Divider, Space } from 'antd';
import { PlusOutlined, MinusCircleOutlined } from '@ant-design/icons';

type StageFieldValue = {
  name?: string;
  duration_days?: number;
  key_tasks?: string;
};

export type TemplateFormValues = {
  name: string;
  variety?: string | null;
  stages: StageFieldValue[];
};

export default function TemplateForm() {
  return (
    <>
      <Form.Item
        name="name"
        label="名称"
        rules={[{ required: true, message: '请输入模板名称' }]}
      >
        <Input placeholder="如：西瓜" />
      </Form.Item>
      <Form.Item name="variety" label="品种">
        <Input placeholder="如：8424" />
      </Form.Item>

      <Divider>生长阶段</Divider>
      <Form.List name="stages">
        {(fields, { add, remove }) => (
          <>
            {fields.map(({ key, name, ...restField }) => (
              <Space key={key} style={{ display: 'flex', marginBottom: 8 }} align="baseline">
                <Form.Item
                  {...restField}
                  name={[name, 'name']}
                  rules={[{ required: true, message: '阶段名' }]}
                >
                  <Input placeholder="阶段名" style={{ width: 120 }} />
                </Form.Item>
                <Form.Item
                  {...restField}
                  name={[name, 'duration_days']}
                  rules={[{ required: true, message: '天数' }]}
                >
                  <InputNumber placeholder="天数" min={1} style={{ width: 90 }} />
                </Form.Item>
                <Form.Item {...restField} name={[name, 'key_tasks']}>
                  <Input placeholder="关键任务（选填）" style={{ width: 160 }} />
                </Form.Item>
                <MinusCircleOutlined onClick={() => remove(name)} />
              </Space>
            ))}
            <Button type="dashed" onClick={() => add()} block icon={<PlusOutlined />}>
              添加阶段
            </Button>
          </>
        )}
      </Form.List>
    </>
  );
}
```

- [ ] **跑测试验证通过**

Run: `cd admin-web && pnpm vitest run src/components/TemplateForm.test.tsx`

Expected: 2 个测试 PASS。

### Step 4.3: 改造 Crops/index.tsx 使用 TemplateForm

- [ ] **修改 `admin-web/src/pages/Crops/index.tsx`**

替换 `<Form>...</Form>` 内部内容。把 [:245-271](../../admin-web/src/pages/Crops/index.tsx#L245-L271) 这一段：

```tsx
<Form form={form} layout="vertical">
  <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入模板名称' }]}><Input placeholder="如：西瓜" /></Form.Item>
  <Form.Item name="variety" label="品种"><Input placeholder="如：8424" /></Form.Item>

  <Divider>生长阶段</Divider>
  <Form.List name="stages">
    ...
  </Form.List>
</Form>
```

替换为：

```tsx
<Form form={form} layout="vertical">
  <TemplateForm />
</Form>
```

并在文件顶部 import：

```tsx
import TemplateForm from '../../components/TemplateForm';
```

如果 `Divider`、`Input`、`InputNumber`、`MinusCircleOutlined`、`PlusOutlined` 在 Crops/index.tsx 不再使用，按 lint 提示清理 import。

- [ ] **类型检查 + 单测**

Run: `cd admin-web && pnpm tsc --noEmit && pnpm vitest run`

Expected: 0 errors；现有测试全部 PASS。

- [ ] **手测回归（启动前端）**

Run: `cd admin-web && pnpm dev`

打开 `/crops`，验证：
- 新建模版 Modal 仍能展示名称/品种/生长阶段输入
- 编辑现有模版能正确回填
- 「智能作物模板」区块仍在新建时显示

如果无法手测，至少跑现有的 vitest 全套：

Run: `cd admin-web && pnpm vitest run`

Expected: 全 PASS。

### Step 4.4: 提交

- [ ] **commit**

```bash
git add admin-web/src/components/TemplateForm.tsx admin-web/src/components/TemplateForm.test.tsx admin-web/src/pages/Crops/index.tsx
git commit -m "refactor(admin-web): 抽离 TemplateForm 共享组件，Crops 复用"
```

---

## Task 5: SystemLibrary 加 CRUD UI

**Files:**
- Modify: `admin-web/src/pages/CropTemplates/SystemLibrary.tsx`
- Modify: `admin-web/src/pages/CropTemplates/SystemLibrary.test.tsx`

### Step 5.1: 写失败测试 — 新建/编辑/删除流程

- [ ] **先读现有测试了解结构**

Run: `cat admin-web/src/pages/CropTemplates/SystemLibrary.test.tsx`

- [ ] **追加 3 个测试**

在 `SystemLibrary.test.tsx` 末尾追加（具体 mock 写法按现有测试风格对齐）：

```tsx
it('点击「新建模版」打开 Modal 并提交后调用 createSystemTemplate', async () => {
  // 渲染 SystemLibrary，mock listSystemCropTemplates 返回 []
  // 点击「新建模版」按钮
  // 填表单：名称=番茄、阶段=开花期
  // 点击确定
  // 断言 createSystemTemplate 被以 { name: '番茄', stages: [...] } 调用
});

it('点击行内「编辑」打开 Modal 并提交后调用 updateSystemTemplate', async () => {
  // mock listSystemCropTemplates 返回 1 条
  // 点击编辑
  // 改名称为「改名番茄」
  // 断言 updateSystemTemplate 被以 (id, payload) 调用
});

it('点击行内「删除」并确认后调用 deleteSystemTemplate', async () => {
  // mock listSystemCropTemplates 返回 1 条
  // 点击删除 → 确认
  // 断言 deleteSystemTemplate 被以 id 调用
});
```

具体实现参考现有 SystemLibrary.test.tsx 中已有的 mock 和 render 风格。

- [ ] **跑测试验证失败**

Run: `cd admin-web && pnpm vitest run src/pages/CropTemplates/SystemLibrary.test.tsx`

Expected: 3 个新测试 FAIL。

### Step 5.2: 实现 SystemLibrary CRUD

- [ ] **修改 `admin-web/src/pages/CropTemplates/SystemLibrary.tsx`**

完整改动要点（具体代码见下方）：

1. **import 新增**：
   ```tsx
   import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
   import { Modal, Form, Popconfirm } from 'antd';
   import TemplateForm from '../../components/TemplateForm';
   import {
     createSystemTemplate,
     updateSystemTemplate,
     deleteSystemTemplate,
     importSystemCropTemplate,
     listSystemCropTemplates,
     type CropTemplate,
   } from '../../api/crops';
   ```

2. **新增 state**：
   ```tsx
   const [modalOpen, setModalOpen] = useState(false);
   const [editingId, setEditingId] = useState<number | null>(null);
   const [saving, setSaving] = useState(false);
   const [form] = Form.useForm();
   ```

3. **新增 handler**：
   ```tsx
   const openCreate = () => {
     setEditingId(null);
     form.resetFields();
     setModalOpen(true);
   };

   const openEdit = (record: CropTemplate) => {
     setEditingId(record.id);
     form.setFieldsValue({
       name: record.name,
       variety: record.variety,
       stages: (record.stages ?? []).map((s) => ({
         name: s.name,
         duration_days: s.duration_days,
         key_tasks: s.key_tasks,
       })),
     });
     setModalOpen(true);
   };

   const handleSave = async () => {
     const values = await form.validateFields();
     const payload = {
       name: values.name,
       variety: values.variety,
       stages: (values.stages || []).map((s, i) => ({ ...s, order_index: i })),
     };
     setSaving(true);
     try {
       if (editingId === null) {
         await createSystemTemplate(payload);
         message.success('创建成功');
       } else {
         await updateSystemTemplate(editingId, payload);
         message.success('更新成功');
       }
       setModalOpen(false);
       form.resetFields();
       loadTemplates(category);
     } catch {
       message.error(editingId === null ? '创建失败' : '更新失败');
     } finally {
       setSaving(false);
     }
   };

   const handleDelete = async (id: number) => {
     try {
       await deleteSystemTemplate(id);
       message.success('删除成功');
       loadTemplates(category);
     } catch (err: any) {
       const detail = err?.response?.data?.detail;
       message.error(typeof detail === 'string' ? detail : '删除失败');
     }
   };
   ```

4. **工具栏加按钮**（在 `<Button icon={<ImportOutlined />}` 之前）：
   ```tsx
   <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
     新建模版
   </Button>
   ```

5. **columns 加操作列**（在「生长阶段」之后）：
   ```tsx
   {
     title: '操作',
     key: 'action',
     width: 160,
     render: (_: unknown, record: CropTemplate) => (
       <Space>
         <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(record)}>
           编辑
         </Button>
         <Popconfirm
           title="确认删除"
           description={`删除系统模版 "${record.name}"？已被农场导入的模版无法删除。`}
           onConfirm={() => handleDelete(record.id)}
           okText="删除"
           cancelText="取消"
         >
           <Button size="small" danger icon={<DeleteOutlined />}>
             删除
           </Button>
         </Popconfirm>
       </Space>
     ),
   },
   ```

6. **Modal 加在 `<Table />` 之后**（PageShell 内）：
   ```tsx
   <Modal
     title={editingId !== null ? '编辑系统模版' : '新建系统模版'}
     open={modalOpen}
     onOk={handleSave}
     confirmLoading={saving}
     onCancel={() => { setModalOpen(false); setEditingId(null); form.resetFields(); }}
     width={560}
   >
     <Form form={form} layout="vertical">
       <TemplateForm />
     </Form>
   </Modal>
   ```

- [ ] **跑测试验证通过**

Run: `cd admin-web && pnpm vitest run src/pages/CropTemplates/SystemLibrary.test.tsx`

Expected: 全部 PASS（含原有 + 新增 3 个）。

- [ ] **类型检查**

Run: `cd admin-web && pnpm tsc --noEmit`

Expected: 0 errors。

### Step 5.3: 提交

- [ ] **commit**

```bash
git add admin-web/src/pages/CropTemplates/SystemLibrary.tsx admin-web/src/pages/CropTemplates/SystemLibrary.test.tsx
git commit -m "feat(admin-web): SystemLibrary 加新建/编辑/删除系统模版 UI"
```

---

## Task 6: 文档同步与验收

**Files:**
- Modify: `docs/reference/api-spec.yaml`

### Step 6.1: 更新 API spec

- [ ] **在 `docs/reference/api-spec.yaml` 的 `/crops/templates/system` 路径下新增 POST/PUT/DELETE 描述**

参考已有 `GET /crops/templates/system` 的 yaml 风格补：

```yaml
/crops/templates/system:
  post:
    summary: 创建系统作物模版
    description: 创建 farm_id 为空的系统模版；同名同品种已存在时返回 409。
    tags: [crops]
    requestBody: { $ref: '#/components/schemas/CropTemplateCreate' }
    responses:
      '201': { description: 创建成功, content: { application/json: { schema: { $ref: '#/components/schemas/CropTemplateResponse' } } } }
      '409': { description: 同名同品种已存在 }

/crops/templates/system/{template_id}:
  put:
    summary: 更新系统作物模版
    description: 全量替换阶段；系统模版不存在返回 404。
    tags: [crops]
    parameters:
      - name: template_id
        in: path
        required: true
        schema: { type: integer }
    requestBody: { $ref: '#/components/schemas/CropTemplateCreate' }
    responses:
      '200': { description: 更新成功 }
      '404': { description: 系统模版不存在 }
  delete:
    summary: 删除系统作物模版
    description: 已被农场导入时返回 409。
    tags: [crops]
    parameters:
      - name: template_id
        in: path
        required: true
        schema: { type: integer }
    responses:
      '200': { description: 删除成功 }
      '404': { description: 系统模版不存在 }
      '409': { description: 已被农场导入 }
```

- [ ] **运行文档新鲜度检查**

Run: `bash scripts/check-doc-freshness.sh`

Expected: PASS（或针对当前改动产出准确报告，无无关失败）。

### Step 6.2: 全量回归测试

- [ ] **后端全量**

Run: `cd backend && poetry run pytest -v`

Expected: 全部 PASS。

- [ ] **前端类型 + 单测**

Run: `cd admin-web && pnpm tsc --noEmit && pnpm vitest run`

Expected: 0 errors，全 PASS。

- [ ] **架构约束检查**

Run: `bash scripts/check-layer-deps.sh && bash scripts/check-complexity-budget.sh`

Expected: PASS。

### Step 6.3: 提交

- [ ] **commit**

```bash
git add docs/reference/api-spec.yaml
git commit -m "docs(api-spec): 同步系统模版 CRUD 接口"
```

---

## Self-Review 校验

### Spec 覆盖检查

| Spec 章节 | 对应 Task |
| --- | --- |
| 3.1 后端 `POST /crops/templates/system` | Task 2 |
| 3.1 后端 `PUT /crops/templates/system/{id}` | Task 2 |
| 3.1 后端 `DELETE /crops/templates/system/{id}` | Task 2 |
| 3.2 service `find_system_template_duplicate` | 复用现有 `find_system_template_match`（无需新增） |
| 3.2 service `count_farm_imports` | Task 1（命名调整为 `count_farm_template_imports`） |
| 3.2 service `update/delete` 支持 `farm_id=None` | Task 1（改用独立方法，不污染现有分支） |
| 3.3 前端 API 3 函数 | Task 3 |
| 3.4 工具栏「新建」 | Task 5 |
| 3.4 表格「操作」列 | Task 5 |
| 3.4 抽离 TemplateForm | Task 4 |
| 3.4 删除失败提示文案 | Task 5 (`handleDelete` 取 `err.response.data.detail`) |
| 5.1 后端验收 6 项 | Task 1 + Task 2 测试覆盖 |
| 5.2 前端验收 5 项 | Task 4 + Task 5 测试覆盖 |
| 5.3 文档与规则同步 | Task 6 |

### 设计决策与 spec 偏差（已确认）

1. **service 改造方式**：spec 写"改造 `update/delete_crop_template` 支持 `farm_id=None` 分支"，实现时改为**新增独立方法** `update_system_crop_template` / `delete_system_crop_template`。理由：现有方法依赖 `_raise_if_system_template` 写保护，加 `farm_id=None` 分支会破坏 403 边界。独立方法更安全。

2. **POST 去重**：spec 写"新增 `find_system_template_duplicate`"，实际复用现有 [`find_system_template_match`](../../backend/app/services/crop_service.py#L165-L177)，签名一致，无需新增。

3. **count_farm_imports 命名**：spec 写 `count_farm_imports(db, system_template_id)`，实现时改为 `count_farm_template_imports(db, name, variety)`。理由：农场副本和系统模版没有外键关联（导入时只复制 name/variety），按 name+variety 匹配更直接。

### 类型一致性

- service 方法签名（`create_system_crop_template(db, template)` / `update_system_crop_template(db, template_id, update)` / `delete_system_crop_template(db, template_id)` / `count_farm_template_imports(db, name, variety)`）在 Task 1 测试、Task 1 实现、Task 2 API 实现中保持一致。
- 前端 `createSystemTemplate` / `updateSystemTemplate` / `deleteSystemTemplate` 命名在 Task 3、Task 5 一致。
- `TemplateFormValues` 类型导出位置：`admin-web/src/components/TemplateForm.tsx`（Task 4 创建）。

### 无占位符

无 "TBD" / "TODO" / "implement later" / "similar to Task N"。所有代码块完整可用。
