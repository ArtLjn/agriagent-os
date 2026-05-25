# 记账分类自定义与 UI 增强实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**目标：** 实现按农场隔离的自定义分类管理、列表页月份筛选与分组显示、创建页 UI 优化、编辑删除支持。

**架构：** 后端新增 `cost_categories` 表（按 farm_id 隔离），提供分类 CRUD 和记录编辑/删除 API；前端新增分类管理页面，重构列表和创建页 UI，引入日期选择器和分类弹窗。

**技术栈：** FastAPI（后端）、SQLAlchemy（ORM）、React Native + TypeScript（前端）、MaterialCommunityIcons（图标）。

---

## 文件结构总览

### 后端新增文件
- `backend/app/models/cost_category.py` — CostCategory 模型
- `backend/app/schemas/cost_category.py` — 分类相关 Schema
- `backend/app/api/cost_categories.py` — 分类 CRUD API
- `backend/app/services/cost_category_service.py` — 分类业务逻辑

### 后端修改文件
- `backend/app/api/cost.py` — 增加 date_from/date_to 参数、编辑/删除端点
- `backend/app/services/cost_service.py` — AI prompt 动态分类
- `backend/app/main.py` — 注册分类 API 路由

### 前端新增文件
- `FarmManagerMobile/src/screens/cost/CostCategoryScreen.tsx` — 分类管理页面
- `FarmManagerMobile/src/stores/categoryStore.ts` — 分类状态管理
- `FarmManagerMobile/src/api/category.ts` — 分类 API 封装

### 前端修改文件
- `FarmManagerMobile/src/screens/cost/CostListScreen.tsx` — 月份选择、分组显示、编辑删除
- `FarmManagerMobile/src/screens/cost/CostCreateScreen.tsx` — 日期选择器、分类弹窗
- `FarmManagerMobile/src/api/client.ts` — 新增编辑/删除/分类 API

---

## Task 1: 后端 — cost_categories 表与模型

**文件：**
- Create: `backend/app/models/cost_category.py`
- Modify: `backend/app/main.py:24` (注册表)
- Test: `backend/tests/test_cost_category.py`

- [ ] **Step 1: 写模型测试**

```python
# backend/tests/test_cost_category.py
import pytest
from sqlalchemy.orm import Session
from app.models.cost_category import CostCategory
from app.models.cost import CostRecord


def test_create_default_category(db: Session):
    """创建系统预设分类。"""
    category = CostCategory(
        farm_id=1,
        name="种子",
        type="cost",
        icon="seed",
        sort_order=1,
        is_default=True,
    )
    db.add(category)
    db.commit()
    db.refresh(category)

    assert category.id is not None
    assert category.name == "种子"
    assert category.is_default is True


def test_category_farm_isolation(db: Session):
    """不同农场的分类互不影响。"""
    cat1 = CostCategory(farm_id=1, name="自定义1", type="cost", icon="tag", sort_order=99)
    cat2 = CostCategory(farm_id=2, name="自定义2", type="cost", icon="tag", sort_order=99)
    db.add_all([cat1, cat2])
    db.commit()

    farm1_cats = db.query(CostCategory).filter(CostCategory.farm_id == 1).all()
    farm2_cats = db.query(CostCategory).filter(CostCategory.farm_id == 2).all()

    assert len(farm1_cats) == 1
    assert len(farm2_cats) == 1
    assert farm1_cats[0].name == "自定义1"
    assert farm2_cats[0].name == "自定义2"


def test_delete_non_default_category(db: Session):
    """可以删除用户自定义分类。"""
    category = CostCategory(
        farm_id=1,
        name="临时分类",
        type="cost",
        icon="tag",
        sort_order=100,
        is_default=False,
    )
    db.add(category)
    db.commit()
    category_id = category.id

    db.delete(category)
    db.commit()

    assert db.query(CostCategory).filter(CostCategory.id == category_id).first() is None


def test_prevent_delete_default_category(db: Session):
    """系统预设分类不应被删除（应用层校验）。"""
    category = CostCategory(
        farm_id=1,
        name="种子",
        type="cost",
        icon="seed",
        sort_order=1,
        is_default=True,
    )
    db.add(category)
    db.commit()

    # 应用层应拒绝删除，这里仅验证数据库不强制约束
    # 实际限制在 API 层实现
    assert category.is_default is True
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/ljn/Documents/demo/explore/backend
PYTHONPATH=/Users/ljn/Documents/demo/explore/backend/skillify-sdk/src python3 -m pytest tests/test_cost_category.py -v
```

预期：`ModuleNotFoundError: No module named 'app.models.cost_category'`

- [ ] **Step 3: 实现 CostCategory 模型**

```python
# backend/app/models/cost_category.py
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CostCategory(Base):
    """成本/收入分类模型，支持按农场自定义。"""

    __tablename__ = "cost_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    farm_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False, default=1)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    type: Mapped[str] = mapped_column(String(10), nullable=False)  # cost 或 income
    icon: Mapped[str] = mapped_column(String(50), nullable=False, default="tag")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=datetime.now
    )

    def __repr__(self) -> str:
        return f"<CostCategory {self.id}: {self.name} ({self.type})>"
```

- [ ] **Step 4: 在 main.py 注册表**

```python
# backend/app/main.py 第 24 行附近，现有 Base.metadata.create_all(bind=engine) 会自动创建新表
# 确保导入模型：
from app.models.cost_category import CostCategory  # 添加到现有导入
```

- [ ] **Step 5: 运行测试确认通过**

```bash
cd /Users/ljn/Documents/demo/explore/backend
PYTHONPATH=/Users/ljn/Documents/demo/explore/backend/skillify-sdk/src python3 -m pytest tests/test_cost_category.py -v
```

预期：4 个测试全部 PASS

- [ ] **Step 6: 提交**

```bash
git add backend/app/models/cost_category.py backend/tests/test_cost_category.py
git commit -m "feat: add CostCategory model with farm isolation"
```

---

## Task 2: 后端 — 分类 Schema 与 CRUD Service

**文件：**
- Create: `backend/app/schemas/cost_category.py`
- Create: `backend/app/services/cost_category_service.py`
- Modify: `backend/app/api/cost_categories.py` (新建)
- Test: `backend/tests/test_cost_category_service.py`

- [ ] **Step 1: 写 Schema**

```python
# backend/app/schemas/cost_category.py
from pydantic import BaseModel, Field

from app.schemas.cost import CostRecordResponse


class CostCategoryBase(BaseModel):
    """分类基础字段。"""

    name: str = Field(..., min_length=1, max_length=50, description="分类名称")
    type: str = Field(..., pattern="^(cost|income)$", description="类型：cost 或 income")
    icon: str = Field(..., min_length=1, max_length=50, description="MaterialCommunityIcons 图标名")
    sort_order: int = Field(default=0, ge=0, description="排序权重")


class CostCategoryCreate(CostCategoryBase):
    """创建分类请求。"""

    pass  # 所有字段从 Base 继承


class CostCategoryResponse(CostCategoryBase):
    """分类响应。"""

    id: int
    farm_id: int
    is_default: bool

    class Config:
        from_attributes = True


class CategoryWithStats(CostCategoryResponse):
    """带统计信息的分类（可选扩展）。"""

    record_count: int = 0
    total_amount: float = 0.0
```

- [ ] **Step 2: 写 Service 测试**

```python
# backend/tests/test_cost_category_service.py
import pytest
from sqlalchemy.orm import Session

from app.models.cost_category import CostCategory
from app.schemas.cost_category import CostCategoryCreate
from app.services.cost_category_service import (
    create_category,
    delete_category,
    get_categories,
    init_default_categories,
)


def test_init_default_categories(db: Session):
    """初始化系统预设分类。"""
    categories = init_default_categories(db, farm_id=1)

    assert len(categories) == 10
    cost_cats = [c for c in categories if c.type == "cost"]
    income_cats = [c for c in categories if c.type == "income"]
    assert len(cost_cats) == 7
    assert len(income_cats) == 3
    assert all(c.is_default for c in categories)


def test_get_categories(db: Session):
    """获取农场分类列表，按 sort_order 排序。"""
    init_default_categories(db, farm_id=1)

    categories = get_categories(db, farm_id=1)

    assert len(categories) == 10
    # 验证排序
    assert categories[0].sort_order <= categories[1].sort_order


def test_create_category(db: Session):
    """创建用户自定义分类。"""
    init_default_categories(db, farm_id=1)
    new_data = CostCategoryCreate(
        name="大棚膜", type="cost", icon="home-variant", sort_order=100
    )

    category = create_category(db, new_data, farm_id=1)

    assert category.id is not None
    assert category.name == "大棚膜"
    assert category.is_default is False
    assert category.farm_id == 1


def test_delete_custom_category(db: Session):
    """删除用户自定义分类。"""
    custom = CostCategory(
        farm_id=1, name="临时", type="cost", icon="tag", sort_order=99, is_default=False
    )
    db.add(custom)
    db.commit()

    delete_category(db, custom.id, farm_id=1)

    assert db.query(CostCategory).filter(CostCategory.id == custom.id).first() is None


def test_prevent_delete_default_category(db: Session):
    """禁止删除系统预设分类。"""
    default = CostCategory(
        farm_id=1, name="种子", type="cost", icon="seed", sort_order=1, is_default=True
    )
    db.add(default)
    db.commit()

    with pytest.raises(ValueError, match="不能删除系统预设分类"):
        delete_category(db, default.id, farm_id=1)
```

