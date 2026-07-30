## 1. 数据模型与迁移

- [x] 1.1 修改 [backend/app/models/crop.py:13](backend/app/models/crop.py#L13)：`CropTemplate.farm_id` 改为 `nullable=True`，保留 ForeignKey 与 default=1（default 仅对用户模版生效，系统模版由 seed 显式传 NULL）
- [x] 1.2 新增 Alembic 迁移：`alembic revision --autogenerate -m "allow null farm_id for system crop templates"`，手工 review 生成的 DDL，确认仅放宽 NOT NULL 约束
- [x] 1.3 验证迁移可逆：`alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` 全流程通过
- [x] 1.4 给 `crop_templates` 增加 `(farm_id, name, variety)` 联合索引（用于精确查重的短路过滤），生成对应迁移

## 2. Service 层精确查重

- [x] 2.1 在 [backend/app/services/crop_service.py](backend/app/services/crop_service.py) 新增 `find_exact_duplicate(db, farm_id, name, variety, stages)`：先按 `(farm_id, name, variety)` 精确过滤，候选集再做 stages 集合比对（顺序无关、`key_tasks` 规范化）
- [x] 2.2 实现 stages 规范化辅助函数 `_normalize_stages_for_compare(stages)`：返回 `frozenset[(name, duration_days, normalized_key_tasks)]`，`normalized_key_tasks` 做 trim + collapse whitespace
- [x] 2.3 单测 [backend/tests/services/test_crop_service_dedup.py](backend/tests/services/test_crop_service_dedup.py)：覆盖精确命中、name 相同 variety 不同、stages 内容不同、stages 顺序不同、`key_tasks` 空白差异等场景

## 3. Service 层系统模版库

- [x] 3.1 新增 `list_system_templates(db, category=None)`：查询 `farm_id IS NULL` 的模版，可选按 category 筛选
- [x] 3.2 新增 `get_system_template(db, template_id)`：仅返回 `farm_id IS NULL` 的模版，否则返回 None
- [x] 3.3 新增 `import_system_template(db, system_template_id, farm_id)`：深拷贝模版 + stages 到 `farm_id`，导入前调 `find_exact_duplicate` 检查重复；命中返回已有 ID + `already_exists=True`，否则创建并返回新 ID
- [x] 3.4 新增 `find_system_template_match(db, name, variety)`：在 `farm_id IS NULL` 范围内按 `(name, variety)` 精确匹配（不模糊），用于 Skill 推荐路径
- [x] 3.5 修改 `get_crop_templates(db, farm_id)` 确保仅返回 `farm_id = farm_id`，不返回 NULL（避免漏过滤）
- [x] 3.6 修改 `get_crop_template` / `update_crop_template` / `delete_crop_template`：拒绝操作 `farm_id IS NULL` 的系统模版（返回 None 或抛 ValueError）
- [x] 3.7 单测覆盖系统模版库的 list / import / 重复导入 / 系统模版写保护

## 4. API 层

- [x] 4.1 修改 [backend/app/api/crop.py:24](backend/app/api/crop.py#L24) `POST /crops/templates`：入库前调 `find_exact_duplicate`，命中返回 HTTP 200 + `{id, already_exists: true}`，未命中走原创建路径返回 HTTP 201
- [x] 4.2 新增 `GET /crops/templates/system?category=` 端点：返回系统模版列表（含 stages），支持按分类筛选
- [x] 4.3 新增 `POST /crops/templates/system/{id}/import` 端点：调 `import_system_template`，返回新 ID 或已有 ID
- [x] 4.4 在 `update_crop_template` / `delete_crop_template` 对应的 PUT/DELETE 端点加防护：目标为系统模版（`farm_id IS NULL`）时返回 403
- [x] 4.5 Pydantic schema 扩展：`CropTemplateResponse` 新增 `category` 字段（可空）；`CropTemplateCreate` 保持不变（系统模版由 seed 写入，不走 API）
- [x] 4.6 API 单测 [backend/tests/api/test_crop_templates_system.py](backend/tests/api/test_crop_templates_system.py)：覆盖 idempotent 创建、系统模版列表、导入、重复导入、系统模版写保护

## 5. Seed 数据（需人工审核）

- [x] 5.1 编写 `backend/app/seed/system_crop_templates.py`：以 Python 数据结构定义 10-20 个系统模版（水稻、小麦、玉米、大豆、番茄、辣椒、黄瓜、西瓜、草莓、生菜等），每个含分类、品种、生育阶段
- [ ] 5.2 生育阶段内容由产品/农业顾问审核签字，记录审核人在 `docs/design/crop-template-system-library.md` 中
- [x] 5.3 编写 alembic data migration 调用 seed 模块，写入 `farm_id IS NULL` 记录；要求 idempotent（已存在则跳过）
- [x] 5.4 seed 加载脚本单测：重复执行不产生重复；删除后重新加载行为正确

## 6. Skill 升级

- [x] 6.1 修改 [backend/app/agent/skills/create-crop-template/scripts/main.py:69-77](backend/app/agent/skills/create-crop-template/scripts/main.py#L69-L77)：移除 `find_template_by_name`（`ilike`），改用 `find_exact_duplicate`；命中返回 SUCCESS 含已有模版 ID 与阶段链
- [x] 6.2 精确查重未命中分支：增加 `find_system_template_match` 调用；命中则返回 `NEED_CLARIFY`，回复模板形如「系统库已有 {crop_name} 的成熟模版（阶段：{...}），要导入吗？」
- [x] 6.3 更新 [backend/app/agent/skills/create-crop-template/skill.md](backend/app/agent/skills/create-crop-template/skill.md) 契约：补充 Runtime 策略与失败处理（NEED_CLARIFY 分支）
- [x] 6.4 Skill 单测 [backend/tests/skills/test_create_crop_template.py](backend/tests/skills/test_create_crop_template.py)：覆盖精确命中、系统模版推荐、无匹配回退 LLM、context 缺失

## 7. Admin Web 前端

- [x] 7.1 在 [admin-web/src/api/crops.ts](admin-web/src/api/crops.ts) 新增 `listSystemCropTemplates(category?)`、`importSystemCropTemplate(id)`、`createCropTemplate` 返回类型补充 `already_exists` 字段
- [x] 7.2 新增页面 `admin-web/src/pages/CropTemplates/SystemLibrary.tsx`：按作物分类展示系统模版，支持多选 + 一键导入到当前 farm
- [x] 7.3 「我的模版库」列表（既有页面）补充提示：当用户尝试创建已存在模版时（API 返回 `already_exists: true`），用 toast 提示「已有相同模版，已为你定位」而非静默
- [x] 7.4 新建模版流程加引导：当用户点击「新建模版」时，先弹「是否从系统模版库选择？」二级入口，避免新用户从零手填
- [x] 7.5 前端单测 [admin-web/src/pages/CropTemplates/SystemLibrary.test.tsx](admin-web/src/pages/CropTemplates/SystemLibrary.test.tsx)：覆盖列表展示、分类筛选、多选导入、重复导入提示

## 8. 文档与配置同步

- [x] 8.1 新增 [docs/design/crop-template-system-library.md](docs/design/crop-template-system-library.md)（用 TEMPLATE.md）：记录决策、seed 清单、审核人
- [x] 8.2 更新 [docs/reference/api-spec.yaml](docs/reference/api-spec.yaml)：新增 `GET /crops/templates/system` 与 `POST /crops/templates/system/{id}/import`；标注 `POST /crops/templates` 的 idempotent 行为变更
- [x] 8.3 更新 [docs/architecture/overview.md](docs/architecture/overview.md)：作物模版部分补充"系统模版库"与"farm_id NULL 语义"
- [ ] 8.4 运行 `bash scripts/check-doc-freshness.sh` 与 `bash scripts/harness-check.sh` 全部通过

## 9. 上线前验证

- [ ] 9.1 端到端验证：新用户注册 → 进入系统模版库 → 勾选 3 个 → 一键导入 → 「我的模版库」可见可编辑
- [ ] 9.2 回归验证：已有用户创建字面重复模版被拦截、不同方案可创建、Skill 创建路径行为符合新规约
- [ ] 9.3 数据库迁移在 staging 环境跑通，确认 NULL 约束放宽不影响现有查询
