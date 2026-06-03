---
last_updated: 2026-05-24
status: active
---

# 系统架构

## 后端分层

```
backend/app/
├── schemas/          # 依赖: 不依赖任何层
├── agents/          # 依赖: core, models, services
├── api/          # 依赖: core, models, schemas, services
├── core/          # 依赖: models
├── models/          # 依赖: core
├── services/          # 依赖: agents, models, schemas
└── main.py          # 入口
```

## 后端依赖方向

```
schemas/ → 不依赖任何层
  ↓
agents/ → core, models, services
  ↓
api/ → core, models, schemas, services
  ↓
core/ → models
  ↓
models/ → core
  ↓
services/ → agents, models, schemas
```


## 前端分层

```
admin-web/src/
├── api/          # 依赖: 不依赖任何层
├── components/          # 依赖: api
├── layouts/          # 依赖: 不依赖任何层
├── pages/          # 依赖: api, components
└── main.ts          # 入口
```

## 核心约定

- 横切关注点（auth/log/telemetry）通过依赖注入，不被业务层直接 import
- API 版本统一 v1，路径前缀 `/api/v1/`
- 数据库迁移只用 alembic，禁止手动改表
- 数据库统一使用 MySQL 8.x，连接串需包含 `charset=utf8mb4`