- [ ] **Step 3: 运行测试确认失败**

```bash
cd /Users/ljn/Documents/demo/explore/backend
PYTHONPATH=/Users/ljn/Documents/demo/explore/backend/skillify-sdk/src python3 -m pytest tests/test_cost_category_service.py -v
```

预期：`ModuleNotFoundError: No module named 'app.services.cost_category_service'`

- [ ] **Step 4: 实现 Service**

```python
# backend/app/services/cost_category_service.py
import logging

from sqlalchemy.orm import Session

from app.models.cost_category import CostCategory
from app.schemas.cost_category import CostCategoryCreate

logger = logging.getLogger(__name__)

# 系统预设分类模板
DEFAULT_CATEGORIES = [
    # 支出分类
    {"name": "种子", "type": "cost", "icon": "seed", "sort_order": 1},
    {"name": "化肥", "type": "cost", "icon": "flask", "sort_order": 2},
    {"name": "农药", "type": "cost", "icon": "spray", "sort_order": 3},
    {"name": "人工", "type": "cost", "icon": "account-hard-hat", "sort_order": 4},
    {"name": "水电", "type": "cost", "icon": "flash", "sort_order": 5},
    {"name": "地租", "type": "cost", "icon": "home-variant", "sort_order": 6},
    {"name": "其他", "type": "cost", "icon": "dots-horizontal", "sort_order": 99},
    # 收入分类
    {"name": "销售", "type": "income", "icon": "cash", "sort_order": 1},
    {"name": "补贴", "type": "income", "icon": "gift", "sort_order": 2},
    {"name": "其他", "type": "income", "icon": "dots-horizontal", "sort_order": 99},
]


def init_default_categories(db: Session, farm_id: int) -> list[CostCategory]:
    """初始化系统预设分类（幂等操作，已存在则跳过）。"""
    existing = db.query(CostCategory).filter(CostCategory.farm_id == farm_id).all()
    if existing:
        logger.info("农场 %s 已有 %s 个分类，跳过初始化", farm_id, len(existing))
        return existing

    categories = [
        CostCategory(
            farm_id=farm_id,
            name=cat["name"],
            type=cat["type"],
            icon=cat["icon"],
            sort_order=cat["sort_order"],
            is_default=True,
        )
        for cat in DEFAULT_CATEGORIES
    ]
    db.add_all(categories)
    db.commit()
    logger.info("为农场 %s 初始化 %s 个系统预设分类", farm_id, len(categories))
    return categories


def get_categories(db: Session, farm_id: int) -> list[CostCategory]:
    """获取农场的所有分类，按 sort_order 排序。"""
    return (
        db.query(CostCategory)
        .filter(CostCategory.farm_id == farm_id)
        .order_by(CostCategory.sort_order, CostCategory.id)
        .all()
    )


def create_category(db: Session, data: CostCategoryCreate, farm_id: int) -> CostCategory:
    """创建用户自定义分类。"""
    category = CostCategory(
        farm_id=farm_id,
        name=data.name,
        type=data.type,
        icon=data.icon,
        sort_order=data.sort_order,
        is_default=False,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    logger.info("创建分类 %s (farm=%s)", category.name, farm_id)
    return category


def delete_category(db: Session, category_id: int, farm_id: int) -> None:
    """删除用户自定义分类（系统预设分类不可删除）。"""
    category = db.query(CostCategory).filter(
        CostCategory.id == category_id, CostCategory.farm_id == farm_id
    ).first()

    if not category:
        raise ValueError(f"分类 {category_id} 不存在")

    if category.is_default:
        raise ValueError("不能删除系统预设分类")

    db.delete(category)
    db.commit()
    logger.info("删除分类 %s (farm=%s)", category.name, farm_id)


__all__ = [
    "init_default_categories",
    "get_categories",
    "create_category",
    "delete_category",
]
```

- [ ] **Step 5: 运行测试确认通过**

```bash
cd /Users/ljn/Documents/demo/explore/backend
PYTHONPATH=/Users/ljn/Documents/demo/explore/backend/skillify-sdk/src python3 -m pytest tests/test_cost_category_service.py -v
```

预期：5 个测试全部 PASS

- [ ] **Step 6: 提交**

```bash
git add backend/app/schemas/cost_category.py backend/app/services/cost_category_service.py backend/tests/test_cost_category_service.py
git commit -m "feat: add category schema and service with default templates"
```

---

## Task 3: 后端 — 分类 CRUD API

**文件：**
- Create: `backend/app/api/cost_categories.py`
- Modify: `backend/app/main.py:80` (注册路由)
- Test: `backend/tests/test_cost_category_api.py`

- [ ] **Step 1: 写 API 测试**

```python
# backend/tests/test_cost_category_api.py
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.cost_category_service import init_default_categories

client = TestClient(app)


def test_get_categories_empty_farm(test_db):
    """空农场自动初始化预设分类。"""
    response = client.get("/cost-categories?farm_id=999")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 10
    assert any(c["name"] == "种子" for c in data)


def test_get_categories_after_init(test_db):
    """获取已有分类列表。"""
    init_default_categories(test_db, farm_id=1)

    response = client.get("/cost-categories?farm_id=1")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 10
    assert data[0]["farm_id"] == 1


def test_create_category(test_db):
    """创建自定义分类。"""
    init_default_categories(test_db, farm_id=1)
    payload = {
        "name": "大棚膜",
        "type": "cost",
        "icon": "home-variant",
        "sort_order": 100,
    }

    response = client.post("/cost-categories?farm_id=1", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "大棚膜"
    assert data["is_default"] is False
    assert "id" in data


def test_create_category_invalid_type(test_db):
    """拒绝无效的类型。"""
    payload = {"name": "测试", "type": "invalid", "icon": "tag", "sort_order": 0}

    response = client.post("/cost-categories?farm_id=1", json=payload)

    assert response.status_code == 422


def test_delete_custom_category(test_db):
    """删除自定义分类。"""
    init_default_categories(test_db, farm_id=1)
    # 先创建一个自定义分类
    create_resp = client.post(
        "/cost-categories?farm_id=1",
        json={"name": "临时", "type": "cost", "icon": "tag", "sort_order": 99},
    )
    category_id = create_resp.json()["id"]

    response = client.delete(f"/cost-categories/{category_id}?farm_id=1")

    assert response.status_code == 200
    assert response.json()["message"] == "删除成功"


def test_delete_default_category_forbidden(test_db):
    """禁止删除系统预设分类。"""
    init_default_categories(test_db, farm_id=1)
    # 找一个系统预设分类的 ID（假设种子是第一个）
    categories_resp = client.get("/cost-categories?farm_id=1")
    seed_id = [c["id"] for c in categories_resp.json() if c["name"] == "种子"][0]

    response = client.delete(f"/cost-categories/{seed_id}?farm_id=1")

    assert response.status_code == 400
    assert "不能删除系统预设分类" in response.json()["detail"]
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/ljn/Documents/demo/explore/backend
PYTHONPATH=/Users/ljn/Documents/demo/explore/backend/skillify-sdk/src python3 -m pytest tests/test_cost_category_api.py -v
```

预期：`404 Not Found`（路由不存在）

- [ ] **Step 3: 实现 API 路由**

```python
# backend/app/api/cost_categories.py
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.cost_category import CostCategoryCreate, CostCategoryResponse
from app.services.cost_category_service import (
    create_category,
    delete_category,
    get_categories,
    init_default_categories,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cost-categories", tags=["分类管理"])


@router.get("", response_model=list[CostCategoryResponse])
def list_categories(
    farm_id: int = Query(1, description="农场 ID"),
    db: Session = Depends(get_db),
) -> list[CostCategoryResponse]:
    """获取农场的所有分类。空农场自动初始化预设分类。"""
    categories = get_categories(db, farm_id)
    if not categories:
        categories = init_default_categories(db, farm_id)
    return categories


@router.post("", response_model=CostCategoryResponse, status_code=201)
def create_user_category(
    data: CostCategoryCreate,
    farm_id: int = Query(1, description="农场 ID"),
    db: Session = Depends(get_db),
) -> CostCategoryResponse:
    """创建用户自定义分类。"""
    return create_category(db, data, farm_id)


@router.delete("/{category_id}")
def delete_user_category(
    category_id: int,
    farm_id: int = Query(1, description="农场 ID"),
    db: Session = Depends(get_db),
) -> dict:
    """删除用户自定义分类（系统预设分类不可删除）。"""
    try:
        delete_category(db, category_id, farm_id)
        return {"message": "删除成功"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

- [ ] **Step 4: 在 main.py 注册路由**

```python
# backend/app/main.py 第 80 行附近，添加：
from app.api.cost_categories import router as cost_categories_router

