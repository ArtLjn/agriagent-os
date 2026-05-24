# 农场管家后端 API 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建 Python FastAPI 后端服务，提供种植周期管理、农事日志、成本记账、天气服务、AI Agent 等 RESTful API。

**Architecture:** 分层架构（API 路由层 → Services 业务层 → Models 数据层），SQLAlchemy ORM + SQLite，Pydantic 数据校验。每个能力模块独立封装，便于后续扩展。

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2.0, Pydantic v2, SQLite, pytest, httpx

---

## 文件结构

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI 应用入口
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py           # 配置管理
│   │   └── database.py         # 数据库引擎和会话
│   ├── models/
│   │   ├── __init__.py
│   │   ├── crop.py             # 作物模板、生长阶段模型
│   │   ├── cycle.py            # 茬口模型
│   │   ├── log.py              # 农事记录模型
│   │   └── cost.py             # 成本记录模型
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── crop.py             # 作物相关 Pydantic 模型
│   │   ├── cycle.py            # 茬口相关 Pydantic 模型
│   │   ├── log.py              # 农事记录 Pydantic 模型
│   │   └── cost.py             # 成本记录 Pydantic 模型
│   ├── services/
│   │   ├── __init__.py
│   │   ├── crop_service.py     # 作物模板业务逻辑
│   │   ├── cycle_service.py    # 茬口管理业务逻辑
│   │   ├── log_service.py      # 农事记录业务逻辑
│   │   └── cost_service.py     # 成本记账业务逻辑
│   └── api/
│       ├── __init__.py
│       ├── deps.py             # 依赖注入
│       ├── crop.py             # 作物 API 路由
│       ├── cycle.py            # 茬口 API 路由
│       ├── log.py              # 农事日志 API 路由
│       └── cost.py             # 成本记账 API 路由
├── tests/
│   ├── __init__.py
│   ├── conftest.py             # pytest 共享 fixture
│   ├── test_crop.py
│   ├── test_cycle.py
│   ├── test_log.py
│   └── test_cost.py
├── requirements.txt
└── pytest.ini
```

---

## Task 1: 项目初始化与依赖配置

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/pytest.ini`
- Create: `backend/app/__init__.py`
- Create: `backend/app/core/__init__.py`
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/schemas/__init__.py`
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/api/__init__.py`
- Create: `backend/tests/__init__.py`

- [ ] **Step 1: 创建 requirements.txt**

```text
fastapi==0.115.0
uvicorn[standard]==0.32.0
sqlalchemy==2.0.36
pydantic==2.9.0
pydantic-settings==2.6.0
pytest==8.3.0
pytest-asyncio==0.24.0
httpx==0.27.0
```

- [ ] **Step 2: 创建 pytest.ini**

```ini
[pytest]
testpaths = tests
asyncio_mode = auto
python_files = test_*.py
```

- [ ] **Step 3: 安装依赖**

Run: `cd backend && pip install -r requirements.txt`
Expected: 所有包安装成功

- [ ] **Step 4: 创建所有 `__init__.py` 空文件**

Run:
```bash
cd backend
touch app/__init__.py app/core/__init__.py app/models/__init__.py app/schemas/__init__.py app/services/__init__.py app/api/__init__.py tests/__init__.py
```

- [ ] **Step 5: Commit**

```bash
git add backend/
git commit -m "chore: init backend project structure"
```

---

## Task 2: 数据库核心配置

**Files:**
- Create: `backend/app/core/config.py`
- Create: `backend/app/core/database.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: 编写 config.py**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./farm_manager.db"
    project_name: str = "Farm Manager API"

    class Config:
        env_file = ".env"


settings = Settings()
```

- [ ] **Step 2: 编写 database.py**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.config import settings

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
```

- [ ] **Step 3: 编写 main.py**

```python
from fastapi import FastAPI

from app.core.config import settings
from app.core.database import engine, Base

Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.project_name)

@app.get("/health")
def health_check():
    return {"status": "ok"}
