## Context

当前作物模版（`CropTemplate` + `GrowthStage`）管理存在三个事实：

1. **数据模型**：[models/crop.py:13](backend/app/models/crop.py#L13) `farm_id` 为 `NOT NULL` 且默认 `1`，模型层无唯一约束，技术允许任意重复。
2. **API 层**：[api/crop.py:24](backend/app/api/crop.py#L24) `POST /crops/templates` 直接调 `create_crop_template` 入库，无任何查重；前端 `admin-web` 直连此接口。
3. **Skill 层**：[create-crop-template/scripts/main.py:69-77](backend/app/agent/skills/create-crop-template/scripts/main.py#L69-L77) 通过 `crop_service.find_template_by_name` 做软查重，而该方法 [crop_service.py:11-22](backend/app/services/crop_service.py#L11-L22) 使用 `name.ilike(f"%{crop_name}%")`，存在子串误匹配（"瓜"命中"西瓜"）和不区分 `variety`（春季版挡住秋季版）两个缺陷。

新用户冷启动路径只有一条：调用 Skill → LLM 凭空生成 4 阶段 → 入库。没有"先用成熟方案"的路径，质量取决于 LLM 单次输出。

Admin Web 中管理员账号同时具备 admin 权限和 app 业务账号数据。作物模板、种植周期、农事日志、成本记账和天气预报属于管理员个人 app 账号的数据视图，应归入"业务调试"；系统模板属于平台预置资产，应归入"业务运营"。

## Goals / Non-Goals

**Goals:**

- 在 service 层统一作物模版精确查重逻辑，让 API 和 Skill 两个入口行为一致。
- 引入系统模版库，让新用户可以"勾选导入"而非"从零生成"。
- 让 Agent Skill 在系统模版库有匹配项时优先推荐导入，节省 LLM 调用并保证质量。

**Non-Goals:**

- 不在数据模型层加唯一约束（同品种不同方案仍允许重复，只拦截字面完全相同）。
- 不做"共享只读 + fork"模式（用户改 stages 时再 fork 的复杂度爆炸）。
- 不在本期做系统模版的后台运营管理界面（P2 延后）。
- 不在本期做系统模版版本升级 / 推送机制。
- 不引入新的依赖。

## Decisions

### Decision 1: 系统模版用 `farm_id IS NULL` 标识，不引入 `is_system` 字段

**选择**：扩展 `CropTemplate.farm_id` 为 nullable，系统模版以 `farm_id IS NULL` 标识。

**备选**：新增 `is_system: bool` + `farm_id` 允许 NULL。

**理由**：
- 查询语义自然：`WHERE farm_id = :uid` 就是用户的，`WHERE farm_id IS NULL` 就是系统的，无需 `is_system` 过滤。
- 复用现有索引（如未来加 `(farm_id, name)` 索引，NULL 也能命中）。
- 减少 schema 字段冗余。

**Trade-off**：如果未来需要"系统模版也按地区/语种分桶"，`farm_id IS NULL` 不够表达。但当前无此需求，按 YAGNI 处理。

### Decision 2: 精确查重的 stages 比对做"顺序无关 + 字段规范化"

**选择**：在 `find_exact_duplicate` 中将 stages 转为 `frozenset((name, duration_days, normalized_key_tasks))` 后比较，不依赖 `order_index`。

**备选**：① 用 stages 序列化后的 hash；② 严格按 `order_index` 比对。

**理由**：
- 用户重排阶段顺序不应被视为不同方案（这是同方案的展示偏好）。
- `key_tasks` 文本需 trim + 统一空白字符，避免"催芽 播种" vs "催芽  播种" 误判为不同。
- hash 方案可读性差，调试困难。

**短路优化**：先按 `(farm_id, name, variety)` 精确过滤，命中候选后再做 stages 深度比对。作物模版量小（一农场几十条），深度比对成本可忽略。

### Decision 3: 导入系统模版采用"副本模式"，不做共享只读

**选择**：`POST /crops/templates/system/{id}/import` 把系统模版（含 stages）深拷贝到当前 `farm_id`，返回新模版 ID。导入后用户可自由编辑。

**备选**：共享只读 + 按需 fork。

**理由**：
- 作物模版本质是个性化的（不同地区/季节天数不同），强制共享反而限制。
- 副本模式与现有 `CropTemplate` 模型零冲突，无需引入"模板引用"概念。
- 数据冗余可忽略：单条作物模版 + 几条 stage，KB 级。

### Decision 4: 精确查重统一在 service 层，API 和 Skill 共用

**选择**：`crop_service.find_exact_duplicate(db, farm_id, name, variety, stages)` 为唯一查重入口。`POST /crops/templates` 改为：查重命中 → 返回已有模版（HTTP 200 + idempotent 标识）；未命中 → 正常创建。Skill 同样调用此方法，移除原 `ilike` 调用。

**理由**：消除"API 不管、Skill 模糊管"的双标问题；后续若调整查重策略只改一处。

### Decision 5: 系统模版内容由人工审核的 seed 数据提供，禁止 LLM 写入

**选择**：初始系统模版由 alembic data migration 或独立 seed 脚本一次性写入；内容须经懂农事的同事审核签字。Skill 与 API 在 `farm_id IS NULL` 范围内为只读。

**备选**：让运营通过后台界面增删（P2）；让 LLM 批量生成初稿。

**理由**：系统模版是"权威方案"，质量直接影响所有新用户首单体验。LLM 单次生成的生育阶段存在天数错误（如把 30 天作物生成 90 天），不能未经审核就广播。

### Decision 6: Skill 调用顺序：精确查重 → 系统模版库匹配 → LLM 生成

**选择**：Skill `create_crop_template` 改造为：
1. 调 `find_exact_duplicate` —— 命中则告知用户已有完全相同的模版（含 ID），不创建。
2. 调 `find_system_template_match` —— 命中则返回 `NEED_CLARIFY`："系统库有 X 的成熟模版，要导入吗？" 由上层确认后调 `import_system_template`。
3. 未命中 → 走原 LLM 生成路径。

**理由**：把"系统模版库"作为 Skill 的优先推荐源，既节省 LLM 调用，又把"质量参差的 LLM 默认阶段"降级为最后兜底。

## Risks / Trade-offs

- **[Risk] `farm_id` 现有外键约束阻止 NULL** → Migration：先 alembic 放宽 `NOT NULL` → `NULL`，保留外键；现有数据 `farm_id = 1` 不受影响；上线前验证 `SELECT 1 FROM crop_templates WHERE farm_id IS NULL` 在 schema 层被允许。
- **[Risk] 精确查重的 stages 比对在大数据集下性能差** → 已有短路优化（先 name+variety 过滤）；当前作物模版量小（单农场 < 100 条），不会成为瓶颈；如果未来出现性能问题，再加 `(farm_id, name, variety)` 联合索引。
- **[Risk] 系统模版内容质量风险** → seed 数据必须人工审核；写一份 `docs/design/crop-template-system-library.md` 列出初始清单和审核人；本期禁止任何 LLM 自动写入系统库。
- **[Risk] 用户多次导入同一系统模版产生重复** → 导入路径复用 `find_exact_duplicate`，命中则提示"已导入过，是否查看现有"。
- **[Risk] Skill 模糊匹配移除后，部分老用户对话体验变化** → 旧行为是"已存在则直接 SUCCESS 不创建"；新行为是"完全相同则不创建、相似则推荐选择"，对用户更友好，不构成回归。

## Migration Plan

1. **Phase 1（后端 + 数据）**：
   - Alembic 迁移：`crop_templates.farm_id` 改为 nullable。
   - `crop_service` 新增 `find_exact_duplicate` / `list_system_templates` / `import_system_template` / `find_system_template_match`。
   - `POST /crops/templates` 接入精确查重（idempotent）。
   - 新增 `GET /crops/templates/system`、`POST /crops/templates/system/{id}/import`。
   - seed 脚本：预置 10-20 个系统模版（人工审核）。

2. **Phase 2（Skill 升级）**：
   - `create_crop_template` 移除 `ilike`，改用精确查重 + 系统库推荐。

3. **Phase 3（前端）**：
   - `admin-web` 在"业务运营"下新增"系统模板"页面（分类 + 多选 + 一键导入）。
   - 管理员个人 app 账号下的作物模板、种植周期、农事日志、成本记账、天气预报和 AI 助手归入"业务调试"。
   - "作物模板"列表处理用户副本与重复创建提示；"系统模板"作为平台预置资产入口。

4. **回滚策略**：迁移可 `alembic downgrade -1`；service 新方法为纯新增，不影响现有调用；API 行为变更（idempotent）需协调前端处理"返回已有 ID"的响应分支。

## Open Questions

- 系统模版的初始作物清单具体包含哪些？（建议由产品 + 农业顾问确认；初稿：水稻、小麦、玉米、大豆、番茄、辣椒、黄瓜、西瓜、草莓、生菜）
- 系统模版是否需要按地区/气候分版本（如"北方春玉米" vs "南方夏玉米"）？本期建议不分，先上通用版本。
- Admin Web 信息架构已收敛：系统模板放在"业务运营"；管理员个人 app 账号业务数据视图放在"业务调试"。
- 后续是否需要在 FarmManager Mobile App 也提供系统模版库入口？本期范围只覆盖 admin-web，App 端延后。