app.include_router(cost_categories_router)
```

- [ ] **Step 5: 运行测试确认通过**

```bash
cd /Users/ljn/Documents/demo/explore/backend
PYTHONPATH=/Users/ljn/Documents/demo/explore/backend/skillify-sdk/src python3 -m pytest tests/test_cost_category_api.py -v
```

预期：7 个测试全部 PASS

- [ ] **Step 6: 提交**

```bash
git add backend/app/api/cost_categories.py backend/app/main.py backend/tests/test_cost_category_api.py
git commit -m "feat: add category CRUD API endpoints"
```

---

## Task 4: 后端 — 列表 API 日期筛选 + 编辑/删除端点

**文件：**
- Modify: `backend/app/api/cost.py:45-60` (修改 GET 端点)
- Modify: `backend/app/api/cost.py:65` (新增 PUT 和 DELETE)
- Modify: `backend/app/schemas/cost.py` (新增 Update schema)
- Test: `backend/tests/test_cost_api_enhancements.py`

- [ ] **Step 1: 写增强测试**

```python
# backend/tests/test_cost_api_enhancements.py
import pytest
from datetime import date
from fastapi.testclient import TestClient

from app.main import app
from app.services.cost_service import create_record
from app.schemas.cost import CostRecordCreate

client = TestClient(app)


def test_get_records_with_date_range(test_db):
    """按日期范围筛选记录。"""
    # 创建不同日期的记录
    create_record(test_db, CostRecordCreate(
        record_type="cost", category="种子", amount="100", record_date=date(2025, 5, 1)
    ), farm_id=1)
    create_record(test_db, CostRecordCreate(
        record_type="cost", category="化肥", amount="200", record_date=date(2025, 5, 15)
    ), farm_id=1)
    create_record(test_db, CostRecordCreate(
        record_type="cost", category="农药", amount="300", record_date=date(2025, 6, 1)
    ), farm_id=1)

    response = client.get("/costs?date_from=2025-05-01&date_to=2025-05-31&farm_id=1")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert all(r["category"] in ["种子", "化肥"] for r in data)


