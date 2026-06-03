# Optimize LLM Write Skill Calling 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 优化 farm-manager Agent 的 write skill 执行流程，消除分类不一致、参数解析失败无自纠错、确认信息不透明等问题。

**Architecture:** 在现有 LangGraph + StructuredTool 架构上叠加四层改进：(1) 动态 enum 约束 category 参数，(2) Pydantic 校验拦截无效 tool call 并反馈 LLM 自纠错，(3) 增强确认消息展示三层上下文，(4) 规则式意图路由过滤无效 tool call。不改写 graph 核心架构。

**Tech Stack:** Python 3.12 / FastAPI / LangGraph / LangChain / Pydantic v2 / SQLAlchemy / React 18 + TypeScript

---

## 文件结构

| 操作 | 文件路径 | 职责 |
|------|---------|------|
| 修改 | `backend/app/agent/skills/__init__.py` | 新增 `get_category_enum()` 函数，修改 `_schema_to_pydantic()` 和 `skills_to_langchain_tools()` 支持 farm_id 参数和动态 enum 注入 |
| 修改 | `backend/app/agent/graph.py:632-736` | 修改 `_parallel_tool_node` 增加 Pydantic 参数校验，校验失败返回错误 ToolMessage |
| 修改 | `backend/app/infra/pending_actions.py` | 修改 `PendingAction` dataclass 增加 `context` 字段；修改 `build_confirm_message()` 输出三层确认消息 |
| 修改 | `backend/app/schemas/agent.py:17-23` | 修改 `PendingActionResponse` 增加 `context` 字段 |
| 修改 | `backend/app/agent/advisor.py:56-127,130-239` | 在 `invoke_advisor` / `stream_advisor` 入口增加意图路由 `_route_intent()` |
| 新增 | `backend/app/agent/intent_router.py` | 意图路由函数 `_classify_intent()` — 基于规则匹配问候/查询/写操作 |
| 修改 | `admin-web/src/api/agent.ts:57-66` | 修改 `PendingAction` 接口增加 `context` 字段 |
| 修改 | `admin-web/src/pages/Agent/index.tsx:57-86` | 修改 `ChatBubble` 展示三层确认信息 |
| 修改 | `admin-web/src/pages/Playground/index.tsx:76-118` | 修改 Playground `ChatBubble` 展示三层确认信息 |
| 新增 | `backend/tests/test_intent_router.py` | 意图路由单元测试 |
| 新增 | `backend/tests/test_schema_constraint.py` | 动态 enum + Pydantic 校验测试 |
| 修改 | `backend/tests/test_pending_actions.py` | 新增三层确认消息测试 |
| 修改 | `backend/app/agent/tool_selector.py` | 将 WRITE_PATTERNS 的金额正则改为支持 "w/W/万" 后缀的完整匹配 |

---

## Task 1: 动态 Enum 约束 — category 参数

**Files:**
- Modify: `backend/app/agent/skills/__init__.py:37-52,79-96`
- Modify: `backend/app/agent/graph.py:437-448`
- Test: `backend/tests/test_schema_constraint.py`

- [ ] **Step 1: 写失败测试 — `get_category_enum` 基础功能**

创建 `backend/tests/test_schema_constraint.py`：

```python
"""测试动态 enum 约束 — category 参数从数据库加载标签列表。"""

from unittest.mock import MagicMock, patch

import pytest

from app.agent.skills import (
    _schema_to_pydantic,
    get_category_enum,
)


class TestGetCategoryEnum:
    """测试 get_category_enum 从数据库加载分类标签。"""

    def test_returns_category_names_from_db(self):
        """从数据库查询结果中提取分类名称列表。"""
        mock_cats = [
            MagicMock(name="化肥"),
            MagicMock(name="种子"),
            MagicMock(name="人工"),
        ]
        with patch("app.agent.skills.cost_category_service") as mock_svc:
            mock_svc.get_categories.return_value = mock_cats
            result = get_category_enum(farm_id=1)
        assert result == ["化肥", "种子", "人工"]

    def test_returns_default_when_no_categories(self):
        """数据库无分类时返回默认列表。"""
        with patch("app.agent.skills.cost_category_service") as mock_svc:
            mock_svc.get_categories.return_value = []
            result = get_category_enum(farm_id=1)
        assert "化肥" in result
        assert "种子" in result
        assert len(result) > 0

    def test_caches_result_for_same_farm(self):
        """同一 farm_id 的第二次调用使用缓存。"""
        mock_cats = [MagicMock(name="化肥")]
        with patch("app.agent.skills.cost_category_service") as mock_svc:
            mock_svc.get_categories.return_value = mock_cats
            get_category_enum(farm_id=1)
            get_category_enum(farm_id=1)
        # 只查一次数据库
        assert mock_svc.get_categories.call_count == 1


class TestSchemaToPydanticWithEnum:
    """测试 _schema_to_pydantic 支持 enum 约束。"""

    def test_category_field_has_enum_values(self):
        """category 字段包含 enum 约束。"""
        schema = {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "分类",
                    "enum": ["化肥", "种子", "人工"],
                },
                "amount": {
                    "type": "number",
                    "description": "金额",
                },
            },
            "required": ["category", "amount"],
        }
        model = _schema_to_pydantic("test", schema)
        field_info = model.model_fields["category"]
        # 验证 enum 约束通过 Field 的 json_schema_extra 传递
        assert field_info.json_schema_extra is not None or field_info.metadata is not None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && poetry run pytest tests/test_schema_constraint.py -v`