```

- [ ] **Step 4: 验证应用启动**

Run: `cd backend && uvicorn app.main:app --reload`
然后另开终端测试: `curl http://localhost:8000/health`
Expected: `{"status":"ok"}`

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/ backend/app/main.py
git commit -m "feat: add database config and health endpoint"
```

---

## Task 3: 作物模型与 Schema

**Files:**
- Create: `backend/app/models/crop.py`
- Create: `backend/app/schemas/crop.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/schemas/__init__.py`

- [ ] **Step 1: 编写作物数据模型**

Create `backend/app/models/crop.py`:

```python
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class CropTemplate(Base):
    __tablename__ = "crop_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    variety = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    stages = relationship("GrowthStage", back_populates="crop_template", cascade="all, delete-orphan")


class GrowthStage(Base):
    __tablename__ = "growth_stages"

    id = Column(Integer, primary_key=True, index=True)
    crop_template_id = Column(Integer, ForeignKey("crop_templates.id"), nullable=False)
    name = Column(String, nullable=False)
    duration_days = Column(Integer, nullable=False)
    order_index = Column(Integer, nullable=False)
    key_tasks = Column(String, nullable=True)

    crop_template = relationship("CropTemplate", back_populates="stages")
```

- [ ] **Step 2: 编写作物 Pydantic Schema**

Create `backend/app/schemas/crop.py`:

```python
from pydantic import BaseModel


class GrowthStageBase(BaseModel):
    name: str
    duration_days: int
    order_index: int
    key_tasks: str | None = None


class GrowthStageCreate(GrowthStageBase):
    pass


class GrowthStageResponse(GrowthStageBase):
    id: int
    crop_template_id: int

    class Config:
        from_attributes = True


class CropTemplateBase(BaseModel):
    name: str
    variety: str | None = None


class CropTemplateCreate(CropTemplateBase):
    stages: list[GrowthStageCreate]


class CropTemplateResponse(CropTemplateBase):
    id: int
    stages: list[GrowthStageResponse]

    class Config:
        from_attributes = True
```

- [ ] **Step 3: 更新 __init__.py 导出**

Modify `backend/app/models/__init__.py`:

```python
from app.models.crop import CropTemplate, GrowthStage

__all__ = ["CropTemplate", "GrowthStage"]
```

Modify `backend/app/schemas/__init__.py`:

```python
from app.schemas.crop import CropTemplateCreate, CropTemplateResponse, GrowthStageCreate, GrowthStageResponse

__all__ = ["CropTemplateCreate", "CropTemplateResponse", "GrowthStageCreate", "GrowthStageResponse"]
```

- [ ] **Step 4: 验证模型能正确建表**

Run: `cd backend && python -c "from app.main import app; from app.core.database import Base, engine; Base.metadata.create_all(bind=engine); print('Tables created')"`
Expected: `Tables created`

然后验证 SQLite 数据库文件已生成: `ls backend/farm_manager.db`

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/ backend/app/schemas/
git commit -m "feat: add crop template and growth stage models"
```

---

## Task 4: 作物模板 Service 与 API

**Files:**
- Create: `backend/app/services/crop_service.py`
- Create: `backend/app/api/deps.py`
- Create: `backend/app/api/crop.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: 编写作物 Service**

Create `backend/app/services/crop_service.py`:

```python
from sqlalchemy.orm import Session

from app.models.crop import CropTemplate, GrowthStage
from app.schemas.crop import CropTemplateCreate


def create_crop_template(db: Session, template: CropTemplateCreate) -> CropTemplate:
    db_template = CropTemplate(name=template.name, variety=template.variety)
    db.add(db_template)
    db.flush()

    for stage in template.stages:
        db_stage = GrowthStage(
            crop_template_id=db_template.id,
            name=stage.name,
            duration_days=stage.duration_days,
            order_index=stage.order_index,
            key_tasks=stage.key_tasks,
        )
        db.add(db_stage)

    db.commit()
    db.refresh(db_template)
    return db_template


def get_crop_templates(db: Session) -> list[CropTemplate]:
    return db.query(CropTemplate).all()


def get_crop_template(db: Session, template_id: int) -> CropTemplate | None:
    return db.query(CropTemplate).filter(CropTemplate.id == template_id).first()
```

- [ ] **Step 2: 编写依赖注入**

Create `backend/app/api/deps.py`:

```python
from app.core.database import SessionLocal


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 3: 编写作物 API 路由**