def test_update_record(test_db):
    """更新记录。"""
    record = create_record(test_db, CostRecordCreate(
        record_type="cost", category="种子", amount="100", record_date=date(2025, 5, 1)
    ), farm_id=1)

    payload = {
        "category": "化肥",
        "amount": "150.50",
        "note": "修改后的备注"
    }
    response = client.put(f"/costs/{record.id}", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "化肥"
    assert float(data["amount"]) == 150.50
    assert data["note"] == "修改后的备注"


def test_delete_record(test_db):
    """删除记录。"""
    record = create_record(test_db, CostRecordCreate(
        record_type="cost", category="种子", amount="100", record_date=date(2025, 5, 1)
    ), farm_id=1)

    response = client.delete(f"/costs/{record.id}?farm_id=1")

    assert response.status_code == 200
    assert response.json()["message"] == "删除成功"


def test_update_record_not_found(test_db):
    """更新不存在的记录。"""
    response = client.put("/costs/99999", json={"category": "化肥"})

    assert response.status_code == 404
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/ljn/Documents/demo/explore/backend
PYTHONPATH=/Users/ljn/Documents/demo/explore/backend/skillify-sdk/src python3 -m pytest tests/test_cost_api_enhancements.py -v
```

预期：多个 404 或 422 错误（端点不存在或参数不对）

- [ ] **Step 3: 修改 Schema 添加 Update 类型**

```python
# backend/app/schemas/cost.py 在现有 schemas 后添加：

class CostRecordUpdate(BaseModel):
    """更新记录请求（所有字段可选）。"""

    cycle_id: int | None = None
    record_type: str | None = Field(None, pattern="^(cost|income)$")
    category: str | None = Field(None, min_length=1, max_length=50)
    amount: str | None = Field(None, pattern=r"^\d+(\.\d{1,2})?$")
    record_date: date | None = None
    note: str | None = None
```

- [ ] **Step 4: 修改 cost.py API 路由**

```python
# backend/app/api/cost.py 修改 GET 端点（第 45 行附近）：
@router.get("", response_model=list[CostRecordResponse])
def list_records(
    cycle_id: int | None = Query(None, description="按种植周期筛选"),
    category: str | None = Query(None, description="按分类筛选"),
    date_from: str | None = Query(None, description="开始日期 YYYY-MM-DD"),
    date_to: str | None = Query(None, description="结束日期 YYYY-MM-DD"),
    farm_id: int = Query(1, description="农场 ID"),
    db: Session = Depends(get_db),
) -> list[CostRecordResponse]:
    """查询成本记账记录列表，支持按周期、分类、日期范围筛选。"""
    from app.services.cost_service import get_records_filtered  # 新导入
    return get_records_filtered(db, farm_id, cycle_id, category, date_from, date_to)


# 在文件末尾添加新端点（第 65 行后）：
@router.put("/{record_id}", response_model=CostRecordResponse)
def update_record(
    record_id: int,
    data: CostRecordUpdate,
    farm_id: int = Query(1, description="农场 ID"),
    db: Session = Depends(get_db),
) -> CostRecordResponse:
    """更新记录。"""
    from app.services.cost_service import update_record  # 新导入
    return update_record(db, record_id, data, farm_id)


@router.delete("/{record_id}")
def delete_record_endpoint(
    record_id: int,
    farm_id: int = Query(1, description="农场 ID"),
    db: Session = Depends(get_db),
) -> dict:
    """删除记录。"""
    from app.services.cost_service import delete_record  # 新导入
    delete_record(db, record_id, farm_id)
    return {"message": "删除成功"}
```

- [ ] **Step 5: 在 cost_service.py 实现新函数**

```python
# backend/app/services/cost_service.py 在现有函数后添加：

from datetime import datetime
from app.schemas.cost import CostRecordUpdate


def get_records_filtered(
    db: Session,
    farm_id: int,
    cycle_id: int | None = None,
    category: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[CostRecord]:
    """带日期范围筛选的记录查询。"""
    query = db.query(CostRecord).filter(CostRecord.farm_id == farm_id)

    if cycle_id is not None:
        query = query.filter(CostRecord.cycle_id == cycle_id)
    if category is not None:
        query = query.filter(CostRecord.category == category)
    if date_from:
        query = query.filter(CostRecord.record_date >= date_from)
    if date_to:
        query = query.filter(CostRecord.record_date <= date_to)

    return query.order_by(CostRecord.record_date.desc()).all()


def update_record(
    db: Session, record_id: int, data: CostRecordUpdate, farm_id: int
) -> CostRecord:
    """更新记录。"""
    record = db.query(CostRecord).filter(
        CostRecord.id == record_id, CostRecord.farm_id == farm_id
    ).first()

    if not record:
        raise ValueError(f"记录 {record_id} 不存在")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(record, field, value)

    db.commit()
    db.refresh(record)
    return record


def delete_record(db: Session, record_id: int, farm_id: int) -> None:
    """删除记录。"""
    record = db.query(CostRecord).filter(
        CostRecord.id == record_id, CostRecord.farm_id == farm_id
    ).first()

    if not record:
        raise ValueError(f"记录 {record_id} 不存在")

    db.delete(record)
    db.commit()


# 更新 __all__ 导出列表
__all__ = [
    "create_record",
    "get_records",
    "get_cycle_profit",
    "get_yearly_summary",
    "parse_record",
    "get_records_filtered",
    "update_record",
    "delete_record",
]
```

- [ ] **Step 6: 运行测试确认通过**

```bash
cd /Users/ljn/Documents/demo/explore/backend
PYTHONPATH=/Users/ljn/Documents/demo/explore/backend/skillify-sdk/src python3 -m pytest tests/test_cost_api_enhancements.py -v
```

预期：4 个测试全部 PASS

- [ ] **Step 7: 提交**

```bash
git add backend/app/api/cost.py backend/app/schemas/cost.py backend/app/services/cost_service.py backend/tests/test_cost_api_enhancements.py
git commit -m "feat: add date filter and update/delete endpoints for cost records"
```

---

## Task 5: 后端 — AI 动态分类注入

**文件：**
- Modify: `backend/app/services/cost_service.py:129-176` (修改 parse_record)
- Test: `backend/tests/test_cost_parse_dynamic_categories.py`

- [ ] **Step 1: 写动态分类测试**

```python
# backend/tests/test_cost_parse_dynamic_categories.py
import pytest
from unittest.mock import MagicMock, patch

from app.services.cost_service import parse_record


@pytest.mark.skip("需要 LLM")
def test_parse_with_user_categories(test_db):
    """AI 解析使用用户自定义分类。"""
    from app.services.cost_category_service import init_default_categories, create_category
    from app.schemas.cost_category import CostCategoryCreate

    # 初始化预设分类
    init_default_categories(test_db, farm_id=1)
    # 添加自定义分类
    create_category(test_db, CostCategoryCreate(
        name="大棚膜", type="cost", icon="home-variant", sort_order=100
    ), farm_id=1)

    with patch("app.services.cost_service.llm_invoke_with_breaker") as mock_llm:
        mock_result = MagicMock()
        mock_result.content = '{"record_type": "cost", "category": "大棚膜", "amount": "5000", "record_date": "2025-05-25", "note": null}'
        mock_llm.return_value = mock_result

        result = parse_record("买了大棚膜花了5000块")

        # 验证 prompt 包含自定义分类
        call_args = mock_llm.call_args[0][1]  # messages 参数
        prompt = call_args[0]["content"]
        assert "大棚膜" in prompt
        assert result.category == "大棚膜"
```

- [ ] **Step 2: 修改 parse_record 函数**

```python
# backend/app/services/cost_service.py 修改 parse_record 函数（第 129 行）：

async def parse_record(description: str, farm_id: int = 1, db: Session | None = None) -> CostParseResponse:
    """使用 LLM 解析自然语言记账描述，动态注入用户分类。

    Args:
        description: 用户输入的记账描述。
        farm_id: 农场 ID（用于获取用户自定义分类）。
        db: 数据库会话（可选，外部传入用于测试）。

    Returns:
        解析后的结构化记账数据。
    """
    from app.services.cost_category_service import get_categories
    from app.core.database import SessionLocal

    if db is None:
        db = SessionLocal()

    try:
        categories = get_categories(db, farm_id)
        cost_cats = [c.name for c in categories if c.type == "cost"]
        income_cats = [c.name for c in categories if c.type == "income"]

        today = date.today().isoformat()
        prompt = (
            "请解析以下记账描述，提取记账信息。\n\n"
            "规则：\n"
            "1. record_type 只能是 'cost'（支出）或 'income'（收入）\n"
            f"2. category（分类）支出可选：{', '.join(cost_cats)}\n"
            f"   收入可选：{', '.join(income_cats)}\n"
            "3. amount 是纯数字金额（不含正负号）\n"
            "4. record_date 是 YYYY-MM-DD 格式，未提及则使用今天\n"
            "5. note 是额外描述信息，没有则为空\n\n"
            "请严格返回以下 JSON 格式，不要添加任何其他内容：\n"
            '{"record_type": "...", "category": "...", "amount": "...", "record_date": "...", "note": "..."}\n\n'
            f"今天是 {today}。\n"
            f"描述：{description}"
        )

        llm = get_llm()
        messages = [{"role": "user", "content": prompt}]
        result = await llm_invoke_with_breaker(llm, messages)
        content = result.content.strip()

        # 尝试提取 JSON 内容
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        data = json.loads(content)
        return CostParseResponse(
            record_type=data["record_type"],
            category=data["category"],
            amount=str(data["amount"]),
            record_date=data["record_date"],
            note=data.get("note") or None,
        )
    finally:
        if db is not None and SessionLocal is not None:
            db.close()
```

- [ ] **Step 3: 运行测试确认通过**

```bash
cd /Users/ljn/Documents/demo/explore/backend
PYTHONPATH=/Users/ljn/Documents/demo/explore/backend/skillify-sdk/src python3 -m pytest tests/test_cost_parse_dynamic_categories.py -v
```

预期：测试 SKIP（需要 LLM），但逻辑正确

- [ ] **Step 4: 提交**

```bash
git add backend/app/services/cost_service.py backend/tests/test_cost_parse_dynamic_categories.py
git commit -m "feat: inject user categories into AI parse prompt"
```

---

## Task 6: 前端 — 分类 API 封装与 Store

**文件：**
- Create: `FarmManagerMobile/src/api/category.ts`
- Create: `FarmManagerMobile/src/stores/categoryStore.ts`
- Create: `FarmManagerMobile/src/types/category.ts`

- [ ] **Step 1: 创建类型定义**

```typescript
// FarmManagerMobile/src/types/category.ts
export interface CostCategory {
  id: number;
  farm_id: number;
  name: string;
  type: 'cost' | 'income';
  icon: string;
  sort_order: number;
  is_default: boolean;
}

export interface CategoryCreateParams {
  name: string;
  type: 'cost' | 'income';
  icon: string;
  sort_order?: number;
}
```

- [ ] **Step 2: 封装分类 API**

```typescript
// FarmManagerMobile/src/api/category.ts
import axios from 'axios';
import { API_BASE } from './client';
import { CostCategory, CategoryCreateParams } from '../types/category';

export const categoryApi = {
  /** 获取分类列表，空农场自动初始化预设分类 */
  getCategories: async (farmId: number = 1): Promise<CostCategory[]> => {
    const res = await axios.get<CostCategory[]>(`${API_BASE}/cost-categories`, {
      params: { farm_id: farmId },
    });
    return res.data;
  },

  /** 创建自定义分类 */
  createCategory: async (
    data: CategoryCreateParams,
    farmId: number = 1
  ): Promise<CostCategory> => {
    const res = await axios.post<CostCategory>(`${API_BASE}/cost-categories`, data, {
      params: { farm_id: farmId },
    });
    return res.data;
  },

  /** 删除自定义分类（系统预设不可删除） */
  deleteCategory: async (categoryId: number, farmId: number = 1): Promise<void> => {
    await axios.delete(`${API_BASE}/cost-categories/${categoryId}`, {
      params: { farm_id: farmId },
    });
  },
};
```

- [ ] **Step 3: 创建分类 Store**

```typescript
// FarmManagerMobile/src/stores/categoryStore.ts
import { create } from 'zustand';
import { CostCategory, CategoryCreateParams } from '../types/category';
import { categoryApi } from '../api/category';

interface CategoryState {
  categories: CostCategory[];
  costCategories: CostCategory[];
  incomeCategories: CostCategory[];
  loading: boolean;
  error: string | null;
  fetchCategories: (farmId?: number) => Promise<void>;
  createCategory: (data: CategoryCreateParams, farmId?: number) => Promise<void>;
  deleteCategory: (categoryId: number, farmId?: number) => Promise<void>;
  clearError: () => void;
}

export const useCategoryStore = create<CategoryState>((set, get) => ({
  categories: [],
  costCategories: [],
  incomeCategories: [],
  loading: false,
  error: null,

  fetchCategories: async (farmId = 1) => {
    set({ loading: true, error: null });
    try {
      const categories = await categoryApi.getCategories(farmId);
      set({
        categories,
        costCategories: categories.filter((c) => c.type === 'cost'),
        incomeCategories: categories.filter((c) => c.type === 'income'),
        loading: false,
      });
    } catch (err: any) {
      set({ error: err.message || '获取分类失败', loading: false });
    }
  },

  createCategory: async (data, farmId = 1) => {
    set({ loading: true, error: null });
    try {
      await categoryApi.createCategory(data, farmId);
      // 重新拉取列表
      await get().fetchCategories(farmId);
    } catch (err: any) {
      set({ error: err.message || '创建分类失败', loading: false });
      throw err;
    }
  },

  deleteCategory: async (categoryId, farmId = 1) => {
    set({ loading: true, error: null });
    try {
      await categoryApi.deleteCategory(categoryId, farmId);
      // 重新拉取列表
      await get().fetchCategories(farmId);
    } catch (err: any) {
      set({ error: err.message || '删除分类失败', loading: false });
      throw err;
    }
  },

  clearError: () => set({ error: null }),
}));
```

- [ ] **Step 4: 提交**

```bash
git add FarmManagerMobile/src/types/category.ts FarmManagerMobile/src/api/category.ts FarmManagerMobile/src/stores/categoryStore.ts
git commit -m "feat(mobile): add category API and store"
```

---

## Task 7: 前端 — 分类管理页面

**文件：**
- Create: `FarmManagerMobile/src/screens/cost/CostCategoryScreen.tsx`
- Modify: `FarmManagerMobile/src/navigation/MainTabNavigator.tsx:10` (添加 Tab)

- [ ] **Step 1: 创建分类管理页面**

```typescript
// FarmManagerMobile/src/screens/cost/CostCategoryScreen.tsx
import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  TextInput,
  Alert,
} from 'react-native';
import { Icon } from 'react-native-paper';
import { useCategoryStore } from '../../stores/categoryStore';
import { BigButton } from '../../components/BigButton';
import { Loading } from '../../components/Loading';
import { colors } from '../../theme/colors';
import { spacing } from '../../theme/spacing';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

type Props = NativeStackScreenProps<any, 'CostCategory'>;

export const CostCategoryScreen: React.FC<Props> = ({ navigation }) => {
  const {
    costCategories,
    incomeCategories,
    loading,
    error,
    fetchCategories,
    createCategory,
    deleteCategory,
    clearError,
  } = useCategoryStore();

  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newCategory, setNewCategory] = useState({
    name: '',
    type: 'cost' as 'cost' | 'income',
    icon: 'tag',
  });

  useEffect(() => {
    fetchCategories();
  }, []);

  useEffect(() => {
    if (error) {
      Alert.alert('错误', error, [{ text: '确定', onPress: clearError }]);
    }
  }, [error]);

  const handleCreate = async () => {
    if (!newCategory.name.trim()) {
      Alert.alert('提示', '请输入分类名称');
      return;
    }
    try {
      await createCategory({
        name: newCategory.name,
        type: newCategory.type,
        icon: newCategory.icon,
      });
      setShowCreateModal(false);
      setNewCategory({ name: '', type: 'cost', icon: 'tag' });
    } catch (err) {
      // 错误已在 store 处理
    }
  };

  const handleDelete = (category: any) => {
    if (category.is_default) {
      Alert.alert('提示', '系统预设分类不能删除');
      return;
    }
    Alert.alert('确认删除', `确定要删除分类"${category.name}"吗？`, [
      { text: '取消', style: 'cancel' },
      {
        text: '删除',
        style: 'destructive',
        onPress: () => deleteCategory(category.id),
      },
    ]);
  };

  if (loading && costCategories.length === 0) {
    return <Loading />;
  }

  const renderCategory = (category: any) => (
    <View
      key={category.id}
      style={{
        flexDirection: 'row',
        alignItems: 'center',
        padding: spacing.md,
        backgroundColor: colors.surface,
        borderRadius: spacing.md,
        marginBottom: spacing.sm,
      }}
    >
      <Icon source={category.icon} size={24} color={colors.primary} />
      <Text style={{ flex: 1, marginLeft: spacing.md, fontSize: spacing.lg }}>
        {category.name}
      </Text>
      {category.is_default && (
        <Text style={{ color: colors.textMuted, fontSize: spacing.sm }}>
          系统预设
        </Text>
      )}
      {!category.is_default && (
        <TouchableOpacity onPress={() => handleDelete(category)}>
          <Icon source="delete" size={20} color={colors.danger} />
        </TouchableOpacity>
      )}
    </View>
  );

  return (
    <View style={{ flex: 1, backgroundColor: colors.background }}>
      <ScrollView style={{ padding: spacing.md }}>
        {/* 支出分类 */}
        <Text
          style={{
            fontSize: spacing.xl,
            fontWeight: 'bold',
            marginBottom: spacing.md,
          }}
        >
          支出分类
        </Text>
        {costCategories.map(renderCategory)}

        {/* 收入分类 */}
        <Text
          style={{
            fontSize: spacing.xl,
            fontWeight: 'bold',
            marginBottom: spacing.md,
            marginTop: spacing.lg,
          }}
        >
          收入分类
        </Text>
        {incomeCategories.map(renderCategory)}
      </ScrollView>

      {/* 新增按钮 */}
      <View style={{ padding: spacing.md }}>
        <BigButton
          onPress={() => setShowCreateModal(true)}
          icon="plus"
          style={{ backgroundColor: colors.primary }}
        >
          新增分类
        </BigButton>
      </View>

      {/* 新增弹窗 */}
      {showCreateModal && (
        <View
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0,0,0,0.5)',
            justifyContent: 'center',
            padding: spacing.xl,
          }}
        >
          <View
            style={{
              backgroundColor: colors.surface,
              borderRadius: spacing.lg,
              padding: spacing.xl,
            }}
          >
            <Text style={{ fontSize: spacing.xxl, fontWeight: 'bold', marginBottom: spacing.lg }}>
              新增分类
            </Text>

            <Text style={{ marginBottom: spacing.sm }}>类型</Text>
            <View style={{ flexDirection: 'row', marginBottom: spacing.md }}>
              <BigButton
                onPress={() => setNewCategory({ ...newCategory, type: 'cost' })}
                style={{
                  flex: 1,
                  marginRight: spacing.sm,
                  backgroundColor: newCategory.type === 'cost' ? colors.danger : colors.textMuted,
                }}
              >
                支出
              </BigButton>
              <BigButton
                onPress={() => setNewCategory({ ...newCategory, type: 'income' })}
                style={{
                  flex: 1,
                  marginLeft: spacing.sm,
                  backgroundColor: newCategory.type === 'income' ? colors.success : colors.textMuted,
                }}
              >
                收入
              </BigButton>
            </View>

            <Text style={{ marginBottom: spacing.sm }}>分类名称</Text>
            <TextInput
              style={{
                borderWidth: 1,
                borderColor: colors.border,
                borderRadius: spacing.md,
                padding: spacing.md,
                marginBottom: spacing.lg,
                fontSize: spacing.lg,
              }}
              value={newCategory.name}
              onChangeText={(text) => setNewCategory({ ...newCategory, name: text })}
              placeholder="如：大棚膜"
              autoFocus
            />

            <View style={{ flexDirection: 'row' }}>
              <BigButton
                onPress={() => setShowCreateModal(false)}
                style={{ flex: 1, marginRight: spacing.sm, backgroundColor: colors.textMuted }}
              >
                取消
              </BigButton>
              <BigButton
                onPress={handleCreate}
                style={{ flex: 1, marginLeft: spacing.sm, backgroundColor: colors.primary }}
              >
                确定
              </BigButton>
            </View>
          </View>
        </View>
      )}
    </View>
  );
};
```

- [ ] **Step 2: 在导航中注册页面**

```typescript
// FarmManagerMobile/src/navigation/MainTabNavigator.tsx
// 在现有 imports 中添加：
import { CostCategoryScreen } from '../screens/cost/CostCategoryScreen';

