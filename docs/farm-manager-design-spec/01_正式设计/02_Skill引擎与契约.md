# 02 — Skill 引擎与契约

> 状态：草稿 | 维护：BlockShip | 关联：[01_Agent平台架构](./01_Agent平台架构.md)、权威契约 [.claude/rules/skill-writing.md](../../../.claude/rules/skill-writing.md)

---

## 1. Skill 是什么

Skill 是 Agent 调用业务能力的**能力包**。当前实现采用 `skillify` SDK 加载 `backend/app/skills/*/skill.md`，再由 `backend/app/skills/registry/*.yaml` 描述 capability、operation、risk、legacy alias 和治理信息。

Farm Manager 当前代码落地 13 个 Skill 包，覆盖记账、账务分类、茬口、作物模板、地块、农事日志、工单、工人、工资、用户设置、农场状态、天气和外部搜索。一个 Skill 包可以暴露多个 operation，例如 `manage_cost` 覆盖 `create_cost_record`、`get_cost_summary`、`get_debt_summary`、`settle_debt` 等 legacy alias。

## 2. 目录结构（强制）

```
backend/app/skills/<skill-name>/
├── __init__.py
├── skill.md              # 契约文档（机器 + 人）
└── scripts/
    ├── __init__.py
    └── main.py           # 按需存在；复杂 Skill 的执行入口
```

禁止：
- 散放单文件 Skill
- 目录名用 snake_case（必须 kebab-case）
- `skill.md` 缺失或 frontmatter 不全
- 新增 capability/operation 后未同步 `backend/app/skills/registry/*.yaml`

## 3. skill.md 契约（hybrid）

```yaml
---
name: create-cost-record            # kebab-case，文档名
tool_name: create_cost_record       # snake_case，运行时工具名
type: write                         # read-only | write
description: 记录农场成本支出。
triggers:
  - 记账
  - 买了化肥
parameters:
  type: object
  properties:
    amount:
      type: number
      description: 支出金额（>0，≤10000000）。
  required:
    - amount
---

# 成本记账

## 何时使用
...

## 不要使用
...

## 参数推断
...

## Runtime 策略
- permission: write_confirm
- direct_call: false
- direct_return: false
- cache: none

## 失败处理
...

## 示例
- 用户：「昨天买了200块化肥」 -> `create_cost_record(amount=200, category="化肥")`
```

完整字段定义见 [.claude/rules/skill-writing.md](../../../.claude/rules/skill-writing.md)，本 Spec 不复述。

## 4. Skill 类型与权限

| type | permission | 是否需确认 | 缓存 | 直接调用 | 直接返回 |
| --- | --- | --- | --- | --- | --- |
| `read-only` | `read` | 否 | 可选（声明 ttl） | 允许 | 允许 |
| `write` | `write_confirm`（默认） | 是 | 禁止 | 禁止 | 禁止 |
| `write` | `write`（特殊：幂等无副作用） | 否 | 禁止 | 谨慎允许 | 谨慎允许 |

**写操作默认走 Pending Action 二次确认**，例外需要在 `skill.md` 显式声明并经人工评审。

## 5. Skill 类实现规范

```python
class CreateCostRecordSkill(Skill):
    def name(self) -> str:
        return "create_cost_record"

    def description(self) -> str:
        return "记录农场成本支出。触发词：记账、买了、卖了、赊账、元、块"

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {...},
            "required": [...],
        }

    async def execute(self, params: dict, context: SkillContext) -> SkillResult:
        # 1. 参数校验
        # 2. 通过 service 写业务数据（禁止直接 SQL）
        # 3. 返回 SkillResult(status=SUCCESS/FAILED/NEED_CLARIFY, reply="...")
```

**编码规则**（强制）：
1. 通过 `build_skill_context()` 注入的 `SkillContext` 获取 farm、LLM 与运行时上下文
2. `farm_id` 从 `context.farm_id` 获取，必要时同时携带 `farm_uid`
3. 返回值统一 `SkillResult(status=ResultStatus.SUCCESS/FAILED/NEED_CLARIFY, reply="...")`
4. 写操作禁止 `@cached`
5. 复用 service 层，不在 Skill 中直接写 SQL
6. 使用 `logging.getLogger(__name__)` 记录关键操作和异常

## 6. 当前 Skill 包清单（按业务域）

### 6.1 记账域

| Skill 包 | 主要 operation / legacy alias | 触发词 |
| --- | --- | --- |
| `manage-cost` | create/query/analyze/delete/settle；兼容 `create_cost_record`、`get_cost_summary`、`get_debt_summary`、`settle_debt` 等 | 记账、买了、卖了、赊账、欠款、趋势 |
| `manage-cost-categories` | query/manage；兼容 `get_cost_categories`、`manage_cost_categories` | 分类、收入分类、支出分类 |
| `manage-labor-payment` | 工资查询、补付、结算 | 工资、应付、补付 |

### 6.2 茬口与作物域