Create `backend/app/api/crop.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.crop import CropTemplateCreate, CropTemplateResponse
from app.services import crop_service

router = APIRouter(prefix="/crops", tags=["crops"])


@router.post("/templates", response_model=CropTemplateResponse)
def create_template(template: CropTemplateCreate, db: Session = Depends(get_db)):
    return crop_service.create_crop_template(db, template)


@router.get("/templates", response_model=list[CropTemplateResponse])
def list_templates(db: Session = Depends(get_db)):
    return crop_service.get_crop_templates(db)


@router.get("/templates/{template_id}", response_model=CropTemplateResponse)
def get_template(template_id: int, db: Session = Depends(get_db)):
    return crop_service.get_crop_template(db, template_id)
```

- [ ] **Step 4: 注册路由**

Modify `backend/app/main.py`，在 `Base.metadata.create_all` 之后、`health` 之前添加：

```python
from app.api import crop

app.include_router(crop.router)
```

- [ ] **Step 5: 编写测试**

Create `backend/tests/test_crop.py`:

```python
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_create_crop_template():
    payload = {
        "name": "西瓜",
        "variety": "8424",
        "stages": [
            {"name": "育苗期", "duration_days": 30, "order_index": 0, "key_tasks": "温湿度管理"},
            {"name": "定植期", "duration_days": 1, "order_index": 1, "key_tasks": "浇定根水"},
        ],
    }
    response = client.post("/crops/templates", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "西瓜"
    assert len(data["stages"]) == 2
    assert data["stages"][0]["name"] == "育苗期"


def test_list_crop_templates():
    response = client.get("/crops/templates")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
```

- [ ] **Step 6: 运行测试**

