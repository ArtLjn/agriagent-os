# 02 — Skill 引擎与契约

> 状态：草稿 | 维护：BlockShip | 关联：[01_Agent平台架构](./01_Agent平台架构.md)、权威契约 [.claude/rules/skill-writing.md](../../../.claude/rules/skill-writing.md)

---

## 1. Skill 是什么

Skill 是 Agent 调用的**原子能力单元**，每个 Skill 解决一类问题：
- `create_cost_record` — 记一笔账
- `get_cost_summary` — 查询成本汇总
- `create_crop_cycle` — 创建一茬种植
- `manage_pending_action` — 处理待确认动作
- ...

Farm Manager 当前已落地 **30+ Skill**，覆盖记账、茬口、工人、日志、债务、用户设置等业务域。

## 2. 目录结构（强制）

```
backend/app/agent/skills/<skill-name>/
├── __init__.py
├── skill.md              # 契约文档（机器 + 人）
└── scripts/
    ├── __init__.py
    └── main.py           # Skill 实现入口
```

禁止：
- 散放单文件 Skill
- 目录名用 snake_case（必须 kebab-case）
- `skill.md` 缺失或 frontmatter 不全

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
1. 数据库操作通过 `SessionLocal()` 获取 session，`finally` 关闭
2. `farm_id` 从 `context.farm_id` 获取
3. 返回值统一 `SkillResult(status=ResultStatus.SUCCESS/FAILED/NEED_CLARIFY, reply="...")`
4. 写操作禁止 `@cached`
5. 复用 service 层，不在 Skill 中直接写 SQL
6. 使用 `logging.getLogger(__name__)` 记录关键操作和异常

## 6. 当前 Skill 清单（按业务域）

### 6.1 记账域

| Skill | type | 触发词 |
| --- | --- | --- |
| `create_cost_record` | write | 记账、买了、卖了、赊账 |
| `delete_cost_record` | write | 删账、撤销记账 |
| `get_cost_summary` | read-only | 这个月花了多少、成本汇总 |
| `get_cost_analytics` | read-only | 同比、环比、趋势 |
| `manage_cost_categories` | write | 新增分类、改分类 |
| `get_cost_categories` | read-only | 有哪些分类 |
| `get_debt_summary` | read-only | 赊账、欠款 |
| `get_labor_payables` | read-only | 工资应付 |

### 6.2 茬口与作物域

| Skill | type | 触发词 |
| --- | --- | --- |
| `create_crop_template` | write | 创建作物模板（按 region 优先推荐系统模板，详见 [../../../docs/superpowers/specs/2026-06-19-knowledge-and-memory-architecture-design.md § 3](../../../docs/superpowers/specs/2026-06-19-knowledge-and-memory-architecture-design.md)） |
| `manage_crop_templates` | write | 改作物模板 |
| `get_crop_templates` | read-only | 有哪些作物 |
| `create_crop_cycle` | write | 种一茬、新一茬 |
| `delete_crop_cycle` | write | 删茬口 |
| `get_crop_cycles` | read-only | 当前茬口、历史茬口 |

### 6.3 农事与工人域

| Skill | type | 触发词 |
| --- | --- | --- |
| `log_farm_activity` | write | 记一笔农事、今天浇水了 |
| `manage_farm_logs` | write | 改日志、删日志 |
| `farm_logs` | read-only | 这周做了什么 |
| `create_operation_work_order` | write | 派工、安排活 |
| `get_operation_work_orders` | read-only | 工单列表 |
| `get_workers` | read-only | 工人列表 |
| `manage_planting_units` | write | 地块管理 |
| `get_planting_units` | read-only | 有哪些地块 |

### 6.4 农场与设置域

| Skill | type | 触发词 |
| --- | --- | --- |
| `farm_status` | read-only | 农场概况 |
| `get_user_settings` | read-only | 我的设置 |
| `manage_user_settings` | write | 改设置 |

完整清单与触发词矩阵见 [../../../docs/agent/skill-coverage-matrix.md](../../../docs/agent/skill-coverage-matrix.md)。

## 7. Skill 注册流程

```
1. 启动时 SkillRegistry 扫描 backend/app/agent/skills/*/skill.md
2. 解析 frontmatter，构建 skill catalog
3. 写入 system prompt 的「Skill 路由表」（第一层）
4. LLM 调用 load_skill / 直接 tool_call 时，注入完整 prompt（第二层）
5. Executor 调用 Skill.execute()
6. Trace 记录 skill_call_total / latency / token
```

## 8. Skill 与 Planner 的关系

```
用户输入 → Planner
  ├─ 关键词匹配（tool_selection_rules.py）→ 候选 Skill 名单
  ├─ LLM 推理（可选，规则失败时）→ 候选 Skill 名单
  └─ 输出 candidates: list[str]

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
  1. 在 backend/app/agent/skills/ 创建目录
  2. 写 skill.md（含 frontmatter + 正文）
  3. 实现 scripts/main.py
  4. 在 backend/tests/skills/ 写测试
  5. 更新 docs/agent/skill-coverage-matrix.md
  6. 在 DataFlywheel 创建初始 regression case（可选）
  7. PR 评审：触发词去重、与现有 Skill 边界、参数 schema 完整性

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