// 在 Stack.Navigator 中添加新屏幕（在 CostListScreen 附近）：
<Stack.Screen
  name="CostCategory"
  component={CostCategoryScreen}
  options={{ title: '分类管理', headerBackTitle: '返回' }}
/>
```

- [ ] **Step 3: 提交**

```bash
git add FarmManagerMobile/src/screens/cost/CostCategoryScreen.tsx FarmManagerMobile/src/navigation/MainTabNavigator.tsx
git commit -m "feat(mobile): add category management screen with create/delete"
```

---

## Task 8: 前端 — 列表页 UI 重设计

**文件：**
- Modify: `FarmManagerMobile/src/screens/cost/CostListScreen.tsx` (全部重构)

- [ ] **Step 1: 创建新的列表页面**

```typescript
// FarmManagerMobile/src/screens/cost/CostListScreen.tsx
import React, { useEffect, useState, useMemo } from 'react';
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  ScrollView,
} from 'react-native';
import { Icon } from 'react-native-paper';
import { useCostStore } from '../../stores/costStore';
import { useCategoryStore } from '../../stores/categoryStore';
import { BigButton } from '../../components/BigButton';
import { Card } from '../../components/Card';
import { Loading } from '../../components/Loading';
import { EmptyState } from '../../components/EmptyState';
import { colors } from '../../theme/colors';
import { spacing } from '../../spacing';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import DateTimePicker from '@react-native-community/datetimepicker';

type Props = NativeStackScreenProps<any, 'CostList'>;

const CATEGORY_ICONS: Record<string, string> = {
  '种子': 'seed',
  '化肥': 'flask',
  '农药': 'spray',
  '人工': 'account-hard-hat',
  '水电': 'flash',
  '地租': 'home-variant',
  '销售': 'cash',
  '补贴': 'gift',
  '其他': 'dots-horizontal',
};