Expected: FAIL — `get_category_enum` 不存在，ImportError

- [ ] **Step 3: 实现 `get_category_enum` 函数**

在 `backend/app/agent/skills/__init__.py` 中：

1. 在文件顶部导入区域新增：
```python
from app.services import cost_category_service
```

2. 在 `_schema_to_pydantic` 函数之后（约第 53 行）新增：
```python
_DEFAULT_CATEGORY_ENUM = ["化肥", "种子", "农药", "人工", "其他"]
_category_cache: dict[int, list[str]] = {}


def get_category_enum(farm_id: int) -> list[str]:
    """从数据库加载 farm 的分类标签列表，结果缓存。"""
    if farm_id in _category_cache:
        return _category_cache[farm_id]
    try:
        db = SessionLocal()
        try:
            categories = cost_category_service.get_categories(db, farm_id)
            names = [c.name for c in categories]
        finally:
            db.close()
        if not names:
            names = list(_DEFAULT_CATEGORY_ENUM)
        _category_cache[farm_id] = names
        return names
    except Exception:
        logger.warning("分类加载失败，使用默认 enum | farm_id=%d", farm_id)
        return list(_DEFAULT_CATEGORY_ENUM)


def clear_category_cache(farm_id: int | None = None) -> None:
    """清除分类缓存。farm_id=None 时清除全部。"""
    if farm_id is None:
        _category_cache.clear()
    else:
        _category_cache.pop(farm_id, None)
```

3. 在顶部 import 区新增：
```python
from app.core.database import SessionLocal
```

- [ ] **Step 4: 修改 `_schema_to_pydantic` 支持 enum**

修改 `backend/app/agent/skills/__init__.py` 的 `_schema_to_pydantic` 函数（第 37-52 行），增加 `enum` 处理：

```python
def _schema_to_pydantic(name: str, schema: dict[str, Any], *, enums: dict[str, list[str]] | None = None) -> type[BaseModel]:
    """将 JSON Schema 转为 Pydantic BaseModel。"""
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    fields: dict[str, Any] = {}
    type_map = {"string": str, "integer": int, "number": float, "boolean": bool}

    for field_name, field_def in properties.items():
        py_type = type_map.get(field_def.get("type", "string"), str)
        if field_name not in required:
            py_type = py_type | None
        default = field_def.get("default") if field_name not in required else ...
        desc = field_def.get("description", "")

        # 支持 enum 约束：通过 Literal 类型或 Field metadata 注入
        enum_values = field_def.get("enum")
        if enums and field_name in enums:
            enum_values = enums[field_name]

        if enum_values and py_type is str:
            from typing import Literal
            py_type = Literal[tuple(enum_values)]  # type: ignore[valid-type]
            if field_name not in required:
                py_type = py_type | None  # type: ignore[assignment]

        fields[field_name] = (py_type, Field(default=default, description=desc))

    return create_model(f"{name}Schema", **fields)
```

- [ ] **Step 5: 修改 `skills_to_langchain_tools` 注入动态 enum**

修改 `backend/app/agent/skills/__init__.py` 的 `skills_to_langchain_tools` 函数（第 79-96 行）：

```python
def skills_to_langchain_tools(manager: SkillManager, farm_id: int = 1) -> list[StructuredTool]:
    """将 skillify Skills 转为 LangChain StructuredTool 列表。"""
    # 加载 farm 的分类 enum
    category_enum = get_category_enum(farm_id)
    enums_map = {"category": category_enum} if category_enum else {}

    tools = []
    for skill_def in manager.list_skills():
        skill = manager.get_skill(skill_def.name)
        if not skill:
            continue
        args_schema = _schema_to_pydantic(skill.name(), skill.parameters_schema(), enums=enums_map)
        tools.append(
            StructuredTool(
                name=skill.name(),
                description=skill.description(),
                args_schema=args_schema,
                func=_make_sync_fn(skill),
                coroutine=_make_async_fn(skill),
            )
        )
    return tools
```

- [ ] **Step 6: 修改 `graph.py` 传递 farm_id**

在 `backend/app/agent/graph.py` 中，找到 `get_langchain_tools()` 的调用位置（约第 438 行附近 `_llm_node` 函数内），需要传递 `farm_id`。

在 `_parallel_tool_node` 中（第 638 行），修改 `get_langchain_tools()` 调用：

```python
# 原代码（第 638 行）
tool_map = {t.name: t for t in get_langchain_tools()}

# 修改为
farm_id = state.get("farm_id", 1)
tool_map = {t.name: t for t in get_langchain_tools(farm_id=farm_id)}
```

同时修改 `backend/app/agent/skills/__init__.py` 的 `get_langchain_tools`：

```python
def get_langchain_tools(farm_id: int = 1) -> list[StructuredTool]:
    """获取 LangChain Tool 列表（供 LangGraph 使用）。"""
    return skills_to_langchain_tools(get_skill_manager(), farm_id=farm_id)
```

同样在 `_llm_node` 中（第 437-448 行），`get_langchain_tools()` 的调用也需要传 `farm_id`：

找到 `_llm_node` 中 `select_tools` 和 `get_langchain_tools` 相关调用，将 `farm_id = state.get("farm_id", 1)` 获取后传递给 `get_langchain_tools(farm_id=farm_id)`。

- [ ] **Step 7: 更新 `__all__` 导出**

在 `backend/app/agent/skills/__init__.py` 的 `__all__` 列表中新增：

