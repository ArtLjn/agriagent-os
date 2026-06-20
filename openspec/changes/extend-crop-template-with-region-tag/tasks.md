## 1. 数据模型与迁移

- [ ] 1.1 在 [backend/app/models/crop.py](../../../backend/app/models/crop.py) `CropTemplate` 加 `region_tag = Column(String(32), nullable=True, index=True)`
- [ ] 1.2 Alembic 生成迁移：`alembic revision --autogenerate -m "add region_tag to crop_templates"`
- [ ] 1.3 检查迁移脚本，加注释说明"NULL 视为 default"，不回填
- [ ] 1.4 应用到开发库，验证字段存在 + 索引创建成功

## 2. Region 映射

- [ ] 2.1 新建 `backend/app/seeds/region_mapping.py`，导出 `CITY_TO_REGION: dict[str, str]` 与 `resolve_region(city) -> str`
- [ ] 2.2 初始映射覆盖徐州及下辖县市（铜山 / 睢宁 / 邳州 / 新沂 / 丰县 / 沛县），其他城市 fallback 到 `default`
- [ ] 2.3 单测 `tests/seeds/test_region_mapping.py` 覆盖：已映射 / 未映射 fallback / None / 空字符串

## 3. Service 层升级

- [ ] 3.1 在 `crop_service.list_system_templates(db, crop_name=None, region='default')` 实现 region 优先匹配 SQL（单次查询 + CASE 排序）
- [ ] 3.2 `crop_service.import_system_template(db, system_template_id, farm_id)` 复制时把 `region_tag` 一并带到副本
- [ ] 3.3 单测覆盖：region 命中 / fallback / 副本保留 region_tag / 跨 region 重复导入

## 4. API 升级

- [ ] 4.1 [backend/app/api/crop.py](../../../backend/app/api/crop.py) `GET /crops/templates/system` 加 `?region=` 与 `?crop_name=` 查询参数
- [ ] 4.2 验证未传 region 时默认 `default`，不抛错
- [ ] 4.3 `POST /crops/templates/system/{id}/import` 复制时携带 region_tag
- [ ] 4.4 集成测试：3 个场景（region 命中 / fallback / 副本保留 region）

## 5. Skill 升级

- [ ] 5.1 [create-crop-template/scripts/main.py](../../../backend/app/agent/skills/create-crop-template/scripts/main.py) `_generate_stages` 前增加 `_recommend_system_template(context, crop_name, region)`
- [ ] 5.2 推荐文案："我们有现成的徐州西瓜模板，要不要直接用？" + 用户拒绝时走 LLM 兜底
- [ ] 5.3 Skill 单测：region 匹配 → 推荐 / 用户拒绝 → LLM / 无匹配 → LLM

## 6. Seed 数据

- [ ] 6.1 用 WebSearch 调研"徐州 西瓜 生育阶段 阶段天数"，记录至少 2 个来源链接
- [ ] 6.2 新建 `backend/app/seeds/crop_templates_xuzhou.py`，写入"徐州 × 西瓜"模板（含 stages），metadata 记录来源
- [ ] 6.3 跑 seed 验证：徐州用户查询能优先匹配，非徐州用户 fallback 到 default

## 7. CI Lint

- [ ] 7.1 新建 `scripts/check-region-tag-naming.sh`，扫描 seed 与 system 库数据，确保 `region_tag` 符合"拼音小写"约定
- [ ] 7.2 加入 CI 流水线，命名违规阻塞合并

## 8. 文档同步

- [ ] 8.1 [farm-manager-design-spec/04_相关规范/03_数据库与迁移规范.md](../../../farm-manager-design-spec/04_相关规范/03_数据库与迁移规范.md) 表清单修正：`crops` → `crop_templates`；补 `region_tag` 字段说明
- [ ] 8.2 [farm-manager-design-spec/01_正式设计/08_业务模块化.md](../../../farm-manager-design-spec/01_正式设计/08_业务模块化.md) `CropPort.list_templates` 签名加 region 参数
- [ ] 8.3 [farm-manager-design-spec/02_产品需求/01_核心能力清单.md](../../../farm-manager-design-spec/02_产品需求/01_核心能力清单.md) 作物管理能力补"地域化模板"
- [ ] 8.4 [farm-manager-design-spec/03_接口协议/01_HTTP_API协议.md](../../../farm-manager-design-spec/03_接口协议/01_HTTP_API协议.md) 补 `GET /crops/templates/system?region=` 与 `POST /crops/templates/system/{id}/import` 端点
- [ ] 8.5 [farm-manager-design-spec/Readme.md](../../../farm-manager-design-spec/Readme.md) 加变更记录 v0.8

## 9. 集成测试与仿真

- [ ] 9.1 `backend/tests/api/test_crop_templates_system.py`：region 优先匹配 / fallback / 副本导入 / 跨 region 重复
- [ ] 9.2 `backend/simulation/cases/` 新增 1 条用例：徐州用户首次问"想种西瓜" → 推荐 system 模板 → 用户接受 → 落地茬口阶段为徐州天数
- [ ] 9.3 跑 `python -m app.simulation.run --suite smoke` 通过

## 10. 前置依赖

- [ ] 10.1 确认 [`crop-template-system-library`](../crop-template-system-library/proposal.md) 已合并到 main，本提案基于其字段与 API 设计