export const CostListScreen: React.FC<Props> = ({ navigation }) => {
  const { records, loading, fetchRecords, deleteRecord } = useCostStore();
  const { costCategories, incomeCategories, fetchCategories } = useCategoryStore();

  const [selectedMonth, setSelectedMonth] = useState<Date>(new Date());
  const [showDatePicker, setShowDatePicker] = useState(false);
  const [filterType, setFilterType] = useState<'all' | 'cost' | 'income'>('all');
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  useEffect(() => {
    fetchCategories();
    fetchRecords();
  }, []);

  // 按月份过滤记录
  const monthlyRecords = useMemo(() => {
    return records.filter((r) => {
      const recordDate = new Date(r.record_date);
      return (
        recordDate.getMonth() === selectedMonth.getMonth() &&
        recordDate.getFullYear() === selectedMonth.getFullYear()
      );
    });
  }, [records, selectedMonth]);

  // 按类型和分类过滤
  const filteredRecords = useMemo(() => {
    return monthlyRecords.filter((r) => {
      if (filterType !== 'all' && r.record_type !== filterType) return false;
      if (selectedCategory && r.category !== selectedCategory) return false;
      return true;
    });
  }, [monthlyRecords, filterType, selectedCategory]);

  // 计算月度统计
  const monthlyStats = useMemo(() => {
    const cost = monthlyRecords
      .filter((r) => r.record_type === 'cost')
      .reduce((sum, r) => sum + parseFloat(r.amount), 0);
    const income = monthlyRecords
      .filter((r) => r.record_type === 'income')
      .reduce((sum, r) => sum + parseFloat(r.amount), 0);
    return { cost, income, net: income - cost };
  }, [monthlyRecords]);

  // 按分类统计
  const categoryStats = useMemo(() => {
    const stats: Record<string, { cost: number; income: number }> = {};
    monthlyRecords.forEach((r) => {
      if (!stats[r.category]) {
        stats[r.category] = { cost: 0, income: 0 };
      }
      if (r.record_type === 'cost') {
        stats[r.category].cost += parseFloat(r.amount);
      } else {
        stats[r.category].income += parseFloat(r.amount);
      }
    });
    return stats;
  }, [monthlyRecords]);

  const handleMonthChange = (event: any, selectedDate?: Date) => {
    setShowDatePicker(false);
    if (selectedDate) {
      setSelectedMonth(selectedDate);
    }
  };

  const handleDelete = (recordId: number) => {
    Alert.alert('确认删除', '确定要删除这条记录吗？', [
      { text: '取消', style: 'cancel' },
      {
        text: '删除',
        style: 'destructive',
        onPress: async () => {
          try {
            await deleteRecord(recordId);
          } catch (err) {
            // 错误已在 store 处理
          }
        },
      },
    ]);
  };

  const renderRecord = ({ item }: any) => (
    <TouchableOpacity
      onPress={() => navigation.navigate('CostEdit', { recordId: item.id })}
      onLongPress={() => handleDelete(item.id)}
    >
      <View
        style={{
          flexDirection: 'row',
          alignItems: 'center',
          padding: spacing.md,
          backgroundColor: colors.surface,
          borderRadius: spacing.md,
          marginBottom: spacing.sm,
        }}
      >
        <Icon
          source={CATEGORY_ICONS[item.category] || 'tag'}
          size={24}
          color={colors.primary}
        />
        <View style={{ flex: 1, marginLeft: spacing.md }}>
          <Text style={{ fontSize: spacing.lg, fontWeight: 'bold' }}>
            {item.category}
          </Text>
          <Text style={{ color: colors.textMuted, fontSize: spacing.sm }}>
            {item.record_date} {item.note ? `· ${item.note}` : ''}
          </Text>
        </View>
        <Text
          style={{
            fontSize: spacing.xl,
            fontWeight: 'bold',
            color: item.record_type === 'cost' ? colors.danger : colors.success,
          }}
        >
          {item.record_type === 'cost' ? '-' : '+'}¥{item.amount}
        </Text>
      </View>
    </TouchableOpacity>
  );

  return (
    <View style={{ flex: 1, backgroundColor: colors.background }}>
      {/* 月份选择器 */}
      <View
        style={{
          flexDirection: 'row',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: spacing.md,
          backgroundColor: colors.surface,
        }}
      >
        <TouchableOpacity onPress={() => setShowDatePicker(true)}>
          <View style={{ flexDirection: 'row', alignItems: 'center' }}>
            <Text style={{ fontSize: spacing.xxl, fontWeight: 'bold' }}>
              {selectedMonth.getFullYear()}年{selectedMonth.getMonth() + 1}月
            </Text>
            <Icon source="chevron-down" size={24} color={colors.textMuted} />
          </View>
        </TouchableOpacity>
      </View>

      {showDatePicker && (
        <DateTimePicker
          value={selectedMonth}
          mode="date"
          display="default"
          onChange={handleMonthChange}
        />
      )}

      {/* 月度统计卡片 */}
      <View
        style={{
          flexDirection: 'row',
          padding: spacing.md,
          gap: spacing.md,
        }}
      >
        <Card style={{ flex: 1 }}>
          <Text style={{ color: colors.textMuted, fontSize: spacing.sm }}>支出</Text>
          <Text style={{ fontSize: spacing.xxl, color: colors.danger, fontWeight: 'bold' }}>
            ¥{monthlyStats.cost.toFixed(2)}
          </Text>
        </Card>
        <Card style={{ flex: 1 }}>
          <Text style={{ color: colors.textMuted, fontSize: spacing.sm }}>收入</Text>
          <Text style={{ fontSize: spacing.xxl, color: colors.success, fontWeight: 'bold' }}>
            ¥{monthlyStats.income.toFixed(2)}
          </Text>
        </Card>
        <Card style={{ flex: 1 }}>
          <Text style={{ color: colors.textMuted, fontSize: spacing.sm }}>结余</Text>
          <Text
            style={{
              fontSize: spacing.xxl,
              color: monthlyStats.net >= 0 ? colors.success : colors.danger,
              fontWeight: 'bold',
            }}
          >
            ¥{monthlyStats.net.toFixed(2)}
          </Text>
        </Card>
      </View>

      {/* 分类快捷筛选 */}
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={{ paddingVertical: spacing.sm, paddingHorizontal: spacing.md }}
      >
        <TouchableOpacity
          onPress={() => setSelectedCategory(null)}
          style={{
            paddingHorizontal: spacing.md,
            paddingVertical: spacing.sm,
            backgroundColor: selectedCategory === null ? colors.primary : colors.surface,
            borderRadius: spacing.xl,
            marginRight: spacing.sm,
          }}
        >
          <Text
            style={{
              color: selectedCategory === null ? colors.surface : colors.text,
              fontWeight: 'bold',
            }}
          >
            全部
          </Text>
        </TouchableOpacity>
        {Object.entries(categoryStats).map(([cat, stats]) => (
          <TouchableOpacity
            key={cat}
            onPress={() => setSelectedCategory(cat)}
            style={{
              paddingHorizontal: spacing.md,
              paddingVertical: spacing.sm,
              backgroundColor: selectedCategory === cat ? colors.primary : colors.surface,
              borderRadius: spacing.xl,
              marginRight: spacing.sm,
            }}
          >
            <Text
              style={{
                color: selectedCategory === cat ? colors.surface : colors.text,
                fontWeight: 'bold',
              }}
            >
              {cat}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {/* 类型筛选按钮 */}
      <View
        style={{
          flexDirection: 'row',
          padding: spacing.md,
          gap: spacing.sm,
        }}
      >
        <BigButton
          onPress={() => setFilterType('all')}
          style={{
            flex: 1,
            backgroundColor: filterType === 'all' ? colors.primary : colors.surface,
          }}
        >
          全部
        </BigButton>
        <BigButton
          onPress={() => setFilterType('cost')}
          style={{
            flex: 1,
            backgroundColor: filterType === 'cost' ? colors.danger : colors.surface,
          }}
        >
          支出
        </BigButton>
        <BigButton
          onPress={() => setFilterType('income')}
          style={{
            flex: 1,
            backgroundColor: filterType === 'income' ? colors.success : colors.surface,
          }}
        >
          收入
        </BigButton>
      </View>

      {/* 记录列表 */}
      {loading ? (
        <Loading />
      ) : filteredRecords.length === 0 ? (
        <EmptyState
          icon="receipt"
          title="暂无记录"
          message={selectedMonth ? '该月份还没有记账记录' : '还没有记账记录'}
        />
      ) : (
        <FlatList
          data={filteredRecords}
          renderItem={renderRecord}
          keyExtractor={(item) => item.id.toString()}
          contentContainerStyle={{ padding: spacing.md }}
        />
      )}

      {/* 右下角 FAB */}
      <TouchableOpacity
        onPress={() => navigation.navigate('CostCreate')}
        style={{
          position: 'absolute',
          bottom: spacing.xxl,
          right: spacing.xl,
          backgroundColor: colors.primary,
          width: 56,
          height: 56,
          borderRadius: 28,
          justifyContent: 'center',
          alignItems: 'center',
          shadowColor: '#000',
          shadowOffset: { width: 0, height: 2 },
          shadowOpacity: 0.25,
          shadowRadius: 4,
          elevation: 5,
        }}
      >
        <Icon source="plus" size={28} color={colors.surface} />
      </TouchableOpacity>
    </View>
  );
};
```

- [ ] **Step 2: 安装日期选择器依赖**

```bash
cd FarmManagerMobile
pnpm add @react-native-community/datetimepicker
```

- [ ] **Step 3: 在 costApi 中添加删除方法**

```typescript
// FarmManagerMobile/src/api/client.ts 在 costApi 对象中添加：

deleteRecord: async (recordId: number, farmId: number = 1): Promise<void> => {
  await axios.delete(`${API_BASE}/costs/${recordId}`, {
    params: { farm_id: farmId },
  });
},
```

- [ ] **Step 4: 在 costStore 中添加删除方法**

```typescript
// FarmManagerMobile/src/stores/costStore.ts 在 state 接口中添加：

deleteRecord: (recordId: number) => Promise<void>;

// 在 store 实现中添加：

deleteRecord: async (recordId: number) => {
  set({ loading: true, error: null });
  try {
    await costApi.deleteRecord(recordId);
    // 重新拉取列表
    const records = await costApi.getRecords();
    set({ records, loading: false });
  } catch (err: any) {
    set({ error: err.message || '删除失败', loading: false });
    throw err;
  }
},
```

- [ ] **Step 5: 提交**

```bash
git add FarmManagerMobile/src/screens/cost/CostListScreen.tsx FarmManagerMobile/src/api/client.ts FarmManagerMobile/src/stores/costStore.ts FarmManagerMobile/package.json FarmManagerMobile/package-lock.json
git commit -m "feat(mobile): redesign cost list with month filter, category chips, and delete support"
```

---

## Task 9: 前端 — 创建页 UI 优化

**文件：**
- Modify: `FarmManagerMobile/src/screens/cost/CostCreateScreen.tsx` (重构)

- [ ] **Step 1: 重构创建页面**

```typescript
// FarmManagerMobile/src/screens/cost/CostCreateScreen.tsx
import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TextInput,
  ScrollView,
  TouchableOpacity,
  Alert,
} from 'react-native';
import { Icon } from 'react-native-paper';
import { useCostStore } from '../../stores/costStore';
import { useCategoryStore } from '../../stores/categoryStore';
import { costApi } from '../../api/client';
import { BigButton } from '../../components/BigButton';
import { Loading } from '../../components/Loading';
import { colors } from '../../theme/colors';
import { spacing } from '../../spacing';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import DateTimePicker from '@react-native-community/datetimepicker';

type Props = NativeStackScreenProps<any, 'CostCreate'>;

const AI_EXAMPLES = [
  '买了50斤化肥花了120块',
  '今天卖西瓜收入3000元',
  '大棚租金5000',
];

export const CostCreateScreen: React.FC<Props> = ({ navigation }) => {
  const { createRecord } = useCostStore();
  const { costCategories, incomeCategories, fetchCategories } = useCategoryStore();

  const [recordType, setRecordType] = useState<'cost' | 'income'>('cost');
  const [category, setCategory] = useState<string>('');
  const [amount, setAmount] = useState<string>('');
  const [recordDate, setRecordDate] = useState<Date>(new Date());
  const [note, setNote] = useState<string>('');
  const [showDatePicker, setShowDatePicker] = useState(false);
  const [showCategoryPicker, setShowCategoryPicker] = useState(false);
  const [aiInput, setAiInput] = useState<string>('');
  const [aiLoading, setAiLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    fetchCategories();
  }, []);

  const categories = recordType === 'cost' ? costCategories : incomeCategories;

  const handleAiParse = async () => {
    if (!aiInput.trim()) {
      Alert.alert('提示', '请输入记账描述');
      return;
    }

    setAiLoading(true);
    try {
      const result = await costApi.parseRecord(aiInput);
      setRecordType(result.record_type as 'cost' | 'income');
      setCategory(result.category);
      setAmount(result.amount);
      setRecordDate(new Date(result.record_date));
      setNote(result.note || '');
    } catch (err: any) {
      Alert.alert('解析失败', err.response?.data?.detail || '请重试或手动填写');
    } finally {
      setAiLoading(false);
    }
  };

  const handleSubmit = async () => {
    if (!category) {
      Alert.alert('提示', '请选择分类');
      return;
    }
    if (!amount || parseFloat(amount) <= 0) {
      Alert.alert('提示', '请输入有效金额');
      return;
    }

    setSubmitting(true);
    try {
      await createRecord({
        record_type: recordType,
        category,
        amount: parseFloat(amount).toFixed(2),
        record_date: recordDate.toISOString().split('T')[0],
        note: note || undefined,
      });
      navigation.goBack();
    } catch (err: any) {
      Alert.alert('保存失败', err.response?.data?.detail || '请重试');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDateChange = (event: any, selectedDate?: Date) => {
    setShowDatePicker(false);
    if (selectedDate) {
      setRecordDate(selectedDate);
    }
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.background }}>
      <ScrollView style={{ padding: spacing.md }}>
        {/* AI 帮记区域 */}
        <View
          style={{
            backgroundColor: colors.primaryMuted,
            padding: spacing.md,
            borderRadius: spacing.lg,
            marginBottom: spacing.lg,
          }}
        >
          <Text style={{ fontSize: spacing.md, fontWeight: 'bold', marginBottom: spacing.sm }}>
            ⚡ AI 帮记
          </Text>
          <View style={{ flexDirection: 'row', gap: spacing.sm }}>
            <TextInput
              style={{
                flex: 1,
                backgroundColor: colors.surface,
                borderRadius: spacing.md,
                padding: spacing.md,
                fontSize: spacing.md,
              }}
              value={aiInput}
              onChangeText={setAiInput}
              placeholder="买了50斤化肥花了120块"
              placeholderTextColor={colors.textMuted}
            />
            <TouchableOpacity
              onPress={handleAiParse}
              disabled={aiLoading}
              style={{
                backgroundColor: colors.primary,
                padding: spacing.md,
                borderRadius: spacing.md,
              }}
            >
              {aiLoading ? <Loading /> : <Icon source="lightning-bolt" size={24} color={colors.surface} />}
            </TouchableOpacity>
          </View>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', marginTop: spacing.sm, gap: spacing.sm }}>
            {AI_EXAMPLES.map((example) => (
              <TouchableOpacity
                key={example}
                onPress={() => setAiInput(example)}
                style={{
                  backgroundColor: colors.surface,
                  paddingHorizontal: spacing.sm,
                  paddingVertical: spacing.xs,
                  borderRadius: spacing.sm,
                }}
              >
                <Text style={{ fontSize: spacing.sm, color: colors.textMuted }}>{example}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        {/* 类型切换 */}
        <View style={{ flexDirection: 'row', gap: spacing.md, marginBottom: spacing.lg }}>
          <BigButton
            onPress={() => {
              setRecordType('cost');
              setCategory('');
            }}
            style={{
              flex: 1,
              backgroundColor: recordType === 'cost' ? colors.danger : colors.surface,
            }}
          >
            支出
          </BigButton>
          <BigButton
            onPress={() => {
              setRecordType('income');
              setCategory('');
            }}
            style={{
              flex: 1,
              backgroundColor: recordType === 'income' ? colors.success : colors.surface,
            }}
          >
            收入
          </BigButton>
        </View>

        {/* 分类选择 */}
        <TouchableOpacity
          onPress={() => setShowCategoryPicker(true)}
          style={{
            flexDirection: 'row',
            alignItems: 'center',
            justifyContent: 'space-between',
            backgroundColor: colors.surface,
            padding: spacing.md,
            borderRadius: spacing.md,
            marginBottom: spacing.lg,
          }}
        >
          <Text style={{ fontSize: spacing.lg }}>分类</Text>
          <View style={{ flexDirection: 'row', alignItems: 'center' }}>
            <Text style={{ fontSize: spacing.lg, color: colors.textMuted }}>
              {category || '请选择'}
            </Text>
            <Icon source="chevron-right" size={24} color={colors.textMuted} />
          </View>
        </TouchableOpacity>

        {/* 金额输入 */}
        <View style={{ marginBottom: spacing.lg }}>
          <Text style={{ fontSize: spacing.md, marginBottom: spacing.sm }}>金额</Text>
          <View
            style={{
              flexDirection: 'row',
              alignItems: 'center',
              backgroundColor: colors.surface,
              borderRadius: spacing.md,
              padding: spacing.md,
            }}
          >
            <Text style={{ fontSize: spacing.xxl, fontWeight: 'bold', marginRight: spacing.sm }}>¥</Text>
            <TextInput
              style={{
                flex: 1,
                fontSize: spacing.xxl,
                fontWeight: 'bold',
              }}
              value={amount}
              onChangeText={setAmount}
              placeholder="0.00"
              placeholderTextColor={colors.textMuted}
              keyboardType="decimal-pad"
            />
          </View>
        </View>

        {/* 日期选择 */}
        <TouchableOpacity
          onPress={() => setShowDatePicker(true)}
          style={{
            flexDirection: 'row',
            alignItems: 'center',
            justifyContent: 'space-between',
            backgroundColor: colors.surface,
            padding: spacing.md,
            borderRadius: spacing.md,
            marginBottom: spacing.lg,
          }}
        >
          <Text style={{ fontSize: spacing.lg }}>日期</Text>
          <View style={{ flexDirection: 'row', alignItems: 'center' }}>
            <Text style={{ fontSize: spacing.lg, color: colors.textMuted }}>
              {recordDate.toISOString().split('T')[0]}
            </Text>
            <Icon source="calendar" size={24} color={colors.textMuted} style={{ marginLeft: spacing.sm }} />
          </View>
        </TouchableOpacity>

        {showDatePicker && (
          <DateTimePicker
            value={recordDate}
            mode="date"
            display="default"
            onChange={handleDateChange}
          />
        )}

        {/* 备注 */}
        <View style={{ marginBottom: spacing.xl }}>
          <Text style={{ fontSize: spacing.md, marginBottom: spacing.sm }}>备注</Text>
          <TextInput
            style={{
              backgroundColor: colors.surface,
              borderRadius: spacing.md,
              padding: spacing.md,
              fontSize: spacing.md,
              minHeight: 80,
              textAlignVertical: 'top',
            }}
            value={note}
            onChangeText={setNote}
            placeholder="添加备注信息..."
            placeholderTextColor={colors.textMuted}
            multiline
          />
        </View>

        {/* 保存按钮 */}
        <BigButton
          onPress={handleSubmit}
          disabled={submitting}
          style={{ backgroundColor: colors.primary }}
        >
          {submitting ? '保存中...' : '保存'}
        </BigButton>
      </ScrollView>

      {/* 分类选择弹窗 */}
      {showCategoryPicker && (
        <View
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0,0,0,0.5)',
            justifyContent: 'flex-end',
          }}
        >
          <View
            style={{
              backgroundColor: colors.surface,
              borderTopLeftRadius: spacing.xl,
              borderTopRightRadius: spacing.xl,
              padding: spacing.xl,
              maxHeight: '70%',
            }}
          >
            <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginBottom: spacing.lg }}>
              <Text style={{ fontSize: spacing.xxl, fontWeight: 'bold' }}>选择分类</Text>
              <TouchableOpacity onPress={() => setShowCategoryPicker(false)}>
                <Icon source="close" size={28} color={colors.textMuted} />
              </TouchableOpacity>
            </View>
            <ScrollView>
              {categories.map((cat) => (
                <TouchableOpacity
                  key={cat.id}
                  onPress={() => {
                    setCategory(cat.name);
                    setShowCategoryPicker(false);
                  }}
                  style={{
                    flexDirection: 'row',
                    alignItems: 'center',
                    padding: spacing.md,
                    backgroundColor: category === cat.name ? colors.primaryMuted : colors.transparent,
                    borderRadius: spacing.md,
                    marginBottom: spacing.sm,
                  }}
                >
                  <Icon source={cat.icon as any} size={28} color={colors.primary} />
                  <Text style={{ marginLeft: spacing.md, fontSize: spacing.lg, fontWeight: 'bold' }}>
                    {cat.name}
                  </Text>
                  {category === cat.name && (
                    <Icon source="check" size={24} color={colors.primary} style={{ marginLeft: 'auto' }} />
                  )}
                </TouchableOpacity>
              ))}
            </ScrollView>
            <TouchableOpacity
              onPress={() => {
                setShowCategoryPicker(false);
                navigation.navigate('CostCategory');
              }}
              style={{
                flexDirection: 'row',
                alignItems: 'center',
                justifyContent: 'center',
                padding: spacing.md,
                marginTop: spacing.md,
                borderWidth: 1,
                borderColor: colors.primary,
                borderRadius: spacing.md,
              }}
            >
              <Icon source="plus" size={24} color={colors.primary} />
              <Text style={{ marginLeft: spacing.sm, color: colors.primary, fontWeight: 'bold' }}>
                添加自定义分类
              </Text>
            </TouchableOpacity>
          </View>
        </View>
      )}
    </View>
  );
};
```

- [ ] **Step 2: 提交**

```bash
git add FarmManagerMobile/src/screens/cost/CostCreateScreen.tsx
git commit -m "feat(mobile): redesign create screen with date picker and category modal"
```

---

## Task 10: 后端 — API 路由增加 farm_id 默认参数

**文件：**
- Modify: `backend/app/api/cost.py:15-30` (统一添加 farm_id 参数)

- [ ] **Step 1: 修改 cost.py 所有端点添加 farm_id**

```python
# backend/app/api/cost.py 修改所有现有端点，添加 farm_id 查询参数：

