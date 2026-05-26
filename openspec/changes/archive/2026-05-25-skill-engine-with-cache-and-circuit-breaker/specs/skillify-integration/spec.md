## Requirements

### R1: Skill 子类实现
- 每个 Skill 继承 `skillify.skills.base.Skill`，实现 `name()`, `description()`, `parameters_schema()`, `execute()`
- Skill 放在 `backend/app/skills/` 目录，文件名与 Skill 名称对应
- execute() 返回 `SkillResult(reply=..., status=ResultStatus.SUCCESS)`

### R2: 自动发现
- SkillManager 通过 `discover_python_package("app.skills")` 扫描目录
- 新增 `.py` 文件放 `skills/` 即自动注册，无需手动 import
- 服务启动时初始化 SkillManager 单例

### R3: LangChain 桥接
- 桥接函数将 SkillManager 中所有 Skill 转为 `langchain_core.tools.StructuredTool`
- parameters_schema (JSON Schema) 转为 Pydantic BaseModel
- Skill.execute() 的 result.reply 作为 Tool 返回值

### R4: 4 个 Skill 迁移
- `WeatherSkill`: 天气预报，调 weather_service
- `CropCycleSkill`: 种植周期查询，查 DB
- `FarmLogSkill`: 农事记录查询，查 DB
- `CostSummarySkill`: 成本汇总，查 DB
- 迁移后删除 `agents/tools.py`

## Acceptance Criteria
- [ ] `GET /agent/chat` 调用后日志显示 Skill 名称而非旧 tool 名
- [ ] 新增 Skill 只需创建 `.py` 文件并重启服务
- [ ] 所有 Skill 通过 SkillManager 自动注册并可列举
