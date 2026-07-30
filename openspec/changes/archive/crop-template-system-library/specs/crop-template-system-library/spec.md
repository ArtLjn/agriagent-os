## ADDED Requirements

### Requirement: 系统模版以 farm_id 为空标识

系统 SHALL 用 `CropTemplate.farm_id IS NULL` 标识系统模版，用户私有模版仍保持 `farm_id = 用户 farm`。系统 SHALL NOT 引入额外的 `is_system` 字段。

#### Scenario: 系统模版的存储表示

- **WHEN** 系统启动并加载 seed 数据
- **THEN** 系统模版的 `farm_id` 字段 SHALL 为 NULL，且仍保留外键约束到 `farms.id`

#### Scenario: 数据库 schema 支持系统模版

- **WHEN** Alembic 迁移执行完成
- **THEN** `crop_templates.farm_id` 列 SHALL 为 nullable，已有数据（`farm_id = 1`）SHALL 不受影响

### Requirement: 用户模版列表不包含系统模版

`get_crop_templates(db, farm_id)` SHALL 仅返回 `farm_id = 用户 farm` 的模版，SHALL NOT 返回 `farm_id IS NULL` 的系统模版。

#### Scenario: 查询用户模版库

- **WHEN** 用户查询自己的作物模版列表
- **THEN** 系统 SHALL 返回该用户 farm 下的所有模版，且不包含任何 `farm_id IS NULL` 的系统模版

### Requirement: 系统模版库 API

系统 SHALL 提供两个端点用于系统模版库的浏览与导入：

- `GET /crops/templates/system` —— 列出所有系统模版（含 stages），支持按 `category`（作物分类，如"粮食"、"蔬菜"、"水果"）筛选。
- `POST /crops/templates/system/{id}/import` —— 将指定系统模版深拷贝到当前用户 farm，返回新模版 ID。

#### Scenario: 列出系统模版库

- **WHEN** 用户调用 `GET /crops/templates/system`
- **THEN** 系统 SHALL 返回 `farm_id IS NULL` 的所有模版，每条含名称、品种、分类、阶段列表

#### Scenario: 按分类筛选系统模版

- **WHEN** 用户调用 `GET /crops/templates/system?category=蔬菜`
- **THEN** 系统 SHALL 仅返回分类为"蔬菜"的系统模版

#### Scenario: 系统模版不支持写入

- **WHEN** 任何请求尝试修改或删除 `farm_id IS NULL` 的模版（`PUT/DELETE /crops/templates/{id}`）
- **THEN** 系统 SHALL 返回 403 或 404，不允许修改

### Requirement: 导入系统模版采用副本模式

`POST /crops/templates/system/{id}/import` SHALL 将系统模版（含所有 stages）深拷贝到当前用户 farm，生成新的 `CropTemplate` 与 `GrowthStage` 记录。导入后的模版与原系统模版解耦，用户可自由编辑。

#### Scenario: 导入系统模版生成副本

- **WHEN** 用户调用 `POST /crops/templates/system/42/import`，系统模版 42 含 4 个阶段
- **THEN** 系统 SHALL 在用户 farm 下创建新模版（新 ID，`farm_id = 用户 farm`）及其 4 个 stages 副本，并返回新模版 ID

#### Scenario: 导入后用户可独立编辑

- **WHEN** 用户导入系统模版后修改其阶段天数
- **THEN** 系统 SHALL 仅修改用户副本，原系统模版（`farm_id IS NULL`）SHALL 不受影响

### Requirement: 导入复用精确查重避免重复

导入系统模版前 SHALL 调用 `crop_service.find_exact_duplicate`，若用户 farm 内已存在字面完全相同的模版，则不重复导入，返回已有模版 ID 与 `already_exists: true`。

#### Scenario: 重复导入同一系统模版

- **WHEN** 用户已导入过系统模版 42（未做任何修改），再次调用 `POST /crops/templates/system/42/import`
- **THEN** 系统 SHALL 不创建新记录，返回已有副本的 ID + `already_exists: true`

#### Scenario: 导入后修改过的模版不影响再次导入

- **WHEN** 用户导入系统模版 42 后修改了阶段天数，再次调用导入接口
- **THEN** 系统 SHALL 视为新模版（内容已不同），创建新副本并返回新 ID

### Requirement: Agent Skill 优先推荐系统模版

`create_crop_template` Skill 在精确查重未命中后、调 LLM 生成之前 SHALL 先调用 `crop_service.find_system_template_match(name, variety)`：

- 命中 → 返回 `NEED_CLARIFY`，告知用户系统库有匹配的成熟模版，并询问是否导入。
- 未命中 → 走原 LLM 生成路径。

Skill SHALL NOT 在未经用户确认的情况下直接导入系统模版（写操作需上层确认）。

#### Scenario: Skill 推荐系统模版

- **WHEN** 用户通过 Skill 创建"玉米"，精确查重未命中，但系统模版库存在"玉米"模版
- **THEN** Skill SHALL 返回 NEED_CLARIFY，提示用户系统库有成熟模版并询问是否导入，不直接调用 LLM

#### Scenario: Skill 在无系统模版时回退 LLM

- **WHEN** 用户通过 Skill 创建"罕见作物 X"，精确查重未命中且系统模版库无匹配
- **THEN** Skill SHALL 走原 LLM 生成路径

### Requirement: 系统模版内容由人工审核的 seed 数据提供

系统模版的初始数据 SHALL 由 seed 脚本（或 alembic data migration）一次性写入，内容 SHALL 经人工审核。系统模版 SHALL NOT 由 LLM 在运行时自动生成或修改。

#### Scenario: seed 数据加载

- **WHEN** 部署执行 seed 脚本
- **THEN** 系统 SHALL 在 `crop_templates` 表中创建 10-20 条 `farm_id IS NULL` 的系统模版，每条含经人工审核的生育阶段

#### Scenario: Skill 不写入系统模版库

- **WHEN** Agent Skill 执行任何创建逻辑
- **THEN** Skill SHALL NOT 写入 `farm_id IS NULL` 的记录，所有新建模版 SHALL 归属某个具体 farm