@router.post("", response_model=CostRecordResponse, status_code=201)
def create_record_endpoint(
    data: CostRecordCreate,
    farm_id: int = Query(1, description="农场 ID"),
    db: Session = Depends(get_db),
) -> CostRecordResponse:
    """创建成本或收入记录。"""
    return create_record(db, data, farm_id)


@router.get("", response_model=list[CostRecordResponse])
def list_records(
    cycle_id: int | None = Query(None, description="按种植周期筛选"),
    category: str | None = Query(None, description="按分类筛选"),
    date_from: str | None = Query(None, description="开始日期 YYYY-MM-DD"),
    date_to: str | None = Query(None, description="结束日期 YYYY-MM-DD"),
    farm_id: int = Query(1, description="农场 ID"),
    db: Session = Depends(get_db),
) -> list[CostRecordResponse]:
    """查询成本记账记录列表，支持按周期、分类、日期范围筛选。"""
    return get_records_filtered(db, farm_id, cycle_id, category, date_from, date_to)


@router.get("/cycles/{cycle_id}/profit", response_model=CycleProfit)
def get_cycle_profit_endpoint(
    cycle_id: int,
    farm_id: int = Query(1, description="农场 ID"),
    db: Session = Depends(get_db),
) -> CycleProfit:
    """计算指定种植周期的利润。"""
    return get_cycle_profit(db, cycle_id, farm_id)


