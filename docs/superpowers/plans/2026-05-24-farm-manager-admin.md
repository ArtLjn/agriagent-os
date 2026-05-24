# Farm Manager PC 管理端 + 配置重构 + 多用户预留 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建后端 YAML 配置系统、farm_id 多租户隔离基础、以及 React + Ant Design 的 PC 管理端（含内嵌 + 独立 API Tester）。

**Architecture:** 后端配置从 .env 迁移到 config.yaml（Pydantic Settings custom source）。新增 Farm 实体，全部业务表加 farm_id 外键，通过 get_current_farm 依赖注入实现当前阶段硬编码返回 farm_id=1、未来可替换为 JWT。前端 admin-web 为独立 Vite 项目，Ant Design CRUD 页面 + 双模式 API 调试面板。

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy / Pydantic Settings + pyyaml | React 18 / Vite 5 / TypeScript / Ant Design 5 / Axios / React Router 6

---

## 文件结构总览

### 后端新建文件
```
backend/
├── config.yaml.example          # YAML 配置模板（含注释）
├── config.yaml                  # 实际配置（.gitignore 忽略）
├── app/
│   ├── models/farm.py           # Farm 模型
│   └── core/
│       └── seed.py              # 种子数据（默认农场）
```

### 后端修改文件
```
backend/
├── requirements.txt             # +pyyaml
├── .gitignore                   # +config.yaml
├── app/
│   ├── main.py                  # lifespan 添加种子数据
│   ├── core/config.py           # Settings 改为嵌套模型 + YAML source
│   ├── api/deps.py              # 新增 get_current_farm
│   ├── models/__init__.py       # 导出 Farm
│   ├── models/crop.py           # CropTemplate +farm_id
│   ├── models/cycle.py          # CropCycle +farm_id
│   ├── models/log.py            # FarmLog +farm_id
│   ├── models/cost.py           # CostRecord +farm_id
│   ├── models/agent.py          # AdviceRecord/ReportRecord +farm_id
│   ├── api/crop.py              # 注入 farm 参数
│   ├── api/cycle.py             # 注入 farm 参数
│   ├── api/log.py               # 注入 farm 参数
│   ├── api/cost.py              # 注入 farm 参数
│   ├── api/agent.py             # 注入 farm 参数
│   ├── services/crop_service.py     # 查询 +farm_id 过滤
│   ├── services/cycle_service.py    # 查询 +farm_id 过滤
│   ├── services/cost_service.py     # 查询 +farm_id 过滤
│   └── services/agent_service.py    # 查询 +farm_id 过滤
```

### 前端新建文件（admin-web/）
```
admin-web/
├── package.json
├── tsconfig.json
├── tsconfig.app.json
├── tsconfig.node.json
├── vite.config.ts
├── index.html
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── vite-env.d.ts
│   ├── api/
│   │   ├── client.ts
│   │   ├── crops.ts
│   │   ├── cycles.ts
│   │   ├── logs.ts
│   │   ├── costs.ts
│   │   ├── agent.ts
│   │   └── weather.ts
│   ├── layouts/
│   │   └── AdminLayout.tsx
│   ├── components/
│   │   └── ApiDebugger/
│   │       ├── index.tsx
│   │       ├── RequestEditor.tsx
│   │       └── ResponsePanel.tsx
│   └── pages/
│       ├── Dashboard/index.tsx
│       ├── Crops/index.tsx
│       ├── Cycles/index.tsx
│       ├── Cycles/Detail.tsx
│       ├── Logs/index.tsx
│       ├── Costs/index.tsx
│       ├── Agent/index.tsx
│       ├── Weather/index.tsx
│       └── ApiTester/index.tsx
```

---

## Phase 1: 后端配置静态化（yaml-config）

### Task 1: 添加 pyyaml 依赖

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: 添加 pyyaml 到 requirements.txt**

在 `backend/requirements.txt` 末尾添加：

```
pyyaml==6.0.2
```

- [ ] **Step 2: 安装依赖**

Run: `cd backend && pip install pyyaml==6.0.2`
Expected: `Successfully installed pyyaml-6.0.2`

- [ ] **Step 3: Commit**

```bash
git add backend/requirements.txt
git commit -m "chore: add pyyaml dependency for YAML config support"
```

---

### Task 2: 创建 config.yaml 配置文件

**Files:**
- Create: `backend/config.yaml.example`
- Modify: `backend/.gitignore`（如果没有则创建）

- [ ] **Step 1: 创建 config.yaml.example**

```yaml
# Farm Manager 后端配置文件
# 使用方法: cp config.yaml.example config.yaml
# 环境变量会覆盖 YAML 中的同名配置

server:
  host: "0.0.0.0"    # 监听地址
  port: 8000          # 监听端口

database:
  url: "sqlite:///./farm_manager.db"  # 数据库连接地址

ai:
  model: "qwen3.5-plus-2026-04-20"                        # LLM 模型名称
  api_key: ""                                              # LLM API 密钥（必填）
  base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"  # LLM API 地址

weather:
  latitude: 34.26    # 天气查询纬度（默认徐州）
  longitude: 117.18  # 天气查询经度（默认徐州）
```

- [ ] **Step 2: 创建实际的 config.yaml（复制模板）**

Run: `cp backend/config.yaml.example backend/config.yaml`

- [ ] **Step 3: 创建/更新 .gitignore**

在 `backend/.gitignore` 中添加：

```
config.yaml
*.db
.venv/
__pycache__/
```

- [ ] **Step 4: Commit**

```bash
git add backend/config.yaml.example backend/.gitignore
git commit -m "chore: add config.yaml template and gitignore"
```

---

### Task 3: 重构 Settings 支持 YAML

**Files:**
- Modify: `backend/app/core/config.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_config.py`：

```python
"""测试 YAML 配置加载。"""

import os
import tempfile

import pytest
import yaml


class TestYamlConfig:
    """YAML 配置加载测试。"""

    def test_load_from_yaml_file(self, tmp_path):
        """从 YAML 文件读取配置。"""
        config_data = {
            "server": {"host": "127.0.0.1", "port": 9000},
            "database": {"url": "sqlite:///./test.db"},
            "ai": {"model": "test-model", "api_key": "test-key", "base_url": "http://localhost:11434"},
            "weather": {"latitude": 39.9, "longitude": 116.4},
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config_data))

        # 动态导入以使用指定 config 路径
        from app.core.config import Settings

        settings = Settings(_config_path=str(config_file))
        assert settings.server.host == "127.0.0.1"
        assert settings.server.port == 9000
        assert settings.ai.api_key == "test-key"
        assert settings.weather.latitude == 39.9

    def test_default_values_when_no_yaml(self):
        """YAML 文件不存在时使用默认值。"""
        from app.core.config import Settings

        settings = Settings(_config_path="/nonexistent/config.yaml")
        assert settings.server.host == "0.0.0.0"
        assert settings.server.port == 8000
        assert settings.database.url == "sqlite:///./farm_manager.db"

    def test_env_var_overrides_yaml(self, tmp_path):
        """环境变量优先级高于 YAML 文件。"""
        config_data = {
            "ai": {"api_key": "yaml-key", "base_url": "http://yaml-url"},
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config_data))

        os.environ["AI_API_KEY"] = "env-key"
        try:
            from app.core.config import Settings

            settings = Settings(_config_path=str(config_file))
            assert settings.ai.api_key == "env-key"
        finally:
            del os.environ["AI_API_KEY"]

    def test_backward_compatible_attributes(self):
        """Settings 保持向后兼容的扁平属性访问。"""
        from app.core.config import Settings

        settings = Settings(_config_path="/nonexistent/config.yaml")
        assert settings.database_url == "sqlite:///./farm_manager.db"
        assert settings.project_name == "Farm Manager API"
        assert settings.ai_model == "qwen3.5-plus-2026-04-20"
        assert settings.weather_latitude == 34.26
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_config.py -v`
Expected: FAIL — `Settings` 不接受 `_config_path`，也没有嵌套属性

- [ ] **Step 3: 重写 config.py**

```python
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel
from pydantic_settings import BaseSettings


class ServerConfig(BaseModel):
    """服务器配置。"""

    host: str = "0.0.0.0"
    port: int = 8000


class DatabaseConfig(BaseModel):
    """数据库配置。"""

    url: str = "sqlite:///./farm_manager.db"


class AIConfig(BaseModel):
    """AI 模型配置。"""

    model: str = "qwen3.5-plus-2026-04-20"
    api_key: str = ""
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"


class WeatherConfig(BaseModel):
    """天气服务配置。"""

    latitude: float = 34.26
    longitude: float = 117.18


class Settings(BaseSettings):
    """应用配置，从 config.yaml 读取，环境变量可覆盖。"""

    server: ServerConfig = ServerConfig()
    database: DatabaseConfig = DatabaseConfig()
    ai: AIConfig = AIConfig()
    weather: WeatherConfig = WeatherConfig()
    project_name: str = "Farm Manager API"

    def __init__(self, _config_path: Optional[str] = None, **kwargs):
        if _config_path:
            yaml_data = self._load_yaml(_config_path)
            # YAML 值作为默认，kwargs（含环境变量）优先
            merged = {**yaml_data, **kwargs}
            super().__init__(**merged)
        else:
            config_path = Path(__file__).parent.parent.parent / "config.yaml"
            if config_path.exists():
                yaml_data = self._load_yaml(str(config_path))
                merged = {**yaml_data, **kwargs}
                super().__init__(**merged)
            else:
                super().__init__(**kwargs)

    @staticmethod
    def _load_yaml(path: str) -> dict:
        """从 YAML 文件加载配置。"""
        with open(path) as f:
            return yaml.safe_load(f) or {}

    # 向后兼容的扁平属性
    @property
    def database_url(self) -> str:
        return self.database.url

    @property
    def ai_model(self) -> str:
        return self.ai.model

    @property
    def ai_api_key(self) -> str:
        return self.ai.api_key

    @property
    def ai_base_url(self) -> str:
        return self.ai.base_url

    @property
    def weather_latitude(self) -> float:
        return self.weather.latitude

    @property
    def weather_longitude(self) -> float:
        return self.weather.longitude


settings = Settings()

__all__ = ["Settings", "settings"]
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_config.py -v`
Expected: 4 PASSED

