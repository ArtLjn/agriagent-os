## ADDED Requirements

### Requirement: 作物模版精确查重统一在 service 层提供

系统 SHALL 在 `crop_service` 提供 `find_exact_duplicate(db, farm_id, name, variety, stages)` 方法，用于判定某个待创建的作物模版在指定农场内是否已存在字面完全相同的副本。判定规则：

- `name` 精确相等（区分大小写、不做子串匹配）。
- `variety` 精确相等（双方均为空视为相等）。
- `stages` 内容比对采用"顺序无关 + 字段规范化"：将每个 stage 转为 `(name, duration_days, normalized_key_tasks)` 元组组成集合后比较，`normalized_key_tasks` 为 trim 后统一空白字符的字符串。

#### Scenario: name 与 variety 精确相同且 stages 内容完全一致

- **WHEN** 已存在模版 `name="西瓜", variety="8424"`，含 4 个阶段；新请求 `name="西瓜", variety="8424"`，含相同 4 个阶段（顺序不同）
- **THEN** 系统 SHALL 命中已有模版并返回其 ID，不视为新模版

#### Scenario: name 相同但 variety 不同

- **WHEN** 已存在模版 `name="西瓜", variety="8424春季版"`；新请求 `name="西瓜", variety="8424秋季版"`
- **THEN** 系统 SHALL 不命中，允许创建新模版

#### Scenario: name 与 variety 相同但 stages 内容不同

- **WHEN** 已存在模版 `name="西瓜", variety="8424"` 含 4 个阶段共 90 天；新请求相同 name+variety 但含 5 个阶段共 120 天
- **THEN** 系统 SHALL 不命中，允许创建新模版（视为不同方案）

#### Scenario: 子串匹配不再使用

- **WHEN** 已存在模版 `name="西瓜"`；新请求 `crop_name="瓜"`
- **THEN** 系统 SHALL 不命中（精确相等比对），不会因旧 `ilike '%瓜%'` 逻辑误判为重复

### Requirement: 后端 API 创建模版必须先做精确查重

`POST /crops/templates` SHALL 在入库前调用 `find_exact_duplicate`：

- 命中 → 返回 HTTP 200，响应体包含已有模版 ID 与 `already_exists: true` 标识，不新建。
- 未命中 → 正常创建并返回 HTTP 201。

API SHALL NOT 使用 `ilike` 或任何模糊匹配进行查重。

#### Scenario: 创建字面完全相同的模版

- **WHEN** 用户提交 `POST /crops/templates`，请求体与已存在模版（含 stages 内容）完全一致
- **THEN** 系统 SHALL 返回 HTTP 200 + 已有模版 ID + `already_exists: true`，不写入新记录

#### Scenario: 创建不同方案的模版

- **WHEN** 用户提交与已存在模版 name 相同但 stages 内容不同的请求
- **THEN** 系统 SHALL 创建新模版并返回 HTTP 201

### Requirement: Agent Skill 创建模版使用 service 层精确查重

`create_crop_template` Skill SHALL 调用 `crop_service.find_exact_duplicate` 而非 `find_template_by_name`，移除所有 `ilike` 模糊匹配逻辑。

- 精确查重命中 → 返回 `SUCCESS` 并告知用户已有完全相同的模版（含 ID 与阶段名），不创建。
- 未命中 → 继续后续流程（系统模版推荐或 LLM 生成）。

#### Scenario: Skill 命中完全相同的已有模版

- **WHEN** 用户通过 Skill 创建"西瓜 8424"，且农场内已存在完全相同的模版
- **THEN** Skill SHALL 返回 SUCCESS，回复包含已有模版的阶段链路，不调用 LLM、不新建记录

#### Scenario: Skill 在 variety 不同时不误拒

- **WHEN** 用户通过 Skill 创建"西瓜 8424 秋季版"，农场内仅存在"西瓜 8424 春季版"
- **THEN** Skill SHALL 不命中精确查重，继续后续流程