| Skill 包 | 主要 operation / legacy alias | 触发词 |
| --- | --- | --- |
| `manage-crop-templates` | query/create/update/delete/import；兼容 `create_crop_template`、`get_crop_templates` | 作物模板、系统模板、导入模板 |
| `manage-crop-cycle` | create/query/update/delete；兼容 `create_crop_cycle`、`get_crop_cycles`、`update_crop_stage` | 种一茬、当前茬口、阶段、删除茬口 |
| `manage-planting-units` | query/create/update/delete | 地块、棚、种植单元 |

### 6.3 农事与工人域

| Skill 包 | 主要 operation / legacy alias | 触发词 |
| --- | --- | --- |
| `manage-farm-logs` | create/query/update/delete；兼容 `log_farm_activity` | 浇水、打药、施肥、农事日志 |
| `manage-work-orders` | create/query/update | 派工、作业单、农事工单 |
| `manage-workers` | query/create/update/deactivate | 工人、新增工人、离职工人 |

### 6.4 农场与设置域

| Skill 包 | 主要 operation / legacy alias | 触发词 |
| --- | --- | --- |
| `farm-status` | query | 农场概况、当前状态 |
| `manage-user-settings` | query/update | 我的设置、修改人设、默认城市 |
| `weather` | query | 天气、预报、下雨、预警 |
| `web_search` | query | 网上查、搜索、行情 |

完整清单与触发词矩阵见 [../../../docs/agent/skill-coverage-matrix.md](../../../docs/agent/skill-coverage-matrix.md)。

## 7. Skill 注册流程

```
1. `SkillManager(python_packages=["app.skills"])` 扫描 `backend/app/skills/*/skill.md`
2. `app/skills/registry/loader.py` 读取 `skills.yaml`、`domains.yaml`、`aliases.yaml`
3. `app/skills/metadata.py` 把 capability / operation / risk / legacy alias 附加到 Skill 和 LangChain Tool
4. `agent/router/service.py` 结合 registry、classifier、retriever、policy 选择候选工具
5. `agent/runtime/tool_executor.py` 调用 `Skill.execute(params, SkillContext)`
6. Trace 记录 tool call、latency、token、reflection 和 router evidence
```

## 8. Skill 与 Router 的关系

```
用户输入 → agent/router
  ├─ RuleIntentClassifier 提取领域/意图/风险信号
  ├─ CandidateRetriever 从 SkillCatalog 检索候选
  ├─ RouterPolicy 做风险裁剪和 fallback
  └─ 输出 RouterDecision(selected_tools, reason, evidence)

candidates → LLM.tools 参数（绑定）
LLM 决定调用哪个 → Executor 执行
```

候选名单会减少 LLM 的 tools schema 长度，节省 token。

## 9. Skill 错误处理

| 错误码 | 场景 | 处理 |
| --- | --- | --- |
| `MISSING_REQUIRED_PARAM` | 必填参数缺失 | 返回 NEED_CLARIFY + 中文追问 |
| `INVALID_PARAM_VALUE` | 参数超范围 | 返回 FAILED + 中文提示 |
| `DB_ERROR` | 数据库异常 | 返回 FAILED + 通用错误消息，记日志 |
| `PERMISSION_DENIED` | 越权 | 返回 FAILED + 权限提示 |
| `PENDING_REQUIRED` | 写操作需确认 | 返回 NEED_CLARIFY + 确认话术 |
| `EXTERNAL_SERVICE_ERROR` | 天气/LLM 失败 | 返回 FAILED + 降级提示 |

**禁止**：
- 把内部异常 traceback 暴露给用户
- 缺参时猜测业务关键字段（如金额、分类）
- 写操作不经过 Pending 直接执行（除非显式声明 `permission: write`）

## 10. 测试规范

```
backend/tests/skills/test_<skill_name>.py
```

最少 3 个测试类：
- `Meta`：name / description / schema 校验
- `Normal`：正常流程，至少 1 个 happy path
- `Error`：参数校验、边界、数据库异常

DB 必须 mock，使用 `unittest.mock.patch`。

CI 校验：`backend/tests/skills/test_skill_docs.py` 扫描全量 `skill.md` 契约。

## 11. Skill 治理流程

```
新增 Skill：
  1. 在 backend/app/skills/ 创建目录
  2. 写 skill.md（含 frontmatter + 正文）
  3. 按需实现 scripts/main.py
  4. 在 backend/tests/skills/ 写测试
  5. 更新 backend/app/skills/registry/skills.yaml / aliases.yaml
  6. 更新 docs/agent/skill-coverage-matrix.md
  7. 在 DataFlywheel 创建初始 regression case（可选）
  8. PR 评审：触发词去重、与现有 Skill 边界、参数 schema 完整性

废弃 Skill：
  1. 在 skill.md frontmatter 增加 deprecated: true
  2. SkillRegistry 跳过 deprecated
  3. 90 天观察期后物理删除
```

## 12. 相关文档

- [01_Agent平台架构](./01_Agent平台架构.md)
- [03_接口协议/04_Skill接口契约](../03_接口协议/04_Skill接口契约.md)
- 权威契约：[../../../.claude/rules/skill-writing.md](../../../.claude/rules/skill-writing.md)
- 覆盖矩阵：[../../../docs/agent/skill-coverage-matrix.md](../../../docs/agent/skill-coverage-matrix.md)