- [ ] **Step 5: 运行全部已有测试确认无回归**

Run: `cd backend && python -m pytest tests/ -v --timeout=30`
Expected: 全部通过（可能有个别 agent 相关测试因 LLM mock 需要调整，记录失败项）

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/config.py backend/tests/test_config.py
git commit -m "refactor: migrate Settings from .env to config.yaml with nested model"
```

---

## Phase 2: 多租户基础（multi-tenant-foundation）

### Task 4: 创建 Farm 模型

**Files:**
- Create: `backend/app/models/farm.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_farm_model.py`：

```python
"""测试 Farm 模型。"""

from fastapi.testclient import TestClient

from app.main import app
from app.core.database import Base, engine

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_db():
    """每个测试前重建表。"""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


class TestFarmModel:
    """Farm 模型测试。"""

    def test_default_farm_seeded_on_startup(self):
        """启动时自动播种默认农场。"""
        # lifespan 已在 TestClient 创建时执行
        # 验证 farms 表有默认记录
        from app.core.database import SessionLocal
        from app.models.farm import Farm

        db = SessionLocal()
        farm = db.query(Farm).filter(Farm.id == 1).first()
        db.close()
        assert farm is not None
        assert farm.name == "默认农场"
```

注意：此测试依赖 Task 6 的种子数据，先写测试框架，种子数据在 Task 6 补充。

- [ ] **Step 2: 创建 farm.py 模型**

```python
from sqlalchemy import Column, DateTime, Integer, String, func

from app.core.database import Base


class Farm(Base):
    """农场模型，作为多租户的顶级隔离实体。"""

    __tablename__ = "farms"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    owner_name = Column(String, nullable=True)
    location = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 3: 更新 models/__init__.py**

在 `backend/app/models/__init__.py` 顶部 import 区添加：

```python
from app.models.farm import Farm
```

并在 `__all__` 列表开头添加 `"Farm"`。

完整文件：

```python
from app.models.farm import Farm
from app.models.crop import CropTemplate, GrowthStage
from app.models.cycle import CropCycle, CycleStage
from app.models.log import FarmLog
from app.models.cost import CostRecord
from app.models.agent import AdviceRecord, ReportRecord

__all__ = [
    "Farm",
    "CropTemplate",
    "GrowthStage",
    "CropCycle",
    "CycleStage",
    "FarmLog",
    "CostRecord",
    "AdviceRecord",
    "ReportRecord",
]
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/farm.py backend/app/models/__init__.py backend/tests/test_farm_model.py
git commit -m "feat: add Farm model for multi-tenant foundation"
```

---

### Task 5: 所有业务模型添加 farm_id

**Files:**
- Modify: `backend/app/models/crop.py`
- Modify: `backend/app/models/cycle.py`
- Modify: `backend/app/models/log.py`
- Modify: `backend/app/models/cost.py`
- Modify: `backend/app/models/agent.py`

- [ ] **Step 1: 修改 crop.py — CropTemplate 添加 farm_id**

在 `CropTemplate` 类中，`id` 列之后添加：

```python
farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False, default=1)
```

需要添加 import：`from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func`

完整的 CropTemplate：

```python
class CropTemplate(Base):
    """作物模板模型，定义一种作物的基本信息及其生长阶段。"""

    __tablename__ = "crop_templates"

    id = Column(Integer, primary_key=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False, default=1)
    name = Column(String, nullable=False)
    variety = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    stages = relationship(
        "GrowthStage",
        back_populates="crop_template",
        cascade="all, delete-orphan",
    )
```

- [ ] **Step 2: 修改 cycle.py — CropCycle 添加 farm_id**

在 `CropCycle` 类中，`id` 列之后添加：

```python
farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False, default=1)
```

- [ ] **Step 3: 修改 log.py — FarmLog 添加 farm_id**

在 `FarmLog` 类中，`id` 列之后添加：

```python
farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False, default=1)
```

需要添加 import：`from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, func`

- [ ] **Step 4: 修改 cost.py — CostRecord 添加 farm_id**

在 `CostRecord` 类中，`id` 列之后添加：

```python
farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False, default=1)
```

需要添加 import：`from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime, ForeignKey, func`

- [ ] **Step 5: 修改 agent.py — AdviceRecord 和 ReportRecord 添加 farm_id**

两个类都在 `id` 列之后添加：

```python
farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False, default=1)
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/crop.py backend/app/models/cycle.py backend/app/models/log.py backend/app/models/cost.py backend/app/models/agent.py
git commit -m "feat: add farm_id foreign key to all business tables"
```

---

### Task 6: 种子数据 + get_current_farm 依赖注入

**Files:**
- Create: `backend/app/core/seed.py`
- Modify: `backend/app/api/deps.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: 创建 seed.py**

```python
from sqlalchemy.orm import Session

from app.models.farm import Farm


def seed_default_farm(db: Session) -> None:
    """播种默认农场数据（id=1）。"""
    existing = db.query(Farm).filter(Farm.id == 1).first()
    if existing:
        return
    db.add(Farm(id=1, name="默认农场", owner_name="默认农户"))
    db.commit()
```

- [ ] **Step 2: 添加 get_current_farm 到 deps.py**

在 `backend/app/api/deps.py` 中追加：

```python
from typing import Generator

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.farm import Farm


