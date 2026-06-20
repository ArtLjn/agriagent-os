## Why

[`crop-template-system-library`](../crop-template-system-library/proposal.md) 提案解决了"系统模板库 + 副本导入 + 精确查重"，但**没解决地域化**：当前 LLM 生成作物阶段不分地域（[create-crop-template/scripts/main.py:114](../../../backend/app/agent/skills/create-crop-template/scripts/main.py#L114)），导致徐州西瓜和海南西瓜拿到同一套阶段天数。

参考 [docs/superpowers/specs/2026-06-19-knowledge-and-memory-architecture-design.md § 3](../../../docs/superpowers/specs/2026-06-19-knowledge-and-memory-architecture-design.md)，地域化的最小落地是在系统模板上加 `region_tag` 字段 + 用户所在 region 优先匹配，**不另起提案，作为 crop-template-system-library 的 delta 升级**。

## What Changes

- **新增字段**：`crop_templates.region_tag` (VARCHAR(32), nullable, indexed)，取值约定 `default` / `xuzhou` / `hainan` / `guangdong` 等，NULL 视为 `default`
- **API 升级**：`GET /crops/templates/system` 支持 `?region=xuzhou` 查询参数，优先返回 region 命中，不足 fallback 到 `default`
- **导入行为**：`POST /crops/templates/system/{id}/import` 复制时把 `region_tag` 一并带到用户副本
- **Skill 升级**：`create_crop_template` 在精确查重未命中后，先按用户 region 查系统模板，命中则**推荐导入**，未命中才走 LLM 兜底
- **用户 region 来源**：复用 `UserSettings.default_city`，城市 → region_tag 映射表 hardcode
- **Seed 数据**：默认每种作物 1 套 `region_tag='default'`；当前业务聚焦"徐州 × 西瓜" → seed 1 套 `region_tag='xuzhou'`，由人工 WebSearch 调研后写入脚本

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `crop-template-system-library`: 在系统模板库与导入机制上增加地域维度，让徐州农户和海南农户能拿到不同的标准模板

## Impact

**数据库迁移**（新建 Alembic）：
- `crop_templates` 表新增 `region_tag` 列 + 索引
- 现有数据 `region_tag` 默认 NULL（视为 `default`）

**模型层**：
- [backend/app/models/crop.py](../../../backend/app/models/crop.py) `CropTemplate` 加 `region_tag` 字段

**Service 层**：
- `crop_service.list_system_templates(region)` 支持优先匹配 + fallback
- `crop_service.import_system_template` 复制时携带 `region_tag`

**API 层**：
- `GET /crops/templates/system?region=...` 查询参数
- `POST /crops/templates/system/{id}/import` 复制时一并写入

**Skill 层**：
- [create-crop-template/scripts/main.py](../../../backend/app/agent/skills/create-crop-template/scripts/main.py) 推荐系统模板时按用户 region 优先匹配

**配置/Seed**：
- `backend/app/seeds/region_mapping.py`（新）城市→region_tag 映射
- `backend/app/seeds/crop_templates_xuzhou.py`（新）徐州地域 seed

**文档同步**：
- [farm-manager-design-spec/04_相关规范/03_数据库与迁移规范.md](../../../farm-manager-design-spec/04_相关规范/03_数据库与迁移规范.md) 表清单补 `crop_templates.region_tag`
- [farm-manager-design-spec/01_正式设计/08_业务模块化.md](../../../farm-manager-design-spec/01_正式设计/08_业务模块化.md) `CropPort.list_templates` 签名加 region
- [farm-manager-design-spec/02_产品需求/01_核心能力清单.md](../../../farm-manager-design-spec/02_产品需求/01_核心能力清单.md) 作物管理能力补地域化描述
- [farm-manager-design-spec/03_接口协议/01_HTTP_API协议.md](../../../farm-manager-design-spec/03_接口协议/01_HTTP_API协议.md) 补 `GET /crops/templates/system?region=`

**前置依赖**：
- 必须先合并 [`crop-template-system-library`](../crop-template-system-library/proposal.md)（本提案基于其字段与 API 设计）

**关联**：
- [docs/superpowers/specs/2026-06-19-knowledge-and-memory-architecture-design.md](../../../docs/superpowers/specs/2026-06-19-knowledge-and-memory-architecture-design.md) § 3
- [farm-manager-design-spec/01_正式设计/04_Memory工程.md](../../../farm-manager-design-spec/01_正式设计/04_Memory工程.md) § 7（用户喜好与作物模板独立）
