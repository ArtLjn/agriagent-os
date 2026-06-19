## Why

当前作物模版管理存在两个相互关联的问题：

1. **去重逻辑分散且错误**：API 层（[api/crop.py:24](backend/app/api/crop.py#L24)）完全不查重，用户可以建出字面完全相同的模版（垃圾数据）；Skill 层（[create-crop-template/scripts/main.py:69-77](backend/app/agent/skills/create-crop-template/scripts/main.py#L69-L77)）虽然查重，但用 `ilike '%name%'` 模糊匹配且不区分 variety，存在子串误匹配（"瓜"命中"西瓜"）和误拒不同方案（"春季版"挡住"秋季版"）的问题。两个入口标准不一致。

2. **新用户冷启动困难**：新用户没有"参考模版"的概念，每次新建作物都靠 LLM 凭空生成生育阶段，质量参差、费 token，且没有"先用成熟方案再个性化"的标准路径。

## What Changes

### 修复：模版精确查重统一在 service 层

- 在 `crop_service` 新增 `find_exact_duplicate(db, farm_id, name, variety, stages)`：`name + variety` 精确相等、`stages` 内容规范化（顺序无关）比对；命中返回已有模版 ID。
- 后端 API `POST /crops/templates` 改为：先查精确重复，命中则返回已有模版（idempotent），不新建。
- Skill `create_crop_template` 移除 `ilike` 模糊匹配；改为调用同一 service 查重，命中则告知用户"已有完全相同的模版"并列出；未命中时正常生成。
- 不在数据模型层加唯一约束（同品种不同方案仍允许，只拦截字面完全相同）。

### 新增：系统模版库

- 用 `CropTemplate.farm_id IS NULL` 标识系统模版（不加 `is_system` 字段），用户模版仍为 `farm_id = 用户 farm`。
- 新增 seed 脚本，预置 10-20 个常见作物（水稻、小麦、玉米、西瓜、番茄、辣椒等），生育阶段需人工审核，**禁止 LLM 自动生成塞入系统库**。
- 导入采用**副本模式**：从 `farm_id IS NULL` 复制一条到 `farm_id = 用户`，用户可自由编辑；导入时复用上面的精确查重，避免用户多次导入产生重复。
- 新增后端 API `GET /crops/templates/system`（按作物分类列出系统模版）、`POST /crops/templates/system/{id}/import`（导入到当前 farm）。
- 新增 admin-web 页面"系统模版库"：按作物分类展示 + 多选 + 一键导入到当前用户的模版库。

### Skill 行为升级（P1，非阻塞）

- Skill `create_crop_template` 在精确查重未命中时，先查系统模版库是否有匹配项，命中则**推荐用户导入系统模版**（节省 LLM 调用 + 保证质量），未命中才走 LLM 生成。

## Capabilities

### New Capabilities

- `crop-template-dedup`: 在 service 层提供作物模版精确查重，覆盖后端 API 与 Agent Skill 两个创建入口，消除字面完全相同的重复模版。
- `crop-template-system-library`: 提供系统预置模版库与"导入即副本"机制，解决新用户冷启动问题，并为 Agent Skill 提供推荐来源。

### Modified Capabilities

（无：现有 `planting-batch-management` 等能力的需求行为不变，本次只动模版创建路径。）

## Impact

- **后端模型**：[CropTemplate](backend/app/models/crop.py) 沿用现有字段，`farm_id` 改为可空（数据库需 migration 把 `NOT NULL` 放宽为 NULL；现有数据 `farm_id` 默认 1 不受影响）。
- **后端 service**：`crop_service.py` 新增 `find_exact_duplicate` 和 `list_system_templates` / `import_system_template`。
- **后端 API**：[api/crop.py](backend/app/api/crop.py) 新增 `GET /crops/templates/system` 与 `POST /crops/templates/system/{id}/import`；调整 `POST /crops/templates` 接入精确查重。
- **Agent Skill**：[create-crop-template](backend/app/agent/skills/create-crop-template/scripts/main.py) 移除 `ilike` 匹配，改为调用 service 精确查重 + 推荐系统模版。
- **Admin Web**：新增"系统模版库"页面与"我的模版库"区分展示。
- **数据库迁移**：alembic 新增一个迁移放宽 `crop_templates.farm_id` 约束；新增 seed 数据加载脚本。
- **文档**：`docs/design/` 新增设计文档；`docs/reference/api-spec.yaml` 同步新增端点。