def get_db() -> Generator[Session, None, None]:
    """获取数据库会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_farm(db: Session = Depends(get_db)) -> Farm:
    """获取当前请求关联的农场。

    当前阶段硬编码返回 farm_id=1，未来替换为 JWT 解析。
    """
    farm = db.query(Farm).filter(Farm.id == 1).first()
    if not farm:
        raise HTTPException(status_code=404, detail="No default farm found")
    return farm
```

- [ ] **Step 3: 更新 main.py lifespan 添加种子数据**

```python
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import agent, crop, cycle, log, cost, weather
from app.core.config import settings
from app.core.database import SessionLocal, engine, Base
from app.core.seed import seed_default_farm
from app.models import Farm  # 确保模型注册


@asynccontextmanager
async def lifespan(app: FastAPI):
    await asyncio.to_thread(Base.metadata.create_all, bind=engine)
    db = SessionLocal()
    try:
        seed_default_farm(db)
    finally:
        db.close()
    yield


app = FastAPI(title=settings.project_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(crop.router)
app.include_router(cycle.router)
app.include_router(log.router)
app.include_router(cost.router)
app.include_router(agent.router)
app.include_router(weather.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
```

- [ ] **Step 4: 删除旧数据库，验证重建**

Run: `rm -f backend/farm_manager.db && cd backend && python -c "from app.main import app; print('OK')"`
Expected: `OK`

- [ ] **Step 5: 运行测试**

Run: `cd backend && python -m pytest tests/test_farm_model.py -v`
Expected: PASSED — 默认农场已播种

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/seed.py backend/app/api/deps.py backend/app/main.py
git commit -m "feat: add seed data and get_current_farm dependency injection"
```

---

### Task 7: 修改 Service 层添加 farm_id 过滤

**Files:**
- Modify: `backend/app/services/crop_service.py`
- Modify: `backend/app/services/cycle_service.py`
- Modify: `backend/app/services/cost_service.py`
- Modify: `backend/app/services/agent_service.py`

每个 service 函数需添加 `farm_id: int` 参数，查询追加 `.filter(Model.farm_id == farm_id)`，创建时填充 `farm_id`。

- [ ] **Step 1: 修改 crop_service.py**

```python
from sqlalchemy.orm import Session

from app.models.crop import CropTemplate, GrowthStage
from app.schemas.crop import CropTemplateCreate


def create_crop_template(db: Session, template: CropTemplateCreate, farm_id: int) -> CropTemplate:
    """创建作物模板及其生长阶段。"""
    db_template = CropTemplate(name=template.name, variety=template.variety, farm_id=farm_id)
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


def get_crop_templates(db: Session, farm_id: int) -> list[CropTemplate]:
    """获取当前农场所有作物模板。"""
    return db.query(CropTemplate).filter(CropTemplate.farm_id == farm_id).all()


def get_crop_template(db: Session, template_id: int, farm_id: int) -> CropTemplate | None:
    """根据 ID 获取单个作物模板。"""
    return db.query(CropTemplate).filter(
        CropTemplate.id == template_id,
        CropTemplate.farm_id == farm_id,
    ).first()


__all__ = ["create_crop_template", "get_crop_templates", "get_crop_template"]
```

- [ ] **Step 2: 修改 cycle_service.py**

所有函数签名添加 `farm_id: int` 参数：
- `create_crop_cycle(db, cycle, farm_id)` — 查模板加 `farm_id` 过滤，创建时填 `farm_id`
- `get_crop_cycles(db, farm_id)` — 加 `farm_id` 过滤
- `get_crop_cycle(db, cycle_id, farm_id)` — 加 `farm_id` 过滤
- `update_stage` — 不变（stage 不直接有 farm_id）
- `_recalculate_stages` — 不变

`create_crop_cycle` 中的模板查询改为：
```python
template = db.query(CropTemplate).filter(
    CropTemplate.id == cycle.crop_template_id,
    CropTemplate.farm_id == farm_id,
).first()
```

`CropCycle` 创建时加 `farm_id=farm_id`。

`get_crop_cycles` 改为：
```python
return db.query(CropCycle).filter(CropCycle.farm_id == farm_id).all()
```

`get_crop_cycle` 改为：
```python
return db.query(CropCycle).filter(
    CropCycle.id == cycle_id,
    CropCycle.farm_id == farm_id,
).first()
```

- [ ] **Step 3: 修改 cost_service.py**

所有函数签名添加 `farm_id: int` 参数：
- `create_record(db, record, farm_id)` — 创建时填 `farm_id`
- `get_records(db, farm_id, ...)` — 加 `farm_id` 过滤
- `get_cycle_profit(db, cycle_id, farm_id)` — 查询加 `farm_id` 过滤
- `get_yearly_summary(db, year, farm_id)` — 查询加 `farm_id` 过滤

- [ ] **Step 4: 修改 agent_service.py**

所有函数签名添加 `farm_id: int` 参数：
- `chat_with_agent(db, message, cycle_id, farm_id)` — 创建记录时填 `farm_id`
- `get_daily_advice(db, cycle_id, farm_id)` — 创建记录时填 `farm_id`
- `generate_report(db, cycle_id, report_type, farm_id)` — 创建记录时填 `farm_id`
- `get_advice_history(db, cycle_id, limit, farm_id)` — 加 `farm_id` 过滤
- `get_report_history(db, cycle_id, limit, farm_id)` — 加 `farm_id` 过滤

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/crop_service.py backend/app/services/cycle_service.py backend/app/services/cost_service.py backend/app/services/agent_service.py
git commit -m "feat: add farm_id filtering to all service layer functions"
```

---

### Task 8: 修改 API 路由注入 farm 上下文

**Files:**
- Modify: `backend/app/api/crop.py`
- Modify: `backend/app/api/cycle.py`
- Modify: `backend/app/api/log.py`
- Modify: `backend/app/api/cost.py`
- Modify: `backend/app/api/agent.py`

每个路由函数添加 `farm: Farm = Depends(get_current_farm)` 参数，调用 service 时传 `farm_id=farm.id`。

- [ ] **Step 1: 修改 crop.py**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_farm
from app.models.farm import Farm
from app.schemas.crop import CropTemplateCreate, CropTemplateResponse
from app.services import crop_service

router = APIRouter(prefix="/crops", tags=["crops"])


@router.post("/templates", response_model=CropTemplateResponse)
def create_template(
    template: CropTemplateCreate,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """创建作物模板。"""
    return crop_service.create_crop_template(db, template, farm_id=farm.id)


@router.get("/templates", response_model=list[CropTemplateResponse])
def list_templates(
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """获取所有作物模板列表。"""
    return crop_service.get_crop_templates(db, farm_id=farm.id)


@router.get("/templates/{template_id}", response_model=CropTemplateResponse)
def get_template(
    template_id: int,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """根据 ID 获取作物模板详情。"""
    template = crop_service.get_crop_template(db, template_id, farm_id=farm.id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


__all__ = ["router"]
```

- [ ] **Step 2: 修改 cycle.py**

每个函数添加 `farm: Farm = Depends(get_current_farm)` 参数。调用 service 时传 `farm_id=farm.id`。

- [ ] **Step 3: 修改 log.py**

需要同时修改 service 层 — `backend/app/services/` 下没有独立的 log_service（当前 log API 直接操作数据库）。需要：
1. 创建 `backend/app/services/log_service.py`（如果 log 逻辑在 API 层内联），或在 API 层直接添加 farm_id 过滤。

查看 log.py 当前逻辑：创建和查询直接在路由中。添加 farm 参数后：

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_farm
from app.models.farm import Farm
from app.models.log import FarmLog
from app.schemas.log import FarmLogCreate, FarmLogResponse

router = APIRouter(prefix="/logs", tags=["logs"])


@router.post("", response_model=FarmLogResponse)
def create_log(
    log: FarmLogCreate,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """创建一条农事日志。"""
    db_log = FarmLog(
        farm_id=farm.id,
        cycle_id=log.cycle_id,
        operation_type=log.operation_type,
        operation_date=log.operation_date,
        operation_time=log.operation_time,
        note=log.note,
        photo_urls=log.photo_urls,
    )
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log


@router.get("", response_model=list[FarmLogResponse])
def list_logs(
    cycle_id: int | None = None,
    operation_type: str | None = None,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """查询农事日志列表。"""
    query = db.query(FarmLog).filter(FarmLog.farm_id == farm.id)
    if cycle_id is not None:
        query = query.filter(FarmLog.cycle_id == cycle_id)
    if operation_type is not None:
        query = query.filter(FarmLog.operation_type == operation_type)
    return query.all()


__all__ = ["router"]
```

- [ ] **Step 4: 修改 cost.py**

每个函数添加 `farm: Farm = Depends(get_current_farm)` 参数。调用 service 时传 `farm_id=farm.id`。

- [ ] **Step 5: 修改 agent.py**

每个函数添加 `farm: Farm = Depends(get_current_farm)` 参数。调用 service 时传 `farm_id=farm.id`。

- [ ] **Step 6: 运行全部测试**

Run: `cd backend && python -m pytest tests/ -v --timeout=30`
Expected: 修复因 `farm_id` 引入导致的失败用例（主要是 fixture 中需要先创建 Farm 种子数据）

- [ ] **Step 7: 启动后端验证 Swagger**

Run: `cd backend && python -m uvicorn app.main:app --reload`
访问 http://localhost:8000/docs，确认全部 20 个端点显示。

- [ ] **Step 8: Commit**

```bash
git add backend/app/api/crop.py backend/app/api/cycle.py backend/app/api/log.py backend/app/api/cost.py backend/app/api/agent.py
git commit -m "feat: inject farm context into all API routes"
```

---

### Task 9: 修复因 farm_id 引入的已有测试

**Files:**
- Modify: `backend/tests/test_crop.py`
- Modify: `backend/tests/test_cycle.py`
- Modify: `backend/tests/test_log.py`
- Modify: `backend/tests/test_cost.py`
- Modify: `backend/tests/test_agent_api.py`
- Modify: `backend/tests/test_agent_service.py`
- Modify: `backend/tests/test_agent_models.py`

所有 integration test 的 `clean_db` fixture 需要改为先 drop 再 create（确保 farms 表存在），然后插入默认农场种子数据。

- [ ] **Step 1: 创建公共 conftest.py**

创建 `backend/tests/conftest.py`：

```python
"""公共测试 fixtures。"""

import pytest
from fastapi.testclient import TestClient

from app.core.database import Base, SessionLocal, engine
from app.main import app
from app.models.farm import Farm


@pytest.fixture(autouse=True)
def clean_db():
    """每个测试前重建表并播种默认农场。"""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    db.add(Farm(id=1, name="默认农场"))
    db.commit()
    db.close()
    yield
```

- [ ] **Step 2: 删除各测试文件中的 autouse clean_db fixture**

从 `test_crop.py`、`test_cycle.py`、`test_log.py`、`test_cost.py`、`test_agent_models.py` 中删除重复的 `clean_db` fixture（已统一到 conftest.py）。

- [ ] **Step 3: 修改 service mock 测试中的 farm_id 参数**

`test_agent_service.py` 和 `test_agent_api.py` 中 mock service 函数时需添加 `farm_id` 参数。

- [ ] **Step 4: 运行全部测试**

Run: `cd backend && python -m pytest tests/ -v --timeout=30`
Expected: ALL PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/tests/conftest.py backend/tests/test_crop.py backend/tests/test_cycle.py backend/tests/test_log.py backend/tests/test_cost.py backend/tests/test_agent_api.py backend/tests/test_agent_service.py backend/tests/test_agent_models.py
git commit -m "test: update all tests for farm_id multi-tenant support"
```

---

## Phase 3: Admin-web 项目初始化

### Task 10: 创建 Vite + React + TS 项目

**Files:**
- Create: `admin-web/` 整个目录

- [ ] **Step 1: 创建 Vite 项目**

Run:
```bash
cd /Users/ljn/Documents/demo/explore
npm create vite@latest admin-web -- --template react-ts
```

- [ ] **Step 2: 安装核心依赖**

Run:
```bash
cd admin-web
npm install antd @ant-design/icons react-router-dom axios
```

- [ ] **Step 3: 配置 vite.config.ts**

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
```

- [ ] **Step 4: 清理 Vite 默认文件**

删除 `src/App.css`、`src/index.css`、`src/assets/` 等默认文件。

- [ ] **Step 5: Commit**

```bash
git add admin-web/
git commit -m "feat: initialize admin-web with Vite + React + TypeScript + Ant Design"
```

---

### Task 11: 创建布局和路由

**Files:**
- Create: `admin-web/src/layouts/AdminLayout.tsx`
- Modify: `admin-web/src/App.tsx`
- Modify: `admin-web/src/main.tsx`

- [ ] **Step 1: 创建 AdminLayout.tsx**

```tsx
import { useState } from 'react';
import { Layout, Menu } from 'antd';
import {
  DashboardOutlined,
  PlantOutlined,
  SwapOutlined,
  FileTextOutlined,
  DollarOutlined,
  RobotOutlined,
  CloudOutlined,
  ApiOutlined,
} from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router-dom';

const { Sider, Content, Header } = Layout;

const menuItems = [
  { key: '/', icon: <DashboardOutlined />, label: '仪表盘' },
  { key: '/crops', icon: <PlantOutlined />, label: '作物管理' },
  { key: '/cycles', icon: <SwapOutlined />, label: '茬口管理' },
  { key: '/logs', icon: <FileTextOutlined />, label: '农事日志' },
  { key: '/costs', icon: <DollarOutlined />, label: '成本记账' },
  { key: '/agent', icon: <RobotOutlined />, label: 'AI 助手' },
  { key: '/weather', icon: <CloudOutlined />, label: '天气预报' },
  { key: '/api-tester', icon: <ApiOutlined />, label: 'API Tester' },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider collapsible collapsed={collapsed} onCollapse={setCollapsed}>
        <div style={{ height: 32, margin: 16, color: '#fff', textAlign: 'center', fontSize: 18, fontWeight: 'bold' }}>
          {collapsed ? 'FM' : 'Farm Manager'}
        </div>
        <Menu
          theme="dark"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header style={{ background: '#fff', padding: '0 24px', fontSize: 20, fontWeight: 'bold' }}>
          Farm Manager 管理端
        </Header>
        <Content style={{ margin: 24 }}>{children}</Content>
      </Layout>
    </Layout>
  );
}
```

- [ ] **Step 2: 创建 App.tsx 路由配置**

```tsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import AdminLayout from './layouts/AdminLayout';
import Dashboard from './pages/Dashboard';
import Crops from './pages/Crops';
import Cycles from './pages/Cycles';
import Logs from './pages/Logs';
import Costs from './pages/Costs';
import Agent from './pages/Agent';
import Weather from './pages/Weather';
import ApiTester from './pages/ApiTester';

export default function App() {
  return (
    <ConfigProvider locale={zhCN}>
      <BrowserRouter>
        <AdminLayout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/crops" element={<Crops />} />
            <Route path="/cycles" element={<Cycles />} />
            <Route path="/logs" element={<Logs />} />
            <Route path="/costs" element={<Costs />} />
            <Route path="/agent" element={<Agent />} />
            <Route path="/weather" element={<Weather />} />
            <Route path="/api-tester" element={<ApiTester />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AdminLayout>
      </BrowserRouter>
    </ConfigProvider>
  );
}
```

- [ ] **Step 3: 更新 main.tsx**

```tsx
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
```

- [ ] **Step 4: 创建页面占位文件**

每个页面先创建最小占位组件，例如 `admin-web/src/pages/Dashboard/index.tsx`：

```tsx
export default function Dashboard() {
  return <div>Dashboard - 开发中</div>;
}
```

对 Crops、Cycles、Logs、Costs、Agent、Weather、ApiTester 各创建同样的占位。

- [ ] **Step 5: 启动开发服务器验证**

Run: `cd admin-web && npm run dev`
访问 http://localhost:5173，确认侧边栏导航正常，页面切换正常。

- [ ] **Step 6: Commit**

```bash
git add admin-web/src/
git commit -m "feat: add admin layout, routing, and page placeholders"
```

---

## Phase 4: Admin-web API 层

### Task 12: 创建 Axios 实例和 API 模块

**Files:**
- Create: `admin-web/src/api/client.ts`
- Create: `admin-web/src/api/crops.ts`
- Create: `admin-web/src/api/cycles.ts`
- Create: `admin-web/src/api/logs.ts`
- Create: `admin-web/src/api/costs.ts`
- Create: `admin-web/src/api/agent.ts`
- Create: `admin-web/src/api/weather.ts`

- [ ] **Step 1: 创建 client.ts**

```typescript
import axios from 'axios';

const apiClient = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error.response?.status, error.response?.data);
    return Promise.reject(error);
  },
);

export default apiClient;
```

- [ ] **Step 2: 创建 crops.ts**

```typescript
import apiClient from './client';

export interface GrowthStage {
  name: string;
  duration_days: number;
  order_index: number;
  key_tasks?: string;
}

export interface CropTemplate {
  id: number;
  name: string;
  variety?: string;
  stages: GrowthStage[];
}

export const listTemplates = () =>
  apiClient.get<CropTemplate[]>('/crops/templates');

export const getTemplate = (id: number) =>
  apiClient.get<CropTemplate>(`/crops/templates/${id}`);

export const createTemplate = (data: { name: string; variety?: string; stages: GrowthStage[] }) =>
  apiClient.post<CropTemplate>('/crops/templates', data);
```

- [ ] **Step 3: 创建 cycles.ts**

```typescript
import apiClient from './client';

export interface CycleStage {
  id: number;
  cycle_id: number;
  name: string;
  start_date: string;
  end_date: string;
  order_index: number;
  key_tasks?: string;
  is_current: boolean;
}

export interface CropCycle {
  id: number;
  name: string;
  crop_template_id: number;
  start_date: string;
  field_name?: string;
  status: string;
  stages: CycleStage[];
}

export interface CropCycleListItem {
  id: number;
  name: string;
  crop_template_name: string;
  start_date: string;
  status: string;
  current_stage_name?: string;
}

export const listCycles = () =>
  apiClient.get<CropCycleListItem[]>('/cycles');

export const getCycle = (id: number) =>
  apiClient.get<CropCycle>(`/cycles/${id}`);

export const createCycle = (data: { name: string; crop_template_id: number; start_date: string; field_name?: string }) =>
  apiClient.post<CropCycle>('/cycles', data);
```

- [ ] **Step 4: 创建 logs.ts**

```typescript
import apiClient from './client';

export interface FarmLog {
  id: number;
  cycle_id: number;
  operation_type: string;
  operation_date: string;
  operation_time?: string;
  note?: string;
  photo_urls?: string;
  created_at: string;
}

export const listLogs = (params?: { cycle_id?: number; operation_type?: string }) =>
  apiClient.get<FarmLog[]>('/logs', { params });

export const createLog = (data: { cycle_id: number; operation_type: string; operation_date: string; note?: string }) =>
  apiClient.post<FarmLog>('/logs', data);
```

- [ ] **Step 5: 创建 costs.ts**

```typescript
import apiClient from './client';

export interface CostRecord {
  id: number;
  cycle_id?: number;
  record_type: string;
  category: string;
  amount: string;
  record_date: string;
  note?: string;
}

export interface CycleProfit {
  cycle_id: number;
  total_cost: string;
  total_income: string;
  net_profit: string;
}

export interface YearlySummary {
  year: number;
  total_cost: string;
  total_income: string;
  net_profit: string;
  by_category: Record<string, string>;
}

export const listRecords = (params?: { cycle_id?: number; category?: string }) =>
  apiClient.get<CostRecord[]>('/costs', { params });

export const createRecord = (data: { cycle_id?: number; record_type: string; category: string; amount: string; record_date: string; note?: string }) =>
  apiClient.post<CostRecord>('/costs', data);

export const getCycleProfit = (cycleId: number) =>
  apiClient.get<CycleProfit>(`/costs/cycles/${cycleId}/profit`);

export const getYearlySummary = (year: number) =>
  apiClient.get<YearlySummary>(`/costs/summary/${year}`);
```

- [ ] **Step 6: 创建 agent.ts**

```typescript
import apiClient from './client';

export const chat = (message: string, cycleId?: number) =>
  apiClient.post('/agent/chat', { message, cycle_id: cycleId });

export const getDailyAdvice = (cycleId?: number) =>
  apiClient.get('/agent/daily', { params: { cycle_id: cycleId } });

export const generateReport = (reportType: string = 'weekly', cycleId?: number) =>
  apiClient.post('/agent/report', { report_type: reportType, cycle_id: cycleId });

export const getAdviceHistory = (params?: { cycle_id?: number; limit?: number }) =>
  apiClient.get('/agent/advice-history', { params });

export const getReportHistory = (params?: { cycle_id?: number; limit?: number }) =>
  apiClient.get('/agent/report-history', { params });
```

- [ ] **Step 7: 创建 weather.ts**

```typescript
import apiClient from './client';

export const getForecast = (days: number = 7) =>
  apiClient.get('/weather/forecast', { params: { days } });
```

- [ ] **Step 8: Commit**

```bash
git add admin-web/src/api/
git commit -m "feat: add API client layer with all endpoint modules"
```

---

## Phase 5: Admin-web 公共组件 — ApiDebugger

### Task 13: 创建 ApiDebugger 组件

**Files:**
- Create: `admin-web/src/components/ApiDebugger/index.tsx`
- Create: `admin-web/src/components/ApiDebugger/RequestEditor.tsx`
- Create: `admin-web/src/components/ApiDebugger/ResponsePanel.tsx`

- [ ] **Step 1: 创建 RequestEditor.tsx**

```tsx
import { Input, Select, Row, Col } from 'antd';

const { TextArea } = Input;

const METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'];

interface Props {
  method: string;
  url: string;
  body: string;
  onMethodChange: (v: string) => void;
  onUrlChange: (v: string) => void;
  onBodyChange: (v: string) => void;
}

export default function RequestEditor({ method, url, body, onMethodChange, onUrlChange, onBodyChange }: Props) {
  return (
    <div>
      <Row gutter={8} style={{ marginBottom: 12 }}>
        <Col span={6}>
          <Select value={method} onChange={onMethodChange} options={METHODS.map((m) => ({ value: m }))} style={{ width: '100%' }} />
        </Col>
        <Col span={18}>
          <Input value={url} onChange={(e) => onUrlChange(e.target.value)} placeholder="/api/endpoint" />
        </Col>
      </Row>
      {(method === 'POST' || method === 'PUT' || method === 'PATCH') && (
        <TextArea
          value={body}
          onChange={(e) => onBodyChange(e.target.value)}
          rows={8}
          placeholder='{"key": "value"}'
          style={{ fontFamily: 'monospace' }}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 2: 创建 ResponsePanel.tsx**

```tsx
import { Tag } from 'antd';

interface Props {
  status: number | null;
  duration: number | null;
  body: string;
}

function statusColor(code: number): string {
  if (code < 300) return 'green';
  if (code < 400) return 'orange';
  return 'red';
}

export default function ResponsePanel({ status, duration, body }: Props) {
  return (
    <div>
      <div style={{ marginBottom: 8 }}>
        {status !== null && <Tag color={statusColor(status)}>{status}</Tag>}
        {duration !== null && <Tag>{duration}ms</Tag>}
      </div>
      <pre style={{ background: '#f5f5f5', padding: 12, borderRadius: 4, maxHeight: 400, overflow: 'auto', fontSize: 12 }}>
        {body || '无响应'}
      </pre>
    </div>
  );
}
```

- [ ] **Step 3: 创建 ApiDebugger/index.tsx**

```tsx
import { useState } from 'react';
import { Button, Drawer, Space, message } from 'antd';
import { SendOutlined } from '@ant-design/icons';
import RequestEditor from './RequestEditor';
import ResponsePanel from './ResponsePanel';
import apiClient from '../../api/client';

interface Props {
  open: boolean;
  onClose: () => void;
  defaultMethod?: string;
  defaultUrl?: string;
  defaultBody?: string;
}

export default function ApiDebugger({ open, onClose, defaultMethod = 'GET', defaultUrl = '', defaultBody = '{}' }: Props) {
  const [method, setMethod] = useState(defaultMethod);
  const [url, setUrl] = useState(defaultUrl);
  const [body, setBody] = useState(defaultBody);
  const [status, setStatus] = useState<number | null>(null);
  const [duration, setDuration] = useState<number | null>(null);
  const [responseBody, setResponseBody] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSend = async () => {
    setLoading(true);
    const start = Date.now();
    try {
      const config: Record<string, unknown> = { method: method.toLowerCase(), url };
      if (['POST', 'PUT', 'PATCH'].includes(method)) {
        try {
          config.data = JSON.parse(body);
        } catch {
          message.error('请求体 JSON 格式错误');
          setLoading(false);
          return;
        }
      }
      const res = await apiClient.request(config);
      setStatus(res.status);
      setDuration(Date.now() - start);
      setResponseBody(JSON.stringify(res.data, null, 2));
    } catch (err: unknown) {
      const axiosErr = err as { response?: { status?: number; data?: unknown } };
      setStatus(axiosErr.response?.status ?? 0);
      setDuration(Date.now() - start);
      setResponseBody(JSON.stringify(axiosErr.response?.data ?? { error: String(err) }, null, 2));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Drawer title="API 调试" open={open} onClose={onClose} width={640}>
      <Space direction="vertical" style={{ width: '100%' }} size="large">
        <RequestEditor
          method={method}
          url={url}
          body={body}
          onMethodChange={setMethod}
          onUrlChange={setUrl}
          onBodyChange={setBody}
        />
        <Button type="primary" icon={<SendOutlined />} loading={loading} onClick={handleSend} block>
          发送请求
        </Button>
        <ResponsePanel status={status} duration={duration} body={responseBody} />
      </Space>
    </Drawer>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add admin-web/src/components/
git commit -m "feat: add reusable ApiDebugger component"
```

---

## Phase 6: Admin-web 业务页面

### Task 14: Dashboard 仪表盘页面

**Files:**
- Modify: `admin-web/src/pages/Dashboard/index.tsx`

- [ ] **Step 1: 实现 Dashboard**

```tsx
import { useEffect, useState } from 'react';
import { Card, Col, Row, Statistic, Typography, Alert, Spin } from 'antd';
import { CheckCircleOutlined, DollarOutlined, CloudOutlined, RobotOutlined } from '@ant-design/icons';
import * as cyclesApi from '../../api/cycles';
import * as costsApi from '../../api/costs';
import * as weatherApi from '../../api/weather';
import * as agentApi from '../../api/agent';

export default function Dashboard() {
  const [loading, setLoading] = useState(true);
  const [cycleCount, setCycleCount] = useState(0);
  const [weather, setWeather] = useState<string>('');
  const [advice, setAdvice] = useState<string>('');
  const [summary, setSummary] = useState<{ total_cost: string; total_income: string; net_profit: string } | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    const year = new Date().getFullYear();
    Promise.allSettled([
      cyclesApi.listCycles(),
      costsApi.getYearlySummary(year),
      weatherApi.getForecast(1),
      agentApi.getDailyAdvice(),
    ]).then(([cyclesRes, costsRes, weatherRes, adviceRes]) => {
      if (cyclesRes.status === 'fulfilled') setCycleCount(cyclesRes.value.data.length);
      if (costsRes.status === 'fulfilled') setSummary(costsRes.value.data);
      if (weatherRes.status === 'fulfilled') {
        const d = weatherRes.value.data?.daily;
        if (d?.temperature_2m_max?.[0]) setWeather(`${d.temperature_2m_max[0]}°C`);
      }
      if (adviceRes.status === 'fulfilled') {
        const a = adviceRes.value.data;
        setAdvice(a?.advice ? a.advice.slice(0, 100) + '...' : '暂无建议');
      }
      if (cyclesRes.status === 'rejected') setError('后端连接失败');
      setLoading(false);
    });
  }, []);

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;
  if (error) return <Alert type="error" message={error} />;

  return (
    <div>
      <Typography.Title level={3}>仪表盘</Typography.Title>
      <Row gutter={16}>
        <Col span={6}>
          <Card><Statistic title="种植周期" value={cycleCount} prefix={<CheckCircleOutlined />} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="今日天气" value={weather || '--'} prefix={<CloudOutlined />} /></Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="年度净利润"
              value={summary?.net_profit ?? '--'}
              prefix={<DollarOutlined />}
              valueStyle={{ color: summary && Number(summary.net_profit) >= 0 ? '#3f8600' : '#cf1322' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="AI 建议" value={advice || '--'} prefix={<RobotOutlined />} valueStyle={{ fontSize: 14 }} />
          </Card>
        </Col>
      </Row>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add admin-web/src/pages/Dashboard/
git commit -m "feat: implement Dashboard page"
```

---

### Task 15: 作物管理页面

**Files:**
- Modify: `admin-web/src/pages/Crops/index.tsx`

- [ ] **Step 1: 实现 Crops 页面（Table + Modal + 内嵌调试）**

```tsx
import { useEffect, useState } from 'react';
import { Table, Button, Modal, Form, Input, InputNumber, Space, message, Drawer } from 'antd';
import { PlusOutlined, BugOutlined } from '@ant-design/icons';
import { listTemplates, createTemplate, type CropTemplate } from '../../api/crops';
import ApiDebugger from '../../components/ApiDebugger';

export default function Crops() {
  const [data, setData] = useState<CropTemplate[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [debugOpen, setDebugOpen] = useState(false);
  const [form] = Form.useForm();

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await listTemplates();
      setData(res.data);
    } catch {
      message.error('加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, []);

  const handleCreate = async () => {
    const values = await form.validateFields();
    try {
      await createTemplate(values);
      message.success('创建成功');
      setModalOpen(false);
      form.resetFields();
      fetchData();
    } catch {
      message.error('创建失败');
    }
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: '名称', dataIndex: 'name' },
    { title: '品种', dataIndex: 'variety' },
    { title: '阶段数', key: 'stages', render: (_: unknown, r: CropTemplate) => r.stages?.length ?? 0 },
  ];

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>新建模板</Button>
        <Button icon={<BugOutlined />} onClick={() => setDebugOpen(true)}>调试</Button>
      </Space>
      <Table rowKey="id" dataSource={data} columns={columns} loading={loading} />

      <Modal title="新建作物模板" open={modalOpen} onOk={handleCreate} onCancel={() => setModalOpen(false)}>
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="名称" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="variety" label="品种"><Input /></Form.Item>
        </Form>
      </Modal>

      <ApiDebugger
        open={debugOpen}
        onClose={() => setDebugOpen(false)}
        defaultMethod="GET"
        defaultUrl="/crops/templates"
      />
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add admin-web/src/pages/Crops/
git commit -m "feat: implement Crops management page with inline debugger"
```

---

### Task 16: 茬口管理页面

**Files:**
- Modify: `admin-web/src/pages/Cycles/index.tsx`
- Create: `admin-web/src/pages/Cycles/Detail.tsx`

- [ ] **Step 1: 实现 Cycles 列表页**

```tsx
import { useEffect, useState } from 'react';
import { Table, Button, Modal, Form, Input, DatePicker, Select, Space, message, Tag } from 'antd';
import { PlusOutlined, BugOutlined, EyeOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { listCycles, createCycle, type CropCycleListItem } from '../../api/cycles';
import { listTemplates, type CropTemplate } from '../../api/crops';
import ApiDebugger from '../../components/ApiDebugger';

export default function Cycles() {
  const [data, setData] = useState<CropCycleListItem[]>([]);
  const [templates, setTemplates] = useState<CropTemplate[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [debugOpen, setDebugOpen] = useState(false);
  const [form] = Form.useForm();
  const navigate = useNavigate();

  const fetchData = async () => {
    setLoading(true);
    try {
      const [cyclesRes, tplRes] = await Promise.all([listCycles(), listTemplates()]);
      setData(cyclesRes.data);
      setTemplates(tplRes.data);
    } catch {
      message.error('加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, []);

  const handleCreate = async () => {
    const values = await form.validateFields();
    try {
      await createCycle({ ...values, start_date: values.start_date.format('YYYY-MM-DD') });
      message.success('创建成功');
      setModalOpen(false);
      form.resetFields();
      fetchData();
    } catch {
      message.error('创建失败');
    }
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: '名称', dataIndex: 'name' },
    { title: '作物', dataIndex: 'crop_template_name' },
    { title: '开始日期', dataIndex: 'start_date' },
    { title: '状态', dataIndex: 'status', render: (s: string) => <Tag color={s === 'active' ? 'green' : 'default'}>{s}</Tag> },
    { title: '当前阶段', dataIndex: 'current_stage_name' },
    { title: '操作', render: (_: unknown, r: CropCycleListItem) => (
      <Button icon={<EyeOutlined />} size="small" onClick={() => navigate(`/cycles/${r.id}`)}>详情</Button>
    )},
  ];

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>新建茬口</Button>
        <Button icon={<BugOutlined />} onClick={() => setDebugOpen(true)}>调试</Button>
      </Space>
      <Table rowKey="id" dataSource={data} columns={columns} loading={loading} />

      <Modal title="新建茬口" open={modalOpen} onOk={handleCreate} onCancel={() => setModalOpen(false)}>
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="名称" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="crop_template_id" label="作物模板" rules={[{ required: true }]}>
            <Select options={templates.map((t) => ({ value: t.id, label: t.name }))} />
          </Form.Item>
          <Form.Item name="start_date" label="开始日期" rules={[{ required: true }]}><DatePicker style={{ width: '100%' }} /></Form.Item>
          <Form.Item name="field_name" label="地块名称"><Input /></Form.Item>
        </Form>
      </Modal>

      <ApiDebugger open={debugOpen} onClose={() => setDebugOpen(false)} defaultMethod="GET" defaultUrl="/cycles" />
    </div>
  );
}
```

- [ ] **Step 2: 实现 Cycles/Detail.tsx**

```tsx
import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Descriptions, Timeline, Card, Button, Spin } from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import { getCycle, type CropCycle } from '../../api/cycles';

export default function CycleDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [cycle, setCycle] = useState<CropCycle | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    getCycle(Number(id))
      .then((res) => setCycle(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <Spin />;
  if (!cycle) return <div>未找到茬口</div>;

  return (
    <div>
      <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/cycles')} style={{ marginBottom: 16 }}>返回列表</Button>
      <Card title={cycle.name}>
        <Descriptions column={2}>
          <Descriptions.Item label="开始日期">{cycle.start_date}</Descriptions.Item>
          <Descriptions.Item label="地块">{cycle.field_name || '--'}</Descriptions.Item>
          <Descriptions.Item label="状态">{cycle.status}</Descriptions.Item>
        </Descriptions>
      </Card>
      <Card title="生长阶段" style={{ marginTop: 16 }}>
        <Timeline items={cycle.stages.map((s) => ({
          color: s.is_current ? 'green' : 'gray',
          children: (
            <div>
              <strong>{s.name}</strong> ({s.start_date} ~ {s.end_date}, {s.duration_days}天)
              {s.is_current && <span style={{ color: '#52c41a', marginLeft: 8 }}>当前阶段</span>}
              {s.key_tasks && <div style={{ color: '#666' }}>{s.key_tasks}</div>}
            </div>
          ),
        }))} />
      </Card>
    </div>
  );
}
```

- [ ] **Step 3: 在 App.tsx 添加详情路由**

在 `App.tsx` 的 Routes 中添加：
```tsx
<Route path="/cycles/:id" element={<CycleDetail />} />
```

需要在顶部 import：`import CycleDetail from './pages/Cycles/Detail';`

- [ ] **Step 4: Commit**

```bash
git add admin-web/src/pages/Cycles/ admin-web/src/App.tsx
git commit -m "feat: implement Cycles list and detail pages"
```

---

### Task 17: 农事日志页面

**Files:**
- Modify: `admin-web/src/pages/Logs/index.tsx`

- [ ] **Step 1: 实现 Logs 页面**

```tsx
import { useEffect, useState } from 'react';
import { Table, Button, Modal, Form, Input, DatePicker, Select, Space, message } from 'antd';
import { PlusOutlined, BugOutlined } from '@ant-design/icons';
import { listLogs, createLog, type FarmLog } from '../../api/logs';
import { listCycles, type CropCycleListItem } from '../../api/cycles';
import ApiDebugger from '../../components/ApiDebugger';

export default function Logs() {
  const [data, setData] = useState<FarmLog[]>([]);
  const [cycles, setCycles] = useState<CropCycleListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [debugOpen, setDebugOpen] = useState(false);
  const [filterCycleId, setFilterCycleId] = useState<number | undefined>();
  const [form] = Form.useForm();

  const fetchData = async () => {
    setLoading(true);
    try {
      const [logsRes, cyclesRes] = await Promise.all([
        listLogs(filterCycleId ? { cycle_id: filterCycleId } : undefined),
        listCycles(),
      ]);
      setData(logsRes.data);
      setCycles(cyclesRes.data);
    } catch {
      message.error('加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, [filterCycleId]);

  const handleCreate = async () => {
    const values = await form.validateFields();
    try {
      await createLog({ ...values, operation_date: values.operation_date.format('YYYY-MM-DD') });
      message.success('创建成功');
      setModalOpen(false);
      form.resetFields();
      fetchData();
    } catch {
      message.error('创建失败');
    }
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: '茬口ID', dataIndex: 'cycle_id', width: 80 },
    { title: '操作类型', dataIndex: 'operation_type' },
    { title: '日期', dataIndex: 'operation_date' },
    { title: '备注', dataIndex: 'note', ellipsis: true },
    { title: '创建时间', dataIndex: 'created_at' },
  ];

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>新增日志</Button>
        <Select
          placeholder="按茬口筛选"
          allowClear
          style={{ width: 200 }}
          value={filterCycleId}
          onChange={(v) => setFilterCycleId(v)}
          options={cycles.map((c) => ({ value: c.id, label: c.name }))}
        />
        <Button icon={<BugOutlined />} onClick={() => setDebugOpen(true)}>调试</Button>
      </Space>
      <Table rowKey="id" dataSource={data} columns={columns} loading={loading} />

      <Modal title="新增日志" open={modalOpen} onOk={handleCreate} onCancel={() => setModalOpen(false)}>
        <Form form={form} layout="vertical">
          <Form.Item name="cycle_id" label="茬口" rules={[{ required: true }]}>
            <Select options={cycles.map((c) => ({ value: c.id, label: c.name }))} />
          </Form.Item>
          <Form.Item name="operation_type" label="操作类型" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="operation_date" label="日期" rules={[{ required: true }]}><DatePicker style={{ width: '100%' }} /></Form.Item>
          <Form.Item name="note" label="备注"><Input.TextArea /></Form.Item>
        </Form>
      </Modal>

      <ApiDebugger open={debugOpen} onClose={() => setDebugOpen(false)} defaultMethod="GET" defaultUrl="/logs" />
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add admin-web/src/pages/Logs/
git commit -m "feat: implement Logs page with cycle filter"
```

---

### Task 18: 成本记账页面

**Files:**
- Modify: `admin-web/src/pages/Costs/index.tsx`

- [ ] **Step 1: 实现 Costs 页面（统计卡片 + 列表 + 新增）**

```tsx
import { useEffect, useState } from 'react';
import { Table, Button, Modal, Form, Input, InputNumber, DatePicker, Select, Space, Card, Row, Col, Statistic, message } from 'antd';
import { PlusOutlined, BugOutlined } from '@ant-design/icons';
import { listRecords, createRecord, getCycleProfit, getYearlySummary, type CostRecord, type CycleProfit, type YearlySummary } from '../../api/costs';
import { listCycles, type CropCycleListItem } from '../../api/cycles';
import ApiDebugger from '../../components/ApiDebugger';

export default function Costs() {
  const [data, setData] = useState<CostRecord[]>([]);
  const [cycles, setCycles] = useState<CropCycleListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [debugOpen, setDebugOpen] = useState(false);
  const [form] = Form.useForm();
  const [profit, setProfit] = useState<CycleProfit | null>(null);
  const [yearly, setYearly] = useState<YearlySummary | null>(null);
  const [selectedCycle, setSelectedCycle] = useState<number | undefined>();

  const fetchData = async () => {
    setLoading(true);
    try {
      const [recordsRes, cyclesRes] = await Promise.all([
        listRecords(selectedCycle ? { cycle_id: selectedCycle } : undefined),
        listCycles(),
      ]);
      setData(recordsRes.data);
      setCycles(cyclesRes.data);

      if (selectedCycle) {
        const profitRes = await getCycleProfit(selectedCycle);
        setProfit(profitRes.data);
      }
      const year = new Date().getFullYear();
      const yearlyRes = await getYearlySummary(year);
      setYearly(yearlyRes.data);
    } catch {
      message.error('加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, [selectedCycle]);

  const handleCreate = async () => {
    const values = await form.validateFields();
    try {
      await createRecord({ ...values, amount: String(values.amount), record_date: values.record_date.format('YYYY-MM-DD') });
      message.success('创建成功');
      setModalOpen(false);
      form.resetFields();
      fetchData();
    } catch {
      message.error('创建失败');
    }
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: '类型', dataIndex: 'record_type', render: (t: string) => t === 'cost' ? '支出' : '收入' },
    { title: '分类', dataIndex: 'category' },
    { title: '金额', dataIndex: 'amount' },
    { title: '日期', dataIndex: 'record_date' },
    { title: '备注', dataIndex: 'note', ellipsis: true },
  ];

  return (
    <div>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={8}>
          <Card><Statistic title="年度总支出" value={yearly?.total_cost ?? '--'} precision={2} /></Card>
        </Col>
        <Col span={8}>
          <Card><Statistic title="年度总收入" value={yearly?.total_income ?? '--'} precision={2} /></Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic title="年度净利润" value={yearly?.net_profit ?? '--'} precision={2} valueStyle={{ color: yearly && Number(yearly.net_profit) >= 0 ? '#3f8600' : '#cf1322' }} />
          </Card>
        </Col>
      </Row>

      <Space style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>新增记录</Button>
        <Select
          placeholder="按茬口筛选"
          allowClear
          style={{ width: 200 }}
          value={selectedCycle}
          onChange={(v) => setSelectedCycle(v)}
          options={cycles.map((c) => ({ value: c.id, label: c.name }))}
        />
        <Button icon={<BugOutlined />} onClick={() => setDebugOpen(true)}>调试</Button>
      </Space>

      {profit && (
        <Card size="small" style={{ marginBottom: 16 }}>
          <Space>
            <span>周期支出: {profit.total_cost}</span>
            <span>周期收入: {profit.total_income}</span>
            <span>净利润: <strong style={{ color: Number(profit.net_profit) >= 0 ? '#3f8600' : '#cf1322' }}>{profit.net_profit}</strong></span>
          </Space>
        </Card>
      )}

      <Table rowKey="id" dataSource={data} columns={columns} loading={loading} />

      <Modal title="新增记录" open={modalOpen} onOk={handleCreate} onCancel={() => setModalOpen(false)}>
        <Form form={form} layout="vertical">
          <Form.Item name="record_type" label="类型" rules={[{ required: true }]}>
            <Select options={[{ value: 'cost', label: '支出' }, { value: 'income', label: '收入' }]} />
          </Form.Item>
          <Form.Item name="category" label="分类" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="amount" label="金额" rules={[{ required: true }]}><InputNumber style={{ width: '100%' }} min={0} precision={2} /></Form.Item>
          <Form.Item name="record_date" label="日期" rules={[{ required: true }]}><DatePicker style={{ width: '100%' }} /></Form.Item>
          <Form.Item name="cycle_id" label="关联茬口">
            <Select allowClear options={cycles.map((c) => ({ value: c.id, label: c.name }))} />
          </Form.Item>
          <Form.Item name="note" label="备注"><Input /></Form.Item>
        </Form>
      </Modal>

      <ApiDebugger open={debugOpen} onClose={() => setDebugOpen(false)} defaultMethod="GET" defaultUrl="/costs" />
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add admin-web/src/pages/Costs/
git commit -m "feat: implement Costs page with stats cards and profit view"
```

---

### Task 19: AI 助手页面

**Files:**
- Modify: `admin-web/src/pages/Agent/index.tsx`

- [ ] **Step 1: 实现 Agent 页面（Tabs: 对话/建议/报告/历史）**

```tsx
import { useState } from 'react';
import { Tabs, Input, Button, Card, List, Select, Space, Spin, message } from 'antd';
import { SendOutlined } from '@ant-design/icons';
import { chat, getDailyAdvice, generateReport, getAdviceHistory, getReportHistory } from '../../api/agent';
import { listCycles, type CropCycleListItem } from '../../api/cycles';
import { useEffect } from 'react';

export default function Agent() {
  const [cycles, setCycles] = useState<CropCycleListItem[]>([]);
  const [selectedCycle, setSelectedCycle] = useState<number | undefined>();

  useEffect(() => {
    listCycles().then((res) => setCycles(res.data)).catch(() => {});
  }, []);

  return (
    <Tabs items={[
      { key: 'chat', label: '对话', children: <ChatTab cycles={cycles} selectedCycle={selectedCycle} setSelectedCycle={setSelectedCycle} /> },
      { key: 'advice', label: '每日建议', children: <AdviceTab cycleId={selectedCycle} /> },
      { key: 'report', label: '报告生成', children: <ReportTab cycles={cycles} selectedCycle={selectedCycle} setSelectedCycle={setSelectedCycle} /> },
      { key: 'history', label: '历史记录', children: <HistoryTab cycleId={selectedCycle} /> },
    ]} />
  );
}

function ChatTab({ cycles, selectedCycle, setSelectedCycle }: { cycles: CropCycleListItem[]; selectedCycle?: number; setSelectedCycle: (v?: number) => void }) {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<{ role: string; content: string }[]>([]);
  const [loading, setLoading] = useState(false);

  const handleSend = async () => {
    if (!input.trim()) return;
    setMessages((prev) => [...prev, { role: 'user', content: input }]);
    setLoading(true);
    try {
      const res = await chat(input, selectedCycle);
      setMessages((prev) => [...prev, { role: 'assistant', content: res.data.reply }]);
      setInput('');
    } catch {
      message.error('对话失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <Select placeholder="关联茬口" allowClear style={{ width: 200, marginBottom: 12 }} value={selectedCycle} onChange={setSelectedCycle}
        options={cycles.map((c) => ({ value: c.id, label: c.name }))} />
      <Card style={{ height: 400, overflow: 'auto', marginBottom: 12 }}>
        {messages.map((m, i) => (
          <div key={i} style={{ marginBottom: 8, textAlign: m.role === 'user' ? 'right' : 'left' }}>
            <span style={{ background: m.role === 'user' ? '#e6f7ff' : '#f0f0f0', padding: '4px 12px', borderRadius: 8, display: 'inline-block' }}>
              {m.content}
            </span>
          </div>
        ))}
        {loading && <Spin />}
      </Card>
      <Space.Compact style={{ width: '100%' }}>
        <Input value={input} onChange={(e) => setInput(e.target.value)} onPressEnter={handleSend} placeholder="输入消息..." />
        <Button type="primary" icon={<SendOutlined />} onClick={handleSend} loading={loading}>发送</Button>
      </Space.Compact>
    </div>
  );
}

function AdviceTab({ cycleId }: { cycleId?: number }) {
  const [advice, setAdvice] = useState('');
  const [loading, setLoading] = useState(false);

  const fetchAdvice = async () => {
    setLoading(true);
    try {
      const res = await getDailyAdvice(cycleId);
      setAdvice(res.data.advice);
    } catch {
      message.error('获取建议失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <Button onClick={fetchAdvice} loading={loading} style={{ marginBottom: 12 }}>获取今日建议</Button>
      <Card>{advice || '点击按钮获取建议'}</Card>
    </div>
  );
}

function ReportTab({ cycles, selectedCycle, setSelectedCycle }: { cycles: CropCycleListItem[]; selectedCycle?: number; setSelectedCycle: (v?: number) => void }) {
  const [report, setReport] = useState('');
  const [loading, setLoading] = useState(false);

  const handleGenerate = async () => {
    setLoading(true);
    try {
      const res = await generateReport('weekly', selectedCycle);
      setReport(res.data.content);
    } catch {
      message.error('生成报告失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <Space style={{ marginBottom: 12 }}>
        <Select placeholder="关联茬口" allowClear style={{ width: 200 }} value={selectedCycle} onChange={setSelectedCycle}
          options={cycles.map((c) => ({ value: c.id, label: c.name }))} />
        <Button type="primary" onClick={handleGenerate} loading={loading}>生成周报</Button>
      </Space>
      <Card><pre style={{ whiteSpace: 'pre-wrap' }}>{report || '点击按钮生成报告'}</pre></Card>
    </div>
  );
}

function HistoryTab({ cycleId }: { cycleId?: number }) {
  const [adviceHistory, setAdviceHistory] = useState<{ id: number; advice_type: string; content: string; created_at: string }[]>([]);
  const [reportHistory, setReportHistory] = useState<{ id: number; report_type: string; content: string; created_at: string }[]>([]);

  useEffect(() => {
    Promise.all([
      getAdviceHistory({ cycle_id: cycleId, limit: 10 }).catch(() => ({ data: [] })),
      getReportHistory({ cycle_id: cycleId, limit: 10 }).catch(() => ({ data: [] })),
    ]).then(([a, r]) => {
      setAdviceHistory(a.data);
      setReportHistory(r.data);
    });
  }, [cycleId]);

  return (
    <div>
      <h4>建议历史</h4>
      <List size="small" dataSource={adviceHistory} renderItem={(item) => (
        <List.Item><List.Item.Meta title={`${item.advice_type} - ${item.created_at}`} description={item.content.slice(0, 100)} /></List.Item>
      )} />
      <h4 style={{ marginTop: 16 }}>报告历史</h4>
      <List size="small" dataSource={reportHistory} renderItem={(item) => (
        <List.Item><List.Item.Meta title={`${item.report_type} - ${item.created_at}`} description={item.content.slice(0, 100)} /></List.Item>
      )} />
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add admin-web/src/pages/Agent/
git commit -m "feat: implement Agent page with chat, advice, report, history tabs"
```

---

### Task 20: 天气预报页面

**Files:**
- Modify: `admin-web/src/pages/Weather/index.tsx`

- [ ] **Step 1: 实现 Weather 页面**

```tsx
import { useEffect, useState } from 'react';
import { Card, Row, Col, InputNumber, Button, Spin } from 'antd';
import { getForecast } from '../../api/weather';

interface DayWeather {
  date: string;
  temp_max: number;
  temp_min: number;
  precipitation: number;
  wind_max: number;
}

export default function Weather() {
  const [days, setDays] = useState(7);
  const [weather, setWeather] = useState<DayWeather[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchWeather = async () => {
    setLoading(true);
    try {
      const res = await getForecast(days);
      const d = res.data.daily;
      const items: DayWeather[] = (d.time || []).map((date: string, i: number) => ({
        date,
        temp_max: d.temperature_2m_max?.[i] ?? 0,
        temp_min: d.temperature_2m_min?.[i] ?? 0,
        precipitation: d.precipitation_sum?.[i] ?? 0,
        wind_max: d.windspeed_10m_max?.[i] ?? 0,
      }));
      setWeather(items);
    } catch {
      setWeather([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchWeather(); }, []);

  return (
    <div>
      <Row gutter={8} style={{ marginBottom: 16 }}>
        <Col><InputNumber min={1} max={16} value={days} onChange={(v) => setDays(v ?? 7)} /></Col>
        <Col><Button type="primary" onClick={fetchWeather} loading={loading}>查询</Button></Col>
      </Row>
      {loading ? <Spin /> : (
        <Row gutter={[16, 16]}>
          {weather.map((d) => (
            <Col span={Math.max(4, 24 / Math.min(days, 6))} key={d.date}>
              <Card size="small" title={d.date}>
                <p>{d.temp_min}°C ~ {d.temp_max}°C</p>
                <p>降水: {d.precipitation}mm</p>
                <p>风速: {d.wind_max}m/s</p>
              </Card>
            </Col>
          ))}
        </Row>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add admin-web/src/pages/Weather/
git commit -m "feat: implement Weather forecast page"
```

---

## Phase 7: 独立 API Tester 页面

### Task 21: 实现 API Tester 页面

**Files:**
- Modify: `admin-web/src/pages/ApiTester/index.tsx`

- [ ] **Step 1: 定义端点元数据 + 实现页面**

```tsx
import { useState } from 'react';
import { Menu, Card, Row, Col } from 'antd';
import RequestEditor from '../../components/ApiDebugger/RequestEditor';
import ResponsePanel from '../../components/ApiDebugger/ResponsePanel';
import { Button, message, Space, Spin } from 'antd';
import { SendOutlined } from '@ant-design/icons';
import apiClient from '../../api/client';

interface Endpoint {
  method: string;
  path: string;
  description: string;
  body?: string;
}

const ENDPOINTS: Record<string, Endpoint[]> = {
  '作物管理': [
    { method: 'POST', path: '/crops/templates', description: '创建作物模板', body: '{"name":"西瓜","variety":"8424","stages":[{"name":"育苗期","duration_days":30,"order_index":1}]}' },
    { method: 'GET', path: '/crops/templates', description: '获取模板列表' },
    { method: 'GET', path: '/crops/templates/1', description: '获取模板详情' },
  ],
  '茬口管理': [
    { method: 'POST', path: '/cycles', description: '创建茬口', body: '{"name":"春季西瓜","crop_template_id":1,"start_date":"2026-04-01"}' },
    { method: 'GET', path: '/cycles', description: '获取茬口列表' },
    { method: 'GET', path: '/cycles/1', description: '获取茬口详情' },
  ],
  '农事日志': [
    { method: 'POST', path: '/logs', description: '创建日志', body: '{"cycle_id":1,"operation_type":"浇水","operation_date":"2026-05-20"}' },
    { method: 'GET', path: '/logs', description: '获取日志列表' },
    { method: 'GET', path: '/logs?cycle_id=1', description: '按茬口筛选日志' },
  ],
  '成本记账': [
    { method: 'POST', path: '/costs', description: '创建记录', body: '{"record_type":"cost","category":"肥料","amount":500,"record_date":"2026-05-20"}' },
    { method: 'GET', path: '/costs', description: '获取记录列表' },
    { method: 'GET', path: '/costs/cycles/1/profit', description: '周期利润' },
    { method: 'GET', path: '/costs/summary/2026', description: '年度汇总' },
  ],
  'AI 助手': [
    { method: 'POST', path: '/agent/chat', description: 'AI 对话', body: '{"message":"今天该做什么？"}' },
    { method: 'GET', path: '/agent/daily', description: '每日建议' },
    { method: 'POST', path: '/agent/report', description: '生成报告', body: '{"report_type":"weekly"}' },
    { method: 'GET', path: '/agent/advice-history', description: '建议历史' },
    { method: 'GET', path: '/agent/report-history', description: '报告历史' },
  ],
  '天气预报': [
    { method: 'GET', path: '/weather/forecast', description: '天气预报(7天)' },
    { method: 'GET', path: '/weather/forecast?days=3', description: '天气预报(3天)' },
  ],
  '系统': [
    { method: 'GET', path: '/health', description: '健康检查' },
  ],
};

const methodColor: Record<string, string> = {
  GET: '#52c41a', POST: '#1890ff', PUT: '#faad14', DELETE: '#ff4d4f',
};

export default function ApiTester() {
  const [selected, setSelected] = useState<Endpoint>(ENDPOINTS['系统'][0]);
  const [method, setMethod] = useState(selected.method);
  const [url, setUrl] = useState(selected.path);
  const [body, setBody] = useState(selected.body || '{}');
  const [status, setStatus] = useState<number | null>(null);
  const [duration, setDuration] = useState<number | null>(null);
  const [responseBody, setResponseBody] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSelect = (ep: Endpoint) => {
    setSelected(ep);
    setMethod(ep.method);
    setUrl(ep.path);
    setBody(ep.body || '{}');
    setStatus(null);
    setDuration(null);
    setResponseBody('');
  };

  const handleSend = async () => {
    setLoading(true);
    const start = Date.now();
    try {
      const config: Record<string, unknown> = { method: method.toLowerCase(), url };
      if (['POST', 'PUT', 'PATCH'].includes(method)) {
        try { config.data = JSON.parse(body); } catch { message.error('JSON 格式错误'); setLoading(false); return; }
      }
      const res = await apiClient.request(config);
      setStatus(res.status);
      setDuration(Date.now() - start);
      setResponseBody(JSON.stringify(res.data, null, 2));
    } catch (err: unknown) {
      const axiosErr = err as { response?: { status?: number; data?: unknown } };
      setStatus(axiosErr.response?.status ?? 0);
      setDuration(Date.now() - start);
      setResponseBody(JSON.stringify(axiosErr.response?.data ?? { error: String(err) }, null, 2));
    } finally {
      setLoading(false);
    }
  };

  const menuItems = Object.entries(ENDPOINTS).map(([group, eps]) => ({
    key: group,
    label: group,
    children: eps.map((ep, idx) => ({
      key: `${group}-${idx}`,
      label: (
        <span>
          <span style={{ color: methodColor[ep.method], fontWeight: 'bold', marginRight: 8 }}>{ep.method}</span>
          <span>{ep.description}</span>
        </span>
      ),
    })),
  }));

  return (
    <Row gutter={16}>
      <Col span={8}>
        <Card title="API 端点" style={{ maxHeight: 'calc(100vh - 200px)', overflow: 'auto' }}>
          <Menu
            mode="inline"
            items={menuItems}
            onClick={({ key }) => {
              const [group, idxStr] = key.split('-');
              handleSelect(ENDPOINTS[group][Number(idxStr)]);
            }}
          />
        </Card>
      </Col>
      <Col span={16}>
        <Card title={selected.description}>
          <Space direction="vertical" style={{ width: '100%' }} size="large">
            <RequestEditor method={method} url={url} body={body}
              onMethodChange={setMethod} onUrlChange={setUrl} onBodyChange={setBody} />
            <Button type="primary" icon={<SendOutlined />} loading={loading} onClick={handleSend} block>
              发送请求
            </Button>
            {loading && <Spin />}
            <ResponsePanel status={status} duration={duration} body={responseBody} />
          </Space>
        </Card>
      </Col>
    </Row>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add admin-web/src/pages/ApiTester/
git commit -m "feat: implement standalone API Tester page with all 20 endpoints"
```

---

## Phase 8: 最终验收

### Task 22: 全链路验证

- [ ] **Step 1: 删除旧数据库，启动后端**

```bash
rm -f backend/farm_manager.db
cd backend && python -m uvicorn app.main:app --reload &
```

- [ ] **Step 2: 验证后端 Swagger**

访问 http://localhost:8000/docs，确认全部端点显示，手动测试 `POST /crops/templates`。

- [ ] **Step 3: 启动前端**

```bash
cd admin-web && npm run dev
```

- [ ] **Step 4: 验证全部页面**

访问 http://localhost:5173，逐个验证：
- Dashboard 加载统计卡片
- Crops 创建/列表
- Cycles 创建/列表/详情
- Logs 创建/筛选
- Costs 创建/统计
- Agent 对话
- Weather 天气卡片
- API Tester 全部 20 端点可发送

- [ ] **Step 5: 运行后端全部测试**

```bash
cd backend && python -m pytest tests/ -v --timeout=30
```

Expected: ALL PASSED

- [ ] **Step 6: 最终 Commit**

```bash
git add .
git commit -m "feat: complete farm-manager-admin with PC dashboard, API tester, and multi-tenant foundation"
```

---

## 自检清单

**1. Spec 覆盖检查:**

| Spec 需求 | 对应 Task |
|-----------|-----------|
| admin-web: 项目初始化 | Task 10, 11 |
| admin-web: Dashboard | Task 14 |
| admin-web: 作物模板管理 | Task 15 |
| admin-web: 茬口管理 | Task 16 |
| admin-web: 农事日志 | Task 17 |
| admin-web: 成本记账 | Task 18 |
| admin-web: AI 助手 | Task 19 |
| admin-web: 天气预报 | Task 20 |
| admin-web: 独立 API Tester | Task 21 |
| admin-web: 内嵌 API 调试 | Task 15-18（各页面集成） |
| admin-web: 侧边栏导航 | Task 11 |
| multi-tenant: Farm 实体 | Task 4 |
| multi-tenant: farm_id 外键 | Task 5 |
| multi-tenant: get_current_farm | Task 6 |
| multi-tenant: API 路由注入 | Task 8 |
| multi-tenant: 种子数据 | Task 6 |
| yaml-config: config.yaml | Task 2, 3 |
| yaml-config: 模板文件 | Task 2 |
| yaml-config: pyyaml 依赖 | Task 1 |

**2. Placeholder 扫描:** 无 TBD/TODO/实现稍后等占位符。

**3. 类型一致性:** 所有 API 模块的 TypeScript 接口与后端 Pydantic Schema 字段名一致（snake_case）。