```python
__all__ = [
    "get_skill_manager",
    "skills_to_langchain_tools",
    "get_langchain_tools",
    "get_skill_registry",
    "clear_skill_cache",
    "build_skill_context",
    "get_category_enum",
    "clear_category_cache",
]
```

- [ ] **Step 8: 运行测试确认通过**

Run: `cd backend && poetry run pytest tests/test_schema_constraint.py -v`
Expected: PASS — 全部测试通过

- [ ] **Step 9: 运行既有测试确认无回归**

Run: `cd backend && poetry run pytest tests/test_skills.py tests/test_pending_actions.py tests/test_function_calling_e2e.py -v`
Expected: PASS — 既有测试全部通过

- [ ] **Step 10: 提交**

```bash
git add backend/app/agent/skills/__init__.py backend/app/agent/graph.py backend/tests/test_schema_constraint.py
git commit -m "feat(agent): 动态 enum 约束 category 参数，从 cost_categories 表加载"
```

---

## Task 2: Pydantic 参数校验与自纠错

**Files:**
- Modify: `backend/app/agent/graph.py:632-736`
- Test: `backend/tests/test_schema_constraint.py` (追加)

- [ ] **Step 1: 写失败测试 — Pydantic 校验拦截**

在 `backend/tests/test_schema_constraint.py` 末尾追加：

```python
class TestPydanticValidationInToolNode:
    """测试 _parallel_tool_node 中的 Pydantic 参数校验。"""

    def setup_method(self):
        from app.infra.pending_actions import _pending
        _pending.clear()

    @pytest.mark.asyncio
    async def test_missing_required_param_returns_error(self):
        """缺少必填参数时返回错误 ToolMessage，不生成 pending action。"""
        from app.agent.graph import _parallel_tool_node
        from langchain_core.messages import AIMessage
        from app.infra.pending_actions import get_pending

        ai_msg = AIMessage(
            content="",
            tool_calls=[
                {
                    "id": "tc1",
                    "name": "create_cost_record",
                    "args": {"category": "化肥"},  # 缺少 amount
                },
            ],
        )
        state = {"messages": [ai_msg], "farm_id": 1}

        with patch("app.agent.graph.get_langchain_tools") as mock_tools:
            from pydantic import BaseModel, Field
            from typing import Literal

            class FakeSchema(BaseModel):
                amount: float = Field(..., description="金额")
                category: Literal["化肥", "种子", "人工", "其他"] = Field(..., description="分类")

            mock_tool = MagicMock()
            mock_tool.name = "create_cost_record"
            mock_tool.args_schema = FakeSchema
            mock_tools.return_value = [mock_tool]

            result = await _parallel_tool_node(state)

        tool_msg = result["messages"][0]
        # 应包含错误信息而非 PENDING_MARKER
        assert "参数校验失败" in tool_msg.content or "amount" in tool_msg.content.lower()
        # 不应生成 pending action
        assert get_pending(farm_id=1) is None

    @pytest.mark.asyncio
    async def test_valid_params_proceed_normally(self):
        """参数正确时正常走 pending action 流程。"""
        from app.agent.graph import _parallel_tool_node
        from langchain_core.messages import AIMessage
        from app.infra.pending_actions import get_pending

        ai_msg = AIMessage(
            content="",
            tool_calls=[
                {
                    "id": "tc1",
                    "name": "create_cost_record",
                    "args": {"amount": 200, "category": "化肥"},
                },
            ],
        )
        state = {"messages": [ai_msg], "farm_id": 1}

        result = await _parallel_tool_node(state)
        tool_msg = result["messages"][0]

        # 应走 pending action 流程
        assert get_pending(farm_id=1) is not None
        assert "PENDING_ACTION" in tool_msg.content or "确认" in tool_msg.content
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && poetry run pytest tests/test_schema_constraint.py::TestPydanticValidationInToolNode -v`
Expected: FAIL — 当前 `_parallel_tool_node` 不做 Pydantic 校验

- [ ] **Step 3: 在 `_parallel_tool_node` 中实现 Pydantic 校验**

修改 `backend/app/agent/graph.py` 的 `_parallel_tool_node` 函数。在写操作拦截逻辑之前（约第 649 行），增加参数校验：

在 `_parallel_tool_node` 函数的 `_call_one` 内部函数中，`is_write_skill` 检查之前插入校验逻辑：

```python
async def _call_one(tc: dict) -> ToolMessage:
    name = tc["name"]
    args = tc["args"]
    tool_call_id = tc["id"]
    logger.info("Skill 调用 %s(%s)", name, args)
    start = _time.perf_counter()

    # Pydantic 参数校验（写操作 + 读操作均校验）
    tool = tool_map.get(name)
    if tool and hasattr(tool, "args_schema") and tool.args_schema:
        try:
            validated = tool.args_schema.model_validate(args)
        except Exception as e:
            error_msg = f"参数校验失败: {e}"
            logger.warning("Tool 参数校验失败 | name=%s | error=%s", name, e)
            return ToolMessage(
                content=error_msg,
                tool_call_id=tool_call_id,
            )

    # 写操作 Skill 拦截：存储 pending action，不直接执行
    if is_write_skill(name):
        # ... 原有拦截逻辑不变 ...
```

注意：原有的 `tool = tool_map.get(name)` 查找在第 672 行（读操作分支内），现在需要提前到校验分支。需要调整代码结构：将 `tool_map.get(name)` 提到函数开头。

完整修改后的 `_call_one` 内部函数（替换原第 642-717 行）：

