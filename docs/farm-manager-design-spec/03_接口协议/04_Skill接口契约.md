# 04 — Skill 接口契约

> 状态：草稿 | 维护：BlockShip | 关联：[01_正式设计/02_Skill引擎与契约](../01_正式设计/02_Skill引擎与契约.md)、权威 [.claude/rules/skill-writing.md](../../../.claude/rules/skill-writing.md)

---

## 1. Skill 调用协议

```
Executor 接收 LangChain ToolCall
  ↓
解析 tool_call.name → SkillRegistry.get(name) → Skill 实例
  ↓
解析 tool_call.args → params: dict
  ↓
校验 params 符合 skill.parameters_schema
  ↓
构造 SkillContext（farm_id, user_id, session_id, trace_id, db, memory）
  ↓
检查 skill.meta.permission
  ├─ read → 直接 execute
  ├─ write_confirm → 创建 PendingAction，返回 NEED_CLARIFY
  └─ write（特殊） → 直接 execute（需人工评审声明）
  ↓
Skill.execute(params, context) → SkillResult
  ↓
返回 ToolMessage 给 Runtime
```

## 2. SkillResult 协议

```python
class SkillResult(BaseModel):
    status: ResultStatus    # SUCCESS / FAILED / NEED_CLARIFY
    reply: str              # 中文自然语言
    data: dict | None = None
    pending: PendingActionCreate | None = None

    def to_tool_message(self, tool_call_id: str) -> ToolMessage:
        """转换为 LangChain ToolMessage。"""
```

### 2.1 SUCCESS

```python
SkillResult(
    status=ResultStatus.SUCCESS,
    reply="已记账：化肥 200 元，向老王农资店赊账。",
    data={"cost_id": 123, "amount": 200, "category": "化肥"}
)
```

### 2.2 FAILED

```python
SkillResult(
    status=ResultStatus.FAILED,
    reply="金额超过上限（1000 万），请确认后重试。"
)
```

### 2.3 NEED_CLARIFY

```python
SkillResult(
    status=ResultStatus.NEED_CLARIFY,
    reply="请问这笔账是支出还是收入？",
    pending=PendingActionCreate(
        skill_name="create_cost_record",
        params={"amount": 200, "category": "化肥"},
        summary="化肥 200 元",
        expires_at=datetime.utcnow() + timedelta(minutes=5)
    )
)
```

## 3. PendingAction 协议

```python
class PendingActionCreate(BaseModel):
    skill_name: str
    params: dict
    summary: str               # 用户可见的摘要
    expires_at: datetime
    metadata: dict = {}

class PendingAction(PendingActionCreate):
    id: str                    # UUID
    farm_id: int
    user_id: int
    session_id: str
    created_at: datetime
    status: PendingStatus      # PENDING / CONFIRMED / CANCELLED / EXPIRED / EXECUTED

class PendingActionResult(BaseModel):
    pending_id: str
    executed: bool
    skill_result: SkillResult | None
    error: str | None
```

## 4. SkillContext 协议

```python
class SkillContext(BaseModel):
    farm_id: int               # 当前农场（必填）
    user_id: int               # 当前用户
    session_id: str            # 会话 ID
    trace_id: str              # trace ID
    db: Session                # SQLAlchemy session（注入）
    memory: MemoryService      # Memory 端口（注入）
    # 注入由 Executor 完成，Skill 不自己创建
```

**禁止**：
- Skill 自己读 request 对象
- Skill 自己构造 Session
- Skill 自己创建 MemoryService 实例

## 5. 参数 schema 协议

JSON Schema 子集，**必须满足**：

```yaml
parameters:
  type: object
  properties:
    <param_name>:
      type: string | number | integer | boolean | array | object
      description: <必填，中文，说明用途和约束>
      enum: [...]              # 可选
      default: ...             # 可选
      minimum: ...             # 数字可选
      maximum: ...             # 数字可选
  required:
    - <必填参数>
```

**禁止**：
- `$ref`（LLM 不友好）
- `oneOf` / `anyOf`（LLM 不友好）
- 缺 description（LLM 不知道何时用）
- description 英文（统一中文）

## 6. 写操作 Skill 调用示例

以 `create_cost_record` 为例：

### 6.1 用户输入

> 「昨天买了 200 块化肥，老王农资店赊账」

### 6.2 LLM 决定调用

```json
{
  "name": "create_cost_record",
  "arguments": {
    "amount": 200,
    "category": "化肥",
    "record_date": "2026-06-18",
    "record_type": "cost",
    "note": "向老王农资店赊账",
    "record_subtype": "赊账",
    "counterparty": "老王农资店"
  }
}
```

### 6.3 Executor 处理

```python
skill = registry.get("create_cost_record")
if skill.meta.permission == "write_confirm":
    pending = PendingActionCreate(
        skill_name="create_cost_record",
        params=params,
        summary="化肥 200 元，向老王农资店赊账",
        expires_at=datetime.utcnow() + timedelta(minutes=5)
    )
    return SkillResult(
        status=ResultStatus.NEED_CLARIFY,
        reply="请确认：记账 化肥 200 元（赊账，向老王农资店）？",
        pending=pending
    )
```