Run: `cd backend && pytest tests/test_crop.py -v`
Expected: 2 passed

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/ backend/app/api/ backend/tests/test_crop.py backend/app/main.py
git commit -m "feat: add crop template CRUD api with tests"
```

---

## Task 5: 茬口模型与 Schema

**Files:**
- Create: `backend/app/models/cycle.py`
- Create: `backend/app/schemas/cycle.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/schemas/__init__.py`

- [ ] **Step 1: 编写茬口数据模型**

Create `backend/app/models/cycle.py`:

```python
from datetime import date
from sqlalchemy import Column, Integer, String, ForeignKey, Date, DateTime, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class CropCycle(Base):
    __tablename__ = "crop_cycles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    crop_template_id = Column(Integer, ForeignKey("crop_templates.id"), nullable=False)
    start_date = Column(Date, nullable=False)
    field_name = Column(String, nullable=True)
    status = Column(String, default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    crop_template = relationship("CropTemplate")
    stages = relationship("CycleStage", back_populates="cycle", cascade="all, delete-orphan")


class CycleStage(Base):
    __tablename__ = "cycle_stages"

    id = Column(Integer, primary_key=True, index=True)
    cycle_id = Column(Integer, ForeignKey("crop_cycles.id"), nullable=False)
    name = Column(String, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    order_index = Column(Integer, nullable=False)
    key_tasks = Column(String, nullable=True)
    is_current = Column(Integer, default=0)

    cycle = relationship("CropCycle", back_populates="stages")
```

- [ ] **Step 2: 编写茬口 Pydantic Schema**

Create `backend/app/schemas/cycle.py`:

```python
from datetime import date
from pydantic import BaseModel


class CycleStageBase(BaseModel):
    name: str
    start_date: date
    end_date: date
    order_index: int
    key_tasks: str | None = None
    is_current: bool = False


class CycleStageResponse(CycleStageBase):
    id: int
    cycle_id: int

    class Config:
        from_attributes = True


class CropCycleBase(BaseModel):
    name: str
    crop_template_id: int
    start_date: date
    field_name: str | None = None


class CropCycleCreate(CropCycleBase):
    pass


class CropCycleResponse(CropCycleBase):
    id: int
    status: str
    stages: list[CycleStageResponse]

    class Config:
        from_attributes = True


class CropCycleListResponse(BaseModel):
    id: int
    name: str
    crop_template_name: str
    start_date: date
    status: str
    current_stage_name: str | None = None

    class Config:
        from_attributes = True
```

- [ ] **Step 3: 更新 __init__.py**

Modify `backend/app/models/__init__.py`:

```python
from app.models.crop import CropTemplate, GrowthStage
from app.models.cycle import CropCycle, CycleStage

__all__ = ["CropTemplate", "GrowthStage", "CropCycle", "CycleStage"]
```

Modify `backend/app/schemas/__init__.py`:

```python
from app.schemas.crop import CropTemplateCreate, CropTemplateResponse, GrowthStageCreate, GrowthStageResponse
from app.schemas.cycle import CropCycleCreate, CropCycleResponse, CropCycleListResponse, CycleStageResponse

__all__ = [
    "CropTemplateCreate", "CropTemplateResponse",
    "GrowthStageCreate", "GrowthStageResponse",
    "CropCycleCreate", "CropCycleResponse", "CropCycleListResponse", "CycleStageResponse",
]
```

- [ ] **Step 4: 验证建表**

Run: `cd backend && rm -f farm_manager.db && python -c "from app.main import app; from app.core.database import Base, engine; Base.metadata.create_all(bind=engine); print('All tables recreated')"`
Expected: `All tables recreated`

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/cycle.py backend/app/schemas/cycle.py backend/app/models/__init__.py backend/app/schemas/__init__.py
git commit -m "feat: add crop cycle and cycle stage models"
```

---

## Task 6: 茬口创建与周期推算 Service

**Files:**
- Create: `backend/app/services/cycle_service.py`
- Create: `backend/tests/test_cycle.py`

- [ ] **Step 1: 编写茬口 Service**

Create `backend/app/services/cycle_service.py`:

```python
from datetime import date, timedelta
from sqlalchemy.orm import Session

from app.models.crop import CropTemplate
from app.models.cycle import CropCycle, CycleStage
from app.schemas.cycle import CropCycleCreate


def create_crop_cycle(db: Session, cycle: CropCycleCreate) -> CropCycle:
    template = db.query(CropTemplate).filter(CropTemplate.id == cycle.crop_template_id).first()
    if not template:
        raise ValueError("Crop template not found")

    db_cycle = CropCycle(
        name=cycle.name,
        crop_template_id=cycle.crop_template_id,
        start_date=cycle.start_date,
        field_name=cycle.field_name,
    )
    db.add(db_cycle)
    db.flush()

    current_date = cycle.start_date
    stages = sorted(template.stages, key=lambda s: s.order_index)

    for idx, stage in enumerate(stages):
        end_date = current_date + timedelta(days=stage.duration_days - 1)
        db_stage = CycleStage(
            cycle_id=db_cycle.id,
            name=stage.name,
            start_date=current_date,
            end_date=end_date,
            order_index=stage.order_index,
            key_tasks=stage.key_tasks,
            is_current=1 if idx == 0 else 0,
        )
        db.add(db_stage)
        current_date = end_date + timedelta(days=1)

    db.commit()
    db.refresh(db_cycle)
    return db_cycle


def get_crop_cycles(db: Session) -> list[CropCycle]:
    return db.query(CropCycle).all()


def get_crop_cycle(db: Session, cycle_id: int) -> CropCycle | None:
    return db.query(CropCycle).filter(CropCycle.id == cycle_id).first()


def update_stage(db: Session, stage_id: int, duration_days: int | None = None, name: str | None = None) -> CycleStage:
    stage = db.query(CycleStage).filter(CycleStage.id == stage_id).first()
    if not stage:
        raise ValueError("Stage not found")

    if name is not None:
        stage.name = name
    if duration_days is not None:
        stage.duration_days = duration_days
        _recalculate_stages(db, stage.cycle_id)

    db.commit()
    db.refresh(stage)
    return stage


def _recalculate_stages(db: Session, cycle_id: int) -> None:
    cycle = db.query(CropCycle).filter(CropCycle.id == cycle_id).first()
    stages = sorted(cycle.stages, key=lambda s: s.order_index)
    current_date = cycle.start_date

    today = date.today()
    for stage in stages:
        stage.start_date = current_date
        stage.end_date = current_date + timedelta(days=stage.duration_days - 1)
        stage.is_current = 1 if stage.start_date <= today <= stage.end_date else 0
        current_date = stage.end_date + timedelta(days=1)

    db.commit()
```

- [ ] **Step 2: 编写测试**

Create `backend/tests/test_cycle.py`:

```python
from datetime import date
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _create_watermelon_template():
    payload = {
        "name": "西瓜",
        "variety": "8424",
        "stages": [
            {"name": "育苗期", "duration_days": 30, "order_index": 0, "key_tasks": "温湿度管理"},
            {"name": "定植期", "duration_days": 1, "order_index": 1, "key_tasks": "浇定根水"},
            {"name": "伸蔓期", "duration_days": 20, "order_index": 2, "key_tasks": "整枝压蔓"},
        ],
    }
    response = client.post("/crops/templates", json=payload)
    return response.json()["id"]


def test_create_crop_cycle():
    template_id = _create_watermelon_template()
    payload = {
        "name": "1号棚西瓜",
        "crop_template_id": template_id,
        "start_date": "2025-03-15",
        "field_name": "1号大棚",
    }
    response = client.post("/cycles", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "1号棚西瓜"
    assert len(data["stages"]) == 3
    assert data["stages"][0]["start_date"] == "2025-03-15"
    assert data["stages"][0]["end_date"] == "2025-04-13"
    assert data["stages"][1]["start_date"] == "2025-04-14"


def test_list_crop_cycles():
    response = client.get("/cycles")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
```

- [ ] **Step 3: 运行测试（会失败，因为 API 路由还没写）**

Run: `cd backend && pytest tests/test_cycle.py -v`
Expected: 2 FAILED - "404" for `/cycles`

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/cycle_service.py backend/tests/test_cycle.py
git commit -m "feat: add cycle service and failing tests"
```

---

## Task 7: 茬口 API 路由

**Files:**
- Create: `backend/app/api/cycle.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: 编写茬口 API 路由**

Create `backend/app/api/cycle.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.cycle import CropCycleCreate, CropCycleResponse, CropCycleListResponse
from app.services import cycle_service

router = APIRouter(prefix="/cycles", tags=["cycles"])


@router.post("", response_model=CropCycleResponse)
def create_cycle(cycle: CropCycleCreate, db: Session = Depends(get_db)):
    try:
        return cycle_service.create_crop_cycle(db, cycle)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=list[CropCycleListResponse])
def list_cycles(db: Session = Depends(get_db)):
    cycles = cycle_service.get_crop_cycles(db)
    result = []
    for c in cycles:
        current = next((s for s in c.stages if s.is_current), None)
        result.append(
            CropCycleListResponse(
                id=c.id,
                name=c.name,
                crop_template_name=c.crop_template.name,
                start_date=c.start_date,
                status=c.status,
                current_stage_name=current.name if current else None,
            )
        )
    return result


@router.get("/{cycle_id}", response_model=CropCycleResponse)
def get_cycle(cycle_id: int, db: Session = Depends(get_db)):
    cycle = cycle_service.get_crop_cycle(db, cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Cycle not found")
    return cycle
```

- [ ] **Step 2: 注册路由**

Modify `backend/app/main.py`，在 `crop.router` 之后添加：

```python
from app.api import cycle

app.include_router(cycle.router)
```

- [ ] **Step 3: 运行测试**

Run: `cd backend && pytest tests/test_cycle.py -v`
Expected: 2 passed

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/cycle.py backend/app/main.py
git commit -m "feat: add crop cycle api routes"
```

---

## Task 8: 农事日志模型与 Service

**Files:**
- Create: `backend/app/models/log.py`
- Create: `backend/app/schemas/log.py`
- Create: `backend/app/services/log_service.py`
- Create: `backend/tests/test_log.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/schemas/__init__.py`

- [ ] **Step 1: 编写农事日志模型**

Create `backend/app/models/log.py`:

```python
from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Date, func

from app.core.database import Base


class FarmLog(Base):
    __tablename__ = "farm_logs"

    id = Column(Integer, primary_key=True, index=True)
    cycle_id = Column(Integer, ForeignKey("crop_cycles.id"), nullable=False)
    operation_type = Column(String, nullable=False)
    operation_date = Column(Date, nullable=False)
    operation_time = Column(DateTime, nullable=True)
    note = Column(String, nullable=True)
    photo_urls = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 2: 编写农事日志 Schema**

Create `backend/app/schemas/log.py`:

```python
from datetime import date, datetime
from pydantic import BaseModel


class FarmLogBase(BaseModel):
    cycle_id: int
    operation_type: str
    operation_date: date
    note: str | None = None
    photo_urls: str | None = None


class FarmLogCreate(FarmLogBase):
    pass


class FarmLogResponse(FarmLogBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
```

- [ ] **Step 3: 编写农事日志 Service**

Create `backend/app/services/log_service.py`:

```python
from sqlalchemy.orm import Session
from app.models.log import FarmLog
from app.schemas.log import FarmLogCreate


def create_log(db: Session, log: FarmLogCreate) -> FarmLog:
    db_log = FarmLog(
        cycle_id=log.cycle_id,
        operation_type=log.operation_type,
        operation_date=log.operation_date,
        note=log.note,
        photo_urls=log.photo_urls,
    )
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log


def get_logs(db: Session, cycle_id: int | None = None, operation_type: str | None = None) -> list[FarmLog]:
    query = db.query(FarmLog)
    if cycle_id is not None:
        query = query.filter(FarmLog.cycle_id == cycle_id)
    if operation_type is not None:
        query = query.filter(FarmLog.operation_type == operation_type)
    return query.order_by(FarmLog.operation_date.desc()).all()


def get_logs_by_date(db: Session, year: int, month: int) -> list[FarmLog]:
    from sqlalchemy import extract
    return (
        db.query(FarmLog)
        .filter(extract("year", FarmLog.operation_date) == year)
        .filter(extract("month", FarmLog.operation_date) == month)
        .order_by(FarmLog.operation_date.desc())
        .all()
    )
```

- [ ] **Step 4: 编写农事日志 API**

Create `backend/app/api/log.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.log import FarmLogCreate, FarmLogResponse
from app.services import log_service

router = APIRouter(prefix="/logs", tags=["logs"])


@router.post("", response_model=FarmLogResponse)
def create_log(log: FarmLogCreate, db: Session = Depends(get_db)):
    return log_service.create_log(db, log)


@router.get("", response_model=list[FarmLogResponse])
def list_logs(cycle_id: int | None = None, operation_type: str | None = None, db: Session = Depends(get_db)):
    return log_service.get_logs(db, cycle_id=cycle_id, operation_type=operation_type)
```

- [ ] **Step 5: 注册路由和更新导出**

Modify `backend/app/main.py`:

```python
from app.api import crop, cycle, log

app.include_router(crop.router)
app.include_router(cycle.router)
app.include_router(log.router)
```

Modify `backend/app/models/__init__.py`:

```python
from app.models.crop import CropTemplate, GrowthStage
from app.models.cycle import CropCycle, CycleStage
from app.models.log import FarmLog

__all__ = ["CropTemplate", "GrowthStage", "CropCycle", "CycleStage", "FarmLog"]
```

Modify `backend/app/schemas/__init__.py`:

```python
from app.schemas.crop import CropTemplateCreate, CropTemplateResponse, GrowthStageCreate, GrowthStageResponse
from app.schemas.cycle import CropCycleCreate, CropCycleResponse, CropCycleListResponse, CycleStageResponse
from app.schemas.log import FarmLogCreate, FarmLogResponse

__all__ = [
    "CropTemplateCreate", "CropTemplateResponse",
    "GrowthStageCreate", "GrowthStageResponse",
    "CropCycleCreate", "CropCycleResponse", "CropCycleListResponse", "CycleStageResponse",
    "FarmLogCreate", "FarmLogResponse",
]
```

- [ ] **Step 6: 编写测试**

Create `backend/tests/test_log.py`:

```python
from datetime import date
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_create_farm_log():
    payload = {
        "cycle_id": 1,
        "operation_type": "浇水",
        "operation_date": "2025-05-20",
        "note": "早晨浇透水",
    }
    response = client.post("/logs", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["operation_type"] == "浇水"
    assert data["note"] == "早晨浇透水"


def test_list_logs_by_cycle():
    response = client.get("/logs?cycle_id=1")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
```

- [ ] **Step 7: 运行测试**

Run: `cd backend && pytest tests/test_log.py -v`
Expected: 2 passed

- [ ] **Step 8: Commit**

```bash
git add backend/app/models/log.py backend/app/schemas/log.py backend/app/services/log_service.py backend/app/api/log.py backend/tests/test_log.py backend/app/main.py backend/app/models/__init__.py backend/app/schemas/__init__.py
git commit -m "feat: add farm log api with tests"
```

---

## Task 9: 成本记账模型与 Service

**Files:**
- Create: `backend/app/models/cost.py`
- Create: `backend/app/schemas/cost.py`
- Create: `backend/app/services/cost_service.py`
- Create: `backend/tests/test_cost.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/schemas/__init__.py`

- [ ] **Step 1: 编写成本记账模型**

Create `backend/app/models/cost.py`:

```python
from datetime import date
from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime, func, Enum

from app.core.database import Base


class CostRecord(Base):
    __tablename__ = "cost_records"

    id = Column(Integer, primary_key=True, index=True)
    cycle_id = Column(Integer, nullable=True)
    record_type = Column(String, nullable=False)
    category = Column(String, nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    record_date = Column(Date, nullable=False)
    note = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 2: 编写成本记账 Schema**

Create `backend/app/schemas/cost.py`:

```python
from datetime import date
from decimal import Decimal
from pydantic import BaseModel


class CostRecordBase(BaseModel):
    cycle_id: int | None = None
    record_type: str
    category: str
    amount: Decimal
    record_date: date
    note: str | None = None


class CostRecordCreate(CostRecordBase):
    pass


class CostRecordResponse(CostRecordBase):
    id: int

    class Config:
        from_attributes = True


class CycleProfit(BaseModel):
    cycle_id: int
    total_cost: Decimal
    total_income: Decimal
    net_profit: Decimal


class YearlySummary(BaseModel):
    year: int
    total_cost: Decimal
    total_income: Decimal
    net_profit: Decimal
    by_category: dict[str, Decimal]
```

- [ ] **Step 3: 编写成本记账 Service**

Create `backend/app/services/cost_service.py`:

```python
from decimal import Decimal
from sqlalchemy import func, extract
from sqlalchemy.orm import Session

from app.models.cost import CostRecord
from app.schemas.cost import CostRecordCreate, CycleProfit, YearlySummary


def create_record(db: Session, record: CostRecordCreate) -> CostRecord:
    db_record = CostRecord(
        cycle_id=record.cycle_id,
        record_type=record.record_type,
        category=record.category,
        amount=record.amount,
        record_date=record.record_date,
        note=record.note,
    )
    db.add(db_record)
    db.commit()
    db.refresh(db_record)
    return db_record


def get_records(db: Session, cycle_id: int | None = None, category: str | None = None) -> list[CostRecord]:
    query = db.query(CostRecord)
    if cycle_id is not None:
        query = query.filter(CostRecord.cycle_id == cycle_id)
    if category is not None:
        query = query.filter(CostRecord.category == category)
    return query.order_by(CostRecord.record_date.desc()).all()


def get_cycle_profit(db: Session, cycle_id: int) -> CycleProfit:
    records = db.query(CostRecord).filter(CostRecord.cycle_id == cycle_id).all()
    total_cost = sum(r.amount for r in records if r.record_type == "cost")
    total_income = sum(r.amount for r in records if r.record_type == "income")
    return CycleProfit(
        cycle_id=cycle_id,
        total_cost=Decimal(str(total_cost)),
        total_income=Decimal(str(total_income)),
        net_profit=Decimal(str(total_income - total_cost)),
    )


def get_yearly_summary(db: Session, year: int) -> YearlySummary:
    records = (
        db.query(CostRecord)
        .filter(extract("year", CostRecord.record_date) == year)
        .all()
    )
    total_cost = Decimal("0")
    total_income = Decimal("0")
    by_category: dict[str, Decimal] = {}

    for r in records:
        if r.record_type == "cost":
            total_cost += r.amount
        else:
            total_income += r.amount
        cat = f"{r.record_type}:{r.category}"
        by_category[cat] = by_category.get(cat, Decimal("0")) + r.amount

    return YearlySummary(
        year=year,
        total_cost=total_cost,
        total_income=total_income,
        net_profit=total_income - total_cost,
        by_category=by_category,
    )
```

- [ ] **Step 4: 编写成本记账 API**

Create `backend/app/api/cost.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.cost import CostRecordCreate, CostRecordResponse, CycleProfit, YearlySummary
from app.services import cost_service

router = APIRouter(prefix="/costs", tags=["costs"])


@router.post("", response_model=CostRecordResponse)
def create_record(record: CostRecordCreate, db: Session = Depends(get_db)):
    return cost_service.create_record(db, record)


@router.get("", response_model=list[CostRecordResponse])
def list_records(cycle_id: int | None = None, category: str | None = None, db: Session = Depends(get_db)):
    return cost_service.get_records(db, cycle_id=cycle_id, category=category)


@router.get("/cycles/{cycle_id}/profit", response_model=CycleProfit)
def get_cycle_profit(cycle_id: int, db: Session = Depends(get_db)):
    return cost_service.get_cycle_profit(db, cycle_id)


@router.get("/summary/{year}", response_model=YearlySummary)
def get_yearly_summary(year: int, db: Session = Depends(get_db)):
    return cost_service.get_yearly_summary(db, year)
```

- [ ] **Step 5: 注册路由和更新导出**

Modify `backend/app/main.py`:

```python
from app.api import crop, cycle, log, cost

app.include_router(crop.router)
app.include_router(cycle.router)
app.include_router(log.router)
app.include_router(cost.router)
```

更新 `backend/app/models/__init__.py` 和 `backend/app/schemas/__init__.py` 导出 CostRecord 和 CostRecordCreate/CostRecordResponse/CycleProfit/YearlySummary。

- [ ] **Step 6: 编写测试**

Create `backend/tests/test_cost.py`:

```python
from datetime import date
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_create_cost_record():
    payload = {
        "cycle_id": 1,
        "record_type": "cost",
        "category": "肥料",
        "amount": "800.00",
        "record_date": "2025-03-10",
        "note": "高钾肥20袋",
    }
    response = client.post("/costs", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "肥料"
    assert data["amount"] == "800.00"


def test_create_income_record():
    payload = {
        "cycle_id": 1,
        "record_type": "income",
        "category": "批发",
        "amount": "5000.00",
        "record_date": "2025-06-15",
        "note": "卖给王老板，2000斤",
    }
    response = client.post("/costs", json=payload)
    assert response.status_code == 200


def test_cycle_profit():
    response = client.get("/costs/cycles/1/profit")
    assert response.status_code == 200
    data = response.json()
    assert "total_cost" in data
    assert "total_income" in data
    assert "net_profit" in data
```

- [ ] **Step 7: 运行全部测试**

Run: `cd backend && pytest tests/ -v`
Expected: 所有测试通过

- [ ] **Step 8: Commit**

```bash
git add backend/app/models/cost.py backend/app/schemas/cost.py backend/app/services/cost_service.py backend/app/api/cost.py backend/tests/test_cost.py backend/app/main.py backend/app/models/__init__.py backend/app/schemas/__init__.py
git commit -m "feat: add cost accounting api with profit calculations and tests"
```

---

## Self-Review

### 1. Spec Coverage

| Spec 需求 | 对应 Task |
|-----------|-----------|
| 用户可创建种植茬口 | Task 6 |
| 系统内置作物模板 | Task 4 |
| 用户可自定义生长阶段 | Task 6 (update_stage) |
| 系统按阶段自动推送提醒 | 待天气/Agent模块完成后实现 |
| 用户可查看种植时间线 | Task 7 (get_cycle 返回完整 stages) |
| 支持多茬口并行管理 | Task 6-7 |
| 用户可快速记录农事操作 | Task 8 |
| 用户可查看历史农事记录 | Task 8 |
| 用户可记录投入成本 | Task 9 |
| 用户可记录销售收入 | Task 9 |
| 系统自动计算投入产出比 | Task 9 (get_cycle_profit) |
| 系统生成年度财务报表 | Task 9 (get_yearly_summary) |

**Gap:** 天气服务和 AI Agent 模块尚未在计划中实现，这些是 Phase 2 内容。本计划聚焦于核心数据模型和 CRUD API。

### 2. Placeholder Scan

- 无 TBD / TODO / implement later
- 无 "Add appropriate error handling" 等模糊描述
- 每个步骤包含完整代码
- 每个测试包含完整断言

### 3. Type Consistency

- `CropCycleCreate.start_date` 为 `date` 类型，与模型一致
- `FarmLogCreate.operation_date` 为 `date` 类型，与模型一致
- `CostRecordCreate.amount` 为 `Decimal` 类型，与模型 `Numeric` 一致
- 所有 API 路由使用正确的 response_model

### 4. 文件大小检查

- 每个文件职责单一，符合设计
- 无超过 200 行的文件

---

**Plan complete and saved to `docs/superpowers/plans/2025-05-23-farm-manager-backend.md`.**

Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints for review

Which approach?