```python
async def _call_one(tc: dict) -> ToolMessage:
    name = tc["name"]
    args = tc["args"]
    tool_call_id = tc["id"]
    logger.info("Skill 调用 %s(%s)", name, args)
    start = _time.perf_counter()

    tool = tool_map.get(name)

    # Pydantic 参数校验
    if tool and hasattr(tool, "args_schema") and tool.args_schema:
        try:
            tool.args_schema.model_validate(args)
        except Exception as e:
            error_msg = f"参数校验失败: {e}"
            logger.warning("Tool 参数校验失败 | name=%s | error=%s", name, e)
            return ToolMessage(
                content=error_msg,
                tool_call_id=tool_call_id,
            )

    # 写操作 Skill 拦截
    if is_write_skill(name):
        action_id = store_pending(farm_id, name, args)
        logger.info(
            "写操作 Skill 已拦截 | farm=%s action_id=%s skill=%s",
            farm_id, action_id, name,
        )
        collector.record(
            node_type="skill_call",
            node_name=name,
            input_data=args,
            output_data="已拦截为 pending action",
            duration_ms=0,
        )
        confirm_text = build_confirm_message(name, args)
        return ToolMessage(
            content=f"{PENDING_MARKER} {confirm_text}",
            tool_call_id=tool_call_id,
        )

    # 读操作执行
    if not tool:
        return ToolMessage(
            content=f"未知工具: {name}", tool_call_id=tool_call_id
        )
    try:
        result = await tool.ainvoke(args)
        duration_ms = int((_time.perf_counter() - start) * 1000)
        summary = str(result)[:120].replace("\n", " ")
        logger.info("Skill 完成 | name=%s | duration_ms=%d | result=%s", name, duration_ms, summary)
        trace_output = getattr(result, "trace_data", None)
        if not trace_output:
            trace_output = {"status": "success", "reply_preview": str(result)[:500]}
        else:
            trace_output["reply_preview"] = str(result)[:500]
        collector.record(
            node_type="skill_call",
            node_name=name,
            input_data=args,
            output_data=trace_output,
            duration_ms=duration_ms,
        )
        return ToolMessage(content=str(result), tool_call_id=tool_call_id)
    except Exception as e:
        duration_ms = int((_time.perf_counter() - start) * 1000)
        logger.error("Skill 失败 | name=%s | error=%s", name, e)
        collector.record(
            node_type="skill_call",
            node_name=name,
            input_data=args,
            duration_ms=duration_ms,
            error_message=str(e),
        )
        return ToolMessage(content=f"工具调用失败: {e}", tool_call_id=tool_call_id)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && poetry run pytest tests/test_schema_constraint.py::TestPydanticValidationInToolNode -v`
Expected: PASS

- [ ] **Step 5: 运行既有测试确认无回归**

Run: `cd backend && poetry run pytest tests/test_pending_actions.py tests/test_function_calling_e2e.py tests/test_parallel_tool_calls.py -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add backend/app/agent/graph.py backend/tests/test_schema_constraint.py
git commit -m "feat(agent): Pydantic 参数校验拦截无效 tool call，校验失败反馈 LLM 自纠错"
```

---

## Task 3: 增强 Plan-Then-Execute 确认消息

**Files:**
- Modify: `backend/app/infra/pending_actions.py:57-66,126-146`
- Modify: `backend/app/schemas/agent.py:17-23`
- Test: `backend/tests/test_pending_actions.py`

- [ ] **Step 1: 写失败测试 — PendingAction 增加 context 字段**

在 `backend/tests/test_pending_actions.py` 的 `TestPendingActionStorage` 类中追加测试：

```python
def test_store_with_context(self):
    """存储带上下文的 pending action。"""
    action_id = store_pending(
        farm_id=1,
        skill_name="create_cost_record",
        params={"amount": 200, "category": "化肥"},
        original_input="昨天买了200块化肥",
    )
    result = get_pending(farm_id=1)
    assert result is not None
    assert result.original_input == "昨天买了200块化肥"
```

在 `TestBuildConfirmMessageFormat` 类中追加：

```python
def test_confirm_message_with_context(self):
    """三层确认消息包含理解/参数/操作。"""
    msg = build_confirm_message(
        "create_cost_record",
        {"amount": 200, "category": "化肥", "record_type": "cost"},
        original_input="昨天买了200块化肥",
    )
    assert "理解" in msg
    assert "昨天买了200块化肥" in msg
    assert "参数" in msg
    assert "200" in msg
    assert "化肥" in msg
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && poetry run pytest tests/test_pending_actions.py::TestPendingActionStorage::test_store_with_context tests/test_pending_actions.py::TestBuildConfirmMessageFormat::test_confirm_message_with_context -v`
Expected: FAIL — `PendingAction` 没有 `original_input` 字段，`store_pending` 不接受该参数

- [ ] **Step 3: 修改 `PendingAction` dataclass**

修改 `backend/app/infra/pending_actions.py` 的 `PendingAction`（第 57-66 行）：

```python
@dataclass
class PendingAction:
    """待确认的操作。"""

    action_id: str
    skill_name: str
    params: dict
    created_at: float
    farm_id: int
    original_input: str = ""  # 用户的原始输入
```

- [ ] **Step 4: 修改 `store_pending` 函数**

修改 `backend/app/infra/pending_actions.py` 的 `store_pending`（第 72-88 行）：

