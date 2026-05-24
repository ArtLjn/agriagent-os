## Why

当前 Farm Manager 只有移动端和后端 API，缺少 PC 端管理工具。开发者需要一个可视化界面来调试全部 API、管理业务数据。同时后端配置依赖 .env 文件（易丢失、无结构），且数据模型为单用户设计，无法扩展到多农户场景。

## What Changes

- 后端配置从 `.env` 迁移到 `config.yaml`，使用结构化的 YAML 配置文件替代扁平的环境变量
- **BREAKING**: 新增 Farm 实体，所有数据表（crops、cycles、logs、costs、agent_history）添加 `farm_id` 外键用于多租户隔离
- 新增认证中间件占位（当前默认返回首个农场，预留 JWT 鉴权扩展点）
- API 路由统一注入 farm 上下文，所有查询按 farm_id 隔离
- 新增 React + Vite + Ant Design + TypeScript 的 PC 管理端项目（admin-web/）
- 管理端覆盖全部 20 个 API 端点的 CRUD 操作
- 管理端包含独立的 API Tester 页面（轻量 Postman 体验）和每个 CRUD 页面内嵌的接口调试按钮

## Capabilities

### New Capabilities

- `admin-web`: PC 端管理后台，包含 Dashboard、作物管理、茬口管理、农事日志、成本记账、AI 助手、天气预报、API Tester 共 8 个页面，支持全 API 的 CRUD 和调试
- `multi-tenant-foundation`: Farm 实体 + farm_id 数据隔离 + 认证中间件占位，为多农户扩展预留架构基础
- `yaml-config`: 后端配置静态化，使用 config.yaml 替代 .env，支持分层结构化配置

### Modified Capabilities

（无现有需要修改的 capability）

## Impact

- **数据库**: 新增 farms 表，现有 5 张数据表均需添加 farm_id 列和外键约束
- **后端 API**: 所有路由函数签名变更，新增 farm 上下文依赖注入；现有 API 路径不变但行为按 farm 隔离
- **后端配置**: Pydantic Settings 的数据源从 `.env` 切换到 `config.yaml`
- **新增项目**: admin-web/ 目录，独立的前端项目（React + Vite + TypeScript + Ant Design）
- **依赖**: 后端新增 pyyaml；前端新增 React、Ant Design、Axios、React Router 等依赖