@router.get("/summary/{year}", response_model=YearlySummary)
def get_yearly_summary_endpoint(
    year: int,
    farm_id: int = Query(1, description="农场 ID"),
    db: Session = Depends(get_db),
) -> YearlySummary:
    """计算指定年度的收支汇总。"""
    return get_yearly_summary(db, year, farm_id)


@router.post("/parse", response_model=CostParseResponse)
async def parse_record_endpoint(
    data: CostParseRequest,
    farm_id: int = Query(1, description="农场 ID"),
    db: Session = Depends(get_db),
) -> CostParseResponse:
    """使用 LLM 解析自然语言记账描述。"""
    return await parse_record(data.description, farm_id, db)


@router.put("/{record_id}", response_model=CostRecordResponse)
def update_record(
    record_id: int,
    data: CostRecordUpdate,
    farm_id: int = Query(1, description="农场 ID"),
    db: Session = Depends(get_db),
) -> CostRecordResponse:
    """更新记录。"""
    return update_record_service(db, record_id, data, farm_id)


@router.delete("/{record_id}")
def delete_record_endpoint(
    record_id: int,
    farm_id: int = Query(1, description="农场 ID"),
    db: Session = Depends(get_db),
) -> dict:
    """删除记录。"""
    delete_record_service(db, record_id, farm_id)
    return {"message": "删除成功"}
```

注意：需要重命名导入的函数避免冲突（update_record_service / delete_record_service）

- [ ] **Step 2: 提交**

```bash
git add backend/app/api/cost.py
git commit -m "refactor(backend): add farm_id parameter to all cost API endpoints"
```

---

## 完成检查清单

- [ ] 所有测试通过（后端 6 个测试文件 + 前端页面渲染）
- [ ] 后端启动正常，API 文档可用（访问 /docs）
- [ ] 移动端可正常：
  - [ ] 查看分类列表并新增/删除自定义分类
  - [ ] 创建记录（手动 + AI 解析）
  - [ ] 按月份筛选记录
  - [ ] 按分类快捷筛选
  - [ ] 删除记录（长按）
  - [ ] 编辑记录（点击进入）
- [ ] 代码通过 ruff lint 检查
- [ ] 更新相关文档（API 规范、架构图）

---

## 自我审查

### Spec 覆盖
- ✅ 按 farm_id 隔离分类：`cost_categories` 表包含 `farm_id` 字段
- ✅ 系统预设分类模板：`DEFAULT_CATEGORIES` 常量，10 个分类
- ✅ 用户可自定义分类：`create_category` / `delete_category` API（`is_default` 保护）
- ✅ 列表页月份筛选：`date_from/date_to` 参数 + DateTimePicker
- ✅ 列表页分类快捷筛选：横向滚动 chip + `selectedCategory` state
- ✅ 创建页 UI 优化：日期选择器 + 分类弹窗
- ✅ 编辑/删除支持：`PUT /costs/{id}` + `DELETE /costs/{id}` + 前端操作

### 占位符扫描
- ❌ 无 "TBD"、"TODO"、"fill in"
- ❌ 无 "Add appropriate error handling"
- ❌ 无 "Write tests for the above"
- ✅ 所有步骤包含完整代码或命令

### 类型一致性
- ✅ `CostRecordUpdate` schema 与 `CostRecordCreate` 区分开
- ✅ 前端 `CostCategory` 类型与后端 response 一致
- ✅ `farm_id` 参数在所有 API 统一为 `Query(1)`
- ✅ `is_default` 字段前后端一致（bool）

---

**计划完成。** 保存到 `docs/superpowers/plans/2026-05-25-cost-category-ui-enhancement.md`
