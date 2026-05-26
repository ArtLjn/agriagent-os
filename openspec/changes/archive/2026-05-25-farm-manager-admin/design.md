## Context

Farm Manager 是一个种植管理工具，当前包含 FastAPI 后端（20 个 API 端点、SQLite 数据库、6 个路由模块）和 React Native 移动端。后端使用 Pydantic BaseSettings + `.env` 管理配置，数据模型为单用户设计（无租户隔离）。没有 PC 端管理工具，开发者只能通过 curl 或 Swagger 调试 API。

当前数据模型共 7 张表：`crop_templates`、`growth_stages`、`crop_cycles`、`cycle_stages`、`farm_logs`、`cost_records`、`advice_records` + `report_records`。所有数据无归属标识，无法支持多农户场景。

## Goals / Non-Goals

**Goals:**

- 后端配置迁移到 `config.yaml`，结构化、可读、可版本控制
- 数据层预留多租户扩展能力（farm_id 隔离），但当前阶段不做完整鉴权
- 搭建 PC 管理端，覆盖全部 API 的 CRUD 和调试能力
- 管理端同时提供嵌入式调试（页面内）和集中式调试（独立 API Tester 页）

**Non-Goals:**

- 不实现完整的用户注册/登录/JWT 签发
- 不实现角色权限体系（admin/viewer 等）
- 不做移动端到 PC 端的功能镜像（PC 端定位为开发者工具）
- 不做数据迁移工具（当前数据量小，可手动处理）

## Decisions

### 1. 配置方案：config.yaml + Pydantic Settings custom_settings_source

**选择**: 使用 Pydantic Settings 的 `@SettingsConfigParm` 自定义 source，从 YAML 文件读取配置，环境变量作为覆盖。

**替代方案**:
- 纯环境变量（现状）：扁平、无结构、易丢失
- TOML：Python 生态主流，但项目已有 YAML 惯例（OpenSpec config.yaml）
- JSON：无注释能力

**理由**: YAML 可读性最好，支持注释，与项目已有惯例一致。Pydantic Settings 原生支持自定义 source，迁移成本极低。

**config.yaml 结构**:
```yaml
server:
  host: "0.0.0.0"
  port: 8000

database:
  url: "sqlite:///./farm_manager.db"

ai:
  model: "qwen3.5-plus-2026-04-20"
  api_key: ""
  base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"

weather:
  latitude: 34.26
  longitude: 117.18
```

### 2. 多租户方案：Farm 实体 + farm_id 外键

**选择**: 新增 `farms` 表作为顶级实体，所有业务表添加 `farm_id` 外键指向 `farms.id`。

**替代方案**:
- 仅加 `user_id`（无 Farm 概念）：无法支持一个农户多个地块的场景
- schema-level 隔离（每个租户独立 SQLite 文件）：过度设计，运维复杂

**理由**: `farm_id` 是最自然的隔离粒度——一个农户对应一个农场，农场下有所有种植数据。未来支持多农户时只需加认证层分配 farm_id 即可。

**farms 表结构**:
```python
class Farm(Base):
    __tablename__ = "farms"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)       # 农场名称，如"李家地"
    owner_name = Column(String, nullable=True)   # 户主姓名
    location = Column(String, nullable=True)     # 地址
    created_at = Column(DateTime, server_default=func.now())
```

**需要加 farm_id 的表**（6 张）:
- `crop_templates` → farm_id（每个农场有自己的作物模板）
- `crop_cycles` → farm_id
- `cycle_stages` → 不加（跟随 cycle 的 farm_id）
- `growth_stages` → 不加（跟随 template 的 farm_id）
- `farm_logs` → farm_id
- `cost_records` → farm_id
- `advice_records` → farm_id
- `report_records` → farm_id

### 3. 认证中间件占位

**选择**: 新增 `get_current_farm` 依赖注入函数，当前硬编码返回 `farm_id=1`（种子数据），预留 JWT 解析位置。

```python
async def get_current_farm(db: Session = Depends(get_db)) -> Farm:
    """当前阶段返回默认农场，未来替换为 JWT 解析。"""
    farm = db.query(Farm).filter(Farm.id == 1).first()
    if not farm:
        raise HTTPException(status_code=404, detail="No farm found")
    return farm
```

所有路由函数签名从 `db: Session = Depends(get_db)` 变为 `db: Session = Depends(get_db), farm: Farm = Depends(get_current_farm)`，service 层查询自动追加 `farm_id` 过滤。

### 4. admin-web 技术架构

**选择**: React 18 + Vite 5 + TypeScript + Ant Design 5 + React Router 6 + Axios

**替代方案**:
- Vue + Element Plus：团队不熟 Vue
- Streamlit：Python 原型快，但定制性差，API 调试面板不好做
- Next.js：SSR 不需要，增加复杂度

**理由**: 用户已有 React（RN）经验，Ant Design 的 Table/Form/Modal 组件完美匹配 CRUD 场景。Vite 开发体验好，HMR 快。

**项目结构**:
```
admin-web/
├── src/
│   ├── api/              # Axios 实例 + 各模块 API 调用函数
│   │   ├── client.ts     # Axios 实例（baseURL 指向后端）
│   │   ├── crops.ts
│   │   ├── cycles.ts
│   │   ├── logs.ts
│   │   ├── costs.ts
│   │   ├── agent.ts
│   │   └── weather.ts
│   ├── components/       # 公共组件
│   │   └── ApiDebugger/  # 内嵌 API 调试组件
│   ├── pages/            # 8 个页面
│   ├── layouts/          # 布局（侧边栏 + 内容区）
│   ├── App.tsx
│   └── main.tsx
├── package.json
├── tsconfig.json
└── vite.config.ts
```

### 5. API Tester 设计

**双模式方案**:

**模式 A — 页面内嵌**: 每个 CRUD 页面顶部有"调试"按钮，点击展开一个 Drawer/Modal，预填当前页面对应的 API 端点、方法、参数模板。用户直接发送请求看响应。

**模式 B — 独立页面**: 左侧按模块分组列出全部 20 个端点（方法 + 路径），点击后右侧显示请求构建器（URL、Headers、Body 编辑器）和响应面板（状态码、耗时、格式化 JSON）。

两个模式共用底层 `ApiDebugger` 组件，区别仅在触发方式（按钮 vs 导航）。

## Risks / Trade-offs

- **[破坏性变更] 数据库 schema 变更** → 现有 SQLite 数据需迁移。由于当前数据量极小（开发阶段），直接新建数据库 + 种子数据脚本即可，无需编写 migration 工具。
- **[范围蔓延] API 调试面板复杂度** → 先实现基础功能（发送请求、看响应），不追求 Postman 级别的完整体验（不做到环境变量、集合管理、断言等）。
- **[过度设计风险] farm_id 隔离增加了当前开发复杂度** → 接受这个代价。隔离逻辑集中在 service 层，API 层通过依赖注入传递 farm，侵入性可控。
- **[依赖膨胀] admin-web 前端依赖** → Ant Design 是唯一重型依赖，其余都是轻量库（axios、react-router），可接受。

## Open Questions

- admin-web 是否需要暗色主题？（Ant Design 5 支持，实现成本低）
- 天气 API 当前返回原始数据无 schema，管理端展示时是否需要后端先做一层格式化？