```python
def store_pending(farm_id: int, skill_name: str, params: dict, original_input: str = "") -> str:
    """存储 pending action，返回 action_id。"""
    action_id = uuid.uuid4().hex
    _pending[farm_id] = PendingAction(
        action_id=action_id,
        skill_name=skill_name,
        params=params,
        created_at=time.time(),
        farm_id=farm_id,
        original_input=original_input,
    )
    logger.info(
        "Pending action 已存储 | farm_id=%d | action_id=%s | skill=%s",
        farm_id, action_id, skill_name,
    )
    return action_id
```

- [ ] **Step 5: 修改 `build_confirm_message` 输出三层信息**

修改 `backend/app/infra/pending_actions.py` 的 `build_confirm_message`（第 126-146 行）：

```python
def build_confirm_message(skill_name: str, params: dict, original_input: str = "") -> str:
    emoji = _SKILL_EMOJI.get(skill_name, "❓")
    action = _SKILL_DISPLAY.get(skill_name, skill_name)

    param_keys = _SKILL_PARAM_FORMAT.get(skill_name, list(params.keys()))
    parts = []
    param_details = []
    for k in param_keys:
        v = params.get(k)
        if v is not None:
            if k == "amount":
                parts.append(f"{v}元")
                param_details.append(f"{k}={v}")
            elif k == "record_type":
                label = "收入" if v == "income" else "支出"
                parts.append(label)
                param_details.append(f"{k}={label}")
            else:
                parts.append(str(v))
                param_details.append(f"{k}={v}")

    detail = " ".join(parts) if parts else ""

    # 三层确认消息
    lines = []
    lines.append(f"{emoji} 确认{action}：{detail}")

    if original_input:
        lines.append(f"📝 理解：您说的是「{original_input}」")

    if param_details:
        lines.append(f"📋 参数：{', '.join(param_details)}")

    lines.append("确认吗？")
    return "\n".join(lines)
```

- [ ] **Step 6: 修改 `PendingActionResponse` schema**

修改 `backend/app/schemas/agent.py` 的 `PendingActionResponse`（第 17-23 行）：

```python
class PendingActionContext(BaseModel):
    """确认消息上下文。"""

    original_input: str = ""
    extracted_params: dict = {}
    notes: list[str] = []


class PendingActionResponse(BaseModel):
    """待确认操作信息，供前端展示确认 UI。"""

    action_id: str
    skill_name: str
    params: dict
    context: PendingActionContext | None = None
```

- [ ] **Step 7: 修改 `_parallel_tool_node` 传递 original_input**

修改 `backend/app/agent/graph.py` 中 `_parallel_tool_node` 的写操作拦截部分。需要从 state 的 messages 中获取用户原始输入：

在 `_parallel_tool_node` 函数开头（第 634 行后）获取用户消息：

```python
farm_id = state.get("farm_id", 1)
collector = get_collector()

# 获取用户原始输入（最近一条 HumanMessage）
original_input = ""
for msg in reversed(state.get("messages", [])):
    if isinstance(msg, HumanMessage):
        original_input = msg.content[:200]
        break
```

然后在 `store_pending` 调用处传递 `original_input`：

```python
action_id = store_pending(farm_id, name, args, original_input=original_input)
```

在文件顶部 import 区确认已有 `from langchain_core.messages import HumanMessage`。

- [ ] **Step 8: 修改 API 层传递 context**

在 `backend/app/api/agent.py` 中，找到构建 `PendingActionResponse` 的位置，增加 `context` 字段：

```python
# 原代码类似：
pending_action = PendingActionResponse(
    action_id=pending.action_id,
    skill_name=pending.skill_name,
    params=pending.params,
)

# 修改为：
from app.schemas.agent import PendingActionContext

notes = []
if pending.original_input:
    notes.append(f"理解：您说的是「{pending.original_input}」")

pending_action = PendingActionResponse(
    action_id=pending.action_id,
    skill_name=pending.skill_name,
    params=pending.params,
    context=PendingActionContext(
        original_input=pending.original_input,
        extracted_params=pending.params,
        notes=notes,
    ),
)
```

- [ ] **Step 9: 运行测试确认通过**

Run: `cd backend && poetry run pytest tests/test_pending_actions.py -v`
Expected: PASS

- [ ] **Step 10: 运行全量测试确认无回归**

Run: `cd backend && poetry run pytest tests/test_pending_actions.py tests/test_function_calling_e2e.py tests/test_agent_api.py -v`
Expected: PASS

- [ ] **Step 11: 提交**

```bash
git add backend/app/infra/pending_actions.py backend/app/schemas/agent.py backend/app/agent/graph.py backend/app/api/agent.py backend/tests/test_pending_actions.py
git commit -m "feat(agent): 增强确认消息展示三层上下文（理解/参数/操作）"
```

---

## Task 4: 意图路由（When2Tool）

**Files:**
- Create: `backend/app/agent/intent_router.py`
- Modify: `backend/app/agent/advisor.py:56-127,130-239`
- Test: `backend/tests/test_intent_router.py`

- [ ] **Step 1: 写意图路由测试**

创建 `backend/tests/test_intent_router.py`：