### 6.4 Runtime 把 NEED_CLARIFY 转为 SSE

```
event: pending
data: {"pending_id": "...", "summary": "化肥 200 元，向老王农资店赊账", "expires_at": "..."}

event: token
data: {"text": "请确认：记账 化肥 200 元（赊账，向老王农资店）？"}

event: done
data: {"message_id": 123}
```

### 6.5 用户确认

```
POST /agent/chat
{"message": "确认", "session_id": "..."}
```

当前仓库未暴露独立 `/pending/*` HTTP 路由。用户确认/取消由下一轮 `/agent/chat` 或 `/agent/chat/stream` 消息进入 `handle_pending_action()`，再执行 pending action / pending plan。

### 6.6 Executor 真正执行

```python
skill = registry.get(pending.skill_name)
result = await skill.execute(pending.params, context)
# result.status == SUCCESS
# 真正写入 cost 表
```

## 7. 只读 Skill 调用示例

以 `get_cost_summary` 为例：

### 7.1 用户输入

> 「这个月花了多少」

### 7.2 LLM 调用

```json
{
  "name": "get_cost_summary",
  "arguments": {"period": "2026-06"}
}
```

### 7.3 Skill 直接执行

```python
async def execute(self, params, context):
    summary = await LedgerPort.query_summary(
        context.db,
        farm_id=context.farm_id,
        period=params["period"]
    )
    return SkillResult(
        status=ResultStatus.SUCCESS,
        reply=f"本月共支出 {summary.total_yuan} 元，分类最高的是 {summary.top_category}。",
        data=summary.dict()
    )
```

### 7.4 直接返回，无 Pending

## 8. 错误处理协议

| Skill 异常 | SkillResult | 用户感知 |
| --- | --- | --- |
| 必填参数缺失 | `NEED_CLARIFY` + 追问 | 「请问金额是多少？」 |
| 参数超范围 | `FAILED` + 中文提示 | 「金额不能超过 1000 万」 |
| 数据库异常 | `FAILED` + 通用提示 | 「暂时无法记录，请稍后重试」 |
| 越权 | `FAILED` + 权限提示 | 「您没有该农场的操作权限」 |
| 业务规则违反 | `FAILED` + 业务提示 | 「该工人已禁用，无法派工」 |
| 外部服务失败 | `FAILED` + 降级提示 | 「天气服务暂时不可用」 |

**禁止**：
- Skill 抛 raw exception 给 Executor（必须捕获转 SkillResult）
- 错误信息含 traceback 或内部细节
- 错误信息英文

## 9. Skill 注册表查询

```
GET /admin/skills
```

返回：

```json
{
  "items": [
    {
      "name": "create_cost_record",
      "tool_name": "create_cost_record",
      "type": "write",
      "description": "记录农场成本支出。",
      "triggers": ["记账", "买了", "卖了", "赊账"],
      "permission": "write_confirm",
      "direct_call": false,
      "cache": "none",
      "skill_md_path": "backend/app/skills/manage-cost/skill.md",
      "scripts_path": "backend/app/skills/manage-cost/scripts/"
    }
  ]
}
```

## 10. Skill 元数据完整性检查

CI 强制检查（`backend/tests/skills/test_skill_docs.py`）：

| 检查项 | 要求 |
| --- | --- |
| 目录存在 | `backend/app/skills/<name>/` |
| `skill.md` 存在 | 必填 |
| frontmatter `name` | 必填，kebab-case |
| frontmatter `tool_name` | 必填（若 name 是 kebab-case），snake_case |
| frontmatter `type` | 必填，read-only 或 write |
| frontmatter `description` | 必填，非空 |
| frontmatter `triggers` | 必填，list，非空 |
| frontmatter `parameters` | 必填，JSON Schema 合法 |
| 正文 `## 何时使用` | 必填 |
| 正文 `## 不要使用` | 必填 |
| 正文 `## Runtime 策略` | 必填，含 permission / direct_call / direct_return / cache |
| 正文 `## 失败处理` | 必填 |
| 正文 `## 示例` | 必填，至少 1 个 |
| `scripts/main.py` 存在 | 复杂执行 Skill 必填；纯声明或聚合型 Skill 按实现需要 |
| Skill 类继承 Skill 基类 | 必填 |
| Skill 类实现 4 个方法 | 必填（name/description/parameters_schema/execute） |
| 测试文件存在 | 必填 |

任何检查失败 CI 阻塞。

## 11. 相关文档

- [01_正式设计/02_Skill引擎与契约](../01_正式设计/02_Skill引擎与契约.md)
- [01_HTTP_API协议](./01_HTTP_API协议.md)
- [02_Agent内部接口](./02_Agent内部接口.md)
- 权威：[../../../.claude/rules/skill-writing.md](../../../.claude/rules/skill-writing.md)
- 覆盖矩阵：[../../../docs/agent/skill-coverage-matrix.md](../../../docs/agent/skill-coverage-matrix.md)
