# Skill 覆盖矩阵

> 来源：`backend/app/agent/skill_coverage.py`。本文档记录当前系统 API/Service 能力与 LLM Skill 的覆盖关系。

## 状态定义

- `covered_by_skill`：已有 Skill 覆盖。
- `needs_skill`：适合自然语言调用，但仍需补 Skill 或补齐确认链路。
- `admin_skill`：只能通过管理员 Skill 暴露。
- `forbidden_for_llm`：不允许通过 LLM Skill 暴露。
- `no_skill_required`：不需要 Skill。

## 普通业务覆盖状态

当前高优先级普通用户业务能力已补齐 Skill 覆盖；新增或补齐的能力包括：

| 领域 | 功能 | Skill |
| --- | --- | --- |
| cost | 删除/撤销账务记录 | `manage_cost` |
| cost_category | 分类列表、创建、删除 | `manage_cost_categories` |
| crop_template | 模板列表、更新、删除 | `get_crop_templates`、`manage_crop_templates` |
| crop_cycle | 删除茬口 | `delete_crop_cycle` |
| farm_log | 农事记录编辑、删除 | `manage_farm_logs` |
| planting_unit | 种植单元 CRUD | `get_planting_units`、`manage_planting_units` |
| user_settings | 当前用户设置查询、更新 | `get_user_settings`、`manage_user_settings` |

## 已补齐能力

- 账务创建、汇总、趋势查询。
- 茬口创建、查询、阶段和起始日期更新。
- 作物模板创建。
- 作业单创建、查询、更新。
- 未付人工查询和结算。
- 工人查询、创建、更新、停用和恢复。
- 工资保存和更新。
- 账务分类查询、创建和删除。
- 种植单元查询、创建、更新和删除。
- 作物模板查询、更新和高风险删除。
- 农事日志更新和删除。
- 高风险茬口删除。
- 当前用户设置查询和白名单更新。
- 天气查询。

## 敏感边界

- 认证、密码、凭据类能力标记为 `forbidden_for_llm`。
- 管理员用户、配额、trace、配置、prompt reload、缓存清理统一归入 `admin_skill`。
- Agent 自身对话、日报、报告历史等交互入口标记为 `no_skill_required`。