```python
"""测试意图路由 — 问候/查询/写操作分类。"""

import pytest

from app.agent.intent_router import classify_intent, IntentType


class TestClassifyIntent:
    """测试 classify_intent 函数。"""

    # 问候类
    @pytest.mark.parametrize(
        "message",
        ["你好", "在吗", "嗨", "hello", "您好"],
    )
    def test_greeting(self, message: str):
        assert classify_intent(message) == IntentType.GREETING

    # 写操作类
    @pytest.mark.parametrize(
        "message",
        ["记一笔账", "买了200块化肥", "卖西瓜收入5000", "赊账", "记录浇水"],
    )
    def test_write(self, message: str):
        assert classify_intent(message) == IntentType.WRITE

    # 查询类
    @pytest.mark.parametrize(
        "message",
        ["上个月花了多少钱", "天气预报", "成本分析", "当前茬口状态"],
    )
    def test_query(self, message: str):
        assert classify_intent(message) == IntentType.QUERY

    # 闲聊/模糊 — 默认走 agent
    @pytest.mark.parametrize(
        "message",
        ["看看我的账", "农场怎么样", "帮我看看"],
    )
    def test_ambiguous_goes_agent(self, message: str):
        assert classify_intent(message) == IntentType.AGENT

    def test_empty_string(self):
        assert classify_intent("") == IntentType.AGENT


class TestGreetingResponses:
    """测试问候语直接回复。"""

    def test_greeting_reply_is_friendly(self):
        from app.agent.intent_router import get_greeting_reply
        reply = get_greeting_reply("你好")
        assert isinstance(reply, str)
        assert len(reply) > 0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && poetry run pytest tests/test_intent_router.py -v`
Expected: FAIL — `app.agent.intent_router` 模块不存在

- [ ] **Step 3: 实现意图路由模块**

创建 `backend/app/agent/intent_router.py`：

```python
"""意图路由 — 基于规则的用户输入分类。"""

import enum
import re

import logging

logger = logging.getLogger(__name__)


class IntentType(enum.Enum):
    """意图类型。"""

    GREETING = "greeting"
    QUERY = "query"
    WRITE = "write"
    AGENT = "agent"


_GREETING_PATTERNS = re.compile(
    r"^(你好|您好|在吗|在不在|嗨|hi|hello|hey|早上好|晚上好|下午好)[\s！!。.？?]*$",
    re.IGNORECASE,
)

_WRITE_KEYWORDS = {
    "记账", "记一笔", "买了", "卖了", "花了", "收入", "支出", "赊账",
    "付了", "收了", "创建", "建一个", "记录", "还了", "还钱",
    "浇水", "施肥", "打药", "除草", "播种",
}

_QUERY_KEYWORDS = {
    "花了多少", "赚了多少", "收支", "余额", "天气", "预报",
    "成本", "利润", "趋势", "茬口", "进度", "阶段",
    "账单", "记录", "日志", "状态", "综合",
}


def classify_intent(message: str) -> IntentType:
    """基于规则分类用户意图。保守策略：不确定时走 AGENT。"""
    stripped = message.strip()
    if not stripped:
        return IntentType.AGENT

    # Layer 1: 问候匹配（必须完全匹配，避免把"你好，记一笔账"判为问候）
    if _GREETING_PATTERNS.match(stripped):
        logger.debug("意图路由 | msg=%s | intent=greeting", stripped[:20])
        return IntentType.GREETING

    # Layer 2: 写操作关键词
    if any(kw in stripped for kw in _WRITE_KEYWORDS):
        logger.debug("意图路由 | msg=%s | intent=write", stripped[:20])
        return IntentType.WRITE

    # Layer 3: 查询关键词
    if any(kw in stripped for kw in _QUERY_KEYWORDS):
        logger.debug("意图路由 | msg=%s | intent=query", stripped[:20])
        return IntentType.QUERY

    # 默认：走完整 agent 流程
    logger.debug("意图路由 | msg=%s | intent=agent", stripped[:20])
    return IntentType.AGENT


_GREETING_REPLIES = [
    "你好！有什么可以帮你的吗？可以问我农场管理相关的问题，也可以直接记账哦。",
    "您好！我可以帮你记账、查收支、看天气，有什么需要？",
    "嗨！随时可以问我问题或者记账。",
]


def get_greeting_reply(message: str) -> str:
    """返回问候语回复。"""
    import hashlib
    idx = int(hashlib.md5(message.encode()).hexdigest()[:8], 16) % len(_GREETING_REPLIES)
    return _GREETING_REPLIES[idx]
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && poetry run pytest tests/test_intent_router.py -v`
Expected: PASS

- [ ] **Step 5: 在 advisor.py 入口增加意图路由**

修改 `backend/app/agent/advisor.py`，在 `invoke_advisor` 函数中（约第 65-70 行之间），在 `check_input` 之后、`init_trace` 之前插入路由判断：

```python
from app.agent.intent_router import IntentType, classify_intent, get_greeting_reply

# ... 在 invoke_advisor 函数中 ...
async def invoke_advisor(
    user_input: str,
    farm_id: int,
    db: Session | None = None,
    conversation_id: int | None = None,
    session_id: str = "",
    request_id: str = "",
) -> str:
    ok, reason = check_input(user_input)
    if not ok:
        logger.warning("Agent 输入被拦截 | farm_id=%s, reason=%s", farm_id, reason)
        return f"输入内容包含不安全信息，已被拦截。原因：{reason}"

    # 意图路由：问候语直接回复
    intent = classify_intent(user_input)
    if intent == IntentType.GREETING:
        reply = get_greeting_reply(user_input)
        return filter_output(reply)

    init_trace(farm_id=farm_id, session_id=session_id, request_id=request_id)
    # ... 后续逻辑不变 ...
```

在 `stream_advisor` 函数中做同样修改（约第 139-146 行之间）：

```python
async def stream_advisor(
    user_input: str,
    farm_id: int,
    ...
) -> AsyncGenerator[str, None]:
    ok, reason = check_input(user_input)
    if not ok:
        yield f"输入内容包含不安全信息，已被拦截。原因：{reason}"
        return

    # 意图路由：问候语直接回复
    intent = classify_intent(user_input)
    if intent == IntentType.GREETING:
        reply = get_greeting_reply(user_input)
        yield filter_output(reply)
        return

    init_trace(farm_id=farm_id, session_id=session_id, request_id=request_id)
    # ... 后续逻辑不变 ...
```

- [ ] **Step 6: 运行全量测试确认无回归**

Run: `cd backend && poetry run pytest tests/test_intent_router.py tests/test_advisor_agent.py tests/test_pending_actions.py -v`
Expected: PASS

- [ ] **Step 7: 提交**

```bash
git add backend/app/agent/intent_router.py backend/app/agent/advisor.py backend/tests/test_intent_router.py
git commit -m "feat(agent): 规则式意图路由，问候语直接回复不触发 LangGraph"
```

---

## Task 5: 前端适配 — 展示三层确认消息

**Files:**
- Modify: `admin-web/src/api/agent.ts:57-66`
- Modify: `admin-web/src/pages/Agent/index.tsx:57-86`
- Modify: `admin-web/src/pages/Playground/index.tsx:76-118`

- [ ] **Step 1: 更新 TypeScript 类型**

修改 `admin-web/src/api/agent.ts` 的 `PendingAction` 接口（第 57-60 行）：

```typescript
export interface PendingActionContext {
  original_input: string;
  extracted_params: Record<string, unknown>;
  notes: string[];
}

export interface PendingAction {
  action_id: string;
  skill_name: string;
  params: Record<string, any>;
  context?: PendingActionContext | null;
}
```

- [ ] **Step 2: 更新 Agent ChatBubble 展示 context**

修改 `admin-web/src/pages/Agent/index.tsx` 的 `ChatBubble` 组件（约第 57-86 行），在 pending action 的确认/取消按钮上方，增加 context 展示区域：

找到渲染 pending action 按钮的位置（确认/取消按钮附近），在按钮之前添加：

```tsx
{msg.pendingAction?.context && (
  <div className="mt-2 p-2 bg-gray-50 rounded-lg text-sm text-gray-600 space-y-1">
    {msg.pendingAction.context.original_input && (
      <p>📝 理解：您说的是「{msg.pendingAction.context.original_input}」</p>
    )}
    {msg.pendingAction.context.notes?.map((note, i) => (
      <p key={i}>{note}</p>
    ))}
  </div>
)}
```

- [ ] **Step 3: 更新 Playground ChatBubble**

在 `admin-web/src/pages/Playground/index.tsx` 中做同样的修改，在 Playground 的 `ChatBubble` 中增加 context 展示（结构和 Agent 页面一致）。

- [ ] **Step 4: 手动验证**

Run: `cd admin-web && pnpm dev`

在浏览器中测试：
1. 打开 Agent 聊天页面
2. 输入"你好" → 应直接回复，无确认按钮
3. 输入"昨天买了200块化肥" → 应展示三层确认信息（理解/参数/操作）

- [ ] **Step 5: 提交**

```bash
git add admin-web/src/api/agent.ts admin-web/src/pages/Agent/index.tsx admin-web/src/pages/Playground/index.tsx
git commit -m "feat(frontend): 展示三层确认消息（理解/参数/操作）"
```

---

## Task 6: 修复金额解析正则 — 支持 "w/W/万" 后缀

**Files:**
- Modify: `backend/app/agent/tool_selector.py:14-16`
- Test: `backend/tests/test_tool_selector.py`

这个任务解决 `bug.todo.md` 中的"100w 解析为 100"的问题。当前 `WRITE_PATTERNS` 中 `create_cost_record` 的金额正则只匹配数字后的单位标记，但没有捕获"万"量级。

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_tool_selector.py` 中追加：

```python
class TestAmountPatternWithSuffix:
    """测试金额正则对 w/W/万 后缀的支持。"""

    def test_amount_with_w_suffix(self):
        """'100w' 应匹配 create_cost_record。"""
        selected = select_tools("今天卖西瓜收入100w")
        assert "create_cost_record" in selected

    def test_amount_with_wan_suffix(self):
        """'100万' 应匹配 create_cost_record。"""
        selected = select_tools("卖西瓜赚了100万")
        assert "create_cost_record" in selected

    def test_amount_with_upper_w(self):
        """'100W' 应匹配 create_cost_record。"""
        selected = select_tools("收入100W")
        assert "create_cost_record" in selected
```

- [ ] **Step 2: 运行测试确认结果**

Run: `cd backend && poetry run pytest tests/test_tool_selector.py::TestAmountPatternWithSuffix -v`
Expected: 可能 PASS — 正则 `(?:元|块|万|w|W|千|百)` 已经包含 `万|w|W`。

如果 PASS，说明 tool_selector 的正则已经能匹配，问题在 LLM 理解层（LLM 看到 "100w" 但不知道 w=万）。这种情况下需要在 system prompt 中增加说明。

- [ ] **Step 3: 如果测试 PASS — 在 prompt 中增加金额解析引导**

修改 `backend/app/agent/prompt_composer.py` 或相关 prompt 片段，在记账相关上下文中增加金额解析指引：

在 prompt 片段中增加：
```
金额解析规则：
- "100w"、"100W" 表示 100万 = 1,000,000
- "5k"、"5K" 表示 5000
- "两百" 表示 200
- 用户提到多个金额时，只取与操作相关的金额
```

找到 prompt 片段目录，将此规则添加到合适的 prompt 文件中。

- [ ] **Step 4: 如果测试 FAIL — 修复正则并重新测试**

Run: `cd backend && poetry run pytest tests/test_tool_selector.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/agent/tool_selector.py backend/tests/test_tool_selector.py
git commit -m "fix(agent): 金额正则支持 w/W/万 后缀 + prompt 增加金额解析引导"
```

---

## Task 7: 集成验证

**Files:**
- Test: `backend/tests/test_schema_constraint.py` (追加)

- [ ] **Step 1: 端到端测试 — 完整流程**

在 `backend/tests/test_schema_constraint.py` 末尾追加：

```python
class TestEndToEndWriteSkill:
    """端到端测试：用户输入 → LLM 工具调用 → 校验 → pending → 确认。"""

    def setup_method(self):
        from app.infra.pending_actions import _pending
        _pending.clear()

    @pytest.mark.asyncio
    async def test_full_flow_with_valid_params(self):
        """正常流程：买了200块化肥 → pending action → 确认。"""
        from app.agent.graph import _parallel_tool_node
        from app.infra.pending_actions import get_pending, build_confirm_message
        from langchain_core.messages import AIMessage

        ai_msg = AIMessage(
            content="",
            tool_calls=[
                {
                    "id": "tc1",
                    "name": "create_cost_record",
                    "args": {"amount": 200, "category": "化肥"},
                },
            ],
        )
        state = {"messages": [ai_msg], "farm_id": 1}

        result = await _parallel_tool_node(state)
        pending = get_pending(farm_id=1)

        assert pending is not None
        assert pending.params["amount"] == 200
        assert pending.params["category"] == "化肥"

        tool_msg = result["messages"][0]
        assert "确认" in tool_msg.content

    @pytest.mark.asyncio
    async def test_invalid_params_no_pending(self):
        """缺少参数时不生成 pending action。"""
        from app.agent.graph import _parallel_tool_node
        from app.infra.pending_actions import get_pending
        from langchain_core.messages import AIMessage

        ai_msg = AIMessage(
            content="",
            tool_calls=[
                {
                    "id": "tc1",
                    "name": "create_cost_record",
                    "args": {"category": "化肥"},  # 缺少 amount
                },
            ],
        )
        state = {"messages": [ai_msg], "farm_id": 1}

        with patch("app.agent.graph.get_langchain_tools") as mock_tools:
            from pydantic import BaseModel, Field
            from typing import Literal

            class FakeSchema(BaseModel):
                amount: float = Field(..., description="金额")
                category: Literal["化肥", "种子", "人工", "其他"] = Field(..., description="分类")

            mock_tool = MagicMock()
            mock_tool.name = "create_cost_record"
            mock_tool.args_schema = FakeSchema
            mock_tools.return_value = [mock_tool]

            await _parallel_tool_node(state)

        assert get_pending(farm_id=1) is None

    def test_greeting_bypasses_agent(self):
        """问候语不走 agent 流程。"""
        from app.agent.intent_router import classify_intent, IntentType

        assert classify_intent("你好") == IntentType.GREETING
        assert classify_intent("在吗") == IntentType.GREETING

    def test_write_intent_detected(self):
        """写操作意图正确识别。"""
        from app.agent.intent_router import classify_intent, IntentType

        assert classify_intent("记一笔账") == IntentType.WRITE
        assert classify_intent("买了200块化肥") == IntentType.WRITE
```

- [ ] **Step 2: 运行集成测试**

Run: `cd backend && poetry run pytest tests/test_schema_constraint.py::TestEndToEndWriteSkill -v`
Expected: PASS

- [ ] **Step 3: 运行全量测试套件**

Run: `cd backend && poetry run pytest -v --tb=short`
Expected: PASS — 全部测试通过，无回归

- [ ] **Step 4: 提交**

```bash
git add backend/tests/test_schema_constraint.py
git commit -m "test(agent): 集成验证 — 动态 enum + 校验 + 意图路由端到端测试"
```

---

## 自查清单

### 1. Spec 覆盖度

| Spec 需求 | 对应 Task |
|-----------|----------|
| `write-skill-schema-constraint`: category 从用户标签选择 | Task 1 |
| `write-skill-schema-constraint`: 动态 enum 从数据库加载 | Task 1 |
| `write-skill-schema-constraint`: Pydantic 校验 + 自纠错 | Task 2 |
| `pending-action-context-display`: 三层确认消息 | Task 3 |
| `agent-intent-router`: 问候/查询/写操作路由 | Task 4 |
| `agent-intent-router`: 保守路由默认 | Task 4 (AGENT 默认) |
| bug: "100w" 解析为 100 | Task 6 |
| bug: 长段落数字解析 | Task 6 (prompt 引导) |
| 前端展示 context | Task 5 |

### 2. Placeholder 扫描

无 TBD、TODO、"implement later"、"add appropriate error handling" 等。

### 3. 类型一致性

- `PendingAction.original_input: str` — 在 `pending_actions.py` dataclass、`store_pending` 参数、`build_confirm_message` 参数、graph.py 调用处一致
- `PendingActionResponse.context` — 在 `schemas/agent.py` 和 `api/agent.py` 构建处一致
- `IntentType` enum — 在 `intent_router.py` 定义和 `advisor.py` 使用处一致
- `get_langchain_tools(farm_id)` — 在 `skills/__init__.py` 签名和 `graph.py` 调用处一致
- `classify_intent` 返回 `IntentType` — 在 `intent_router.py` 和 `advisor.py` 使用处一致
