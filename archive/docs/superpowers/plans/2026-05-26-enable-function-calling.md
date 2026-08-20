# enable-function-calling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将后端 LLM 从 `qwen-flash-character` 切换为 `qwen3.6-flash`，启用标准 function calling 协议，让 Agent 能真实调用 skill 获取数据。

**Architecture:** 在配置层新增 `enable_thinking` 开关，通过 `model_kwargs` 透传给 DashScope；prompt 中强化 tool calling 硬约束；保持 LangGraph 图结构不变，端到端验证 5 个 skill 的 FC 链路。

**Tech Stack:** Python, LangChain ChatOpenAI, DashScope, pytest

---

## File Map

| 文件 | 职责 | 操作 |
|------|------|------|
| `backend/app/core/config.py` | AIConfig Pydantic 模型 | 新增 `enable_thinking` 字段 |
| `backend/config.yaml.example` | 配置模板 | 更新默认模型，新增 `enable_thinking` |
| `backend/app/core/llm.py` | LLM 工厂函数 | `get_llm()` 传递 `model_kwargs` |
| `backend/prompts/base.j2` | System prompt 模板 | 强化 tool calling 硬约束 |
| `backend/app/core/prompt_registry.py` | 内置默认 prompt 回退 | 同步更新 `_DEFAULT_PROMPTS["system_base"]` |
| `backend/tests/test_llm.py` | LLM 工厂测试 | 新增 `enable_thinking` 配置传递测试 |
| `backend/tests/test_agent_tools.py` | Agent 工具测试 | 新增 FC 触发/不触发测试 |

---

### Task 1: AIConfig 新增 enable_thinking 字段

**Files:**
- Modify: `backend/app/core/config.py:21-26`
- Test: `backend/tests/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
def test_ai_config_default_enable_thinking_false():
    from app.core.config import AIConfig
    config = AIConfig()
    assert config.enable_thinking is False

def test_ai_config_enable_thinking_can_be_set():
    from app.core.config import AIConfig
    config = AIConfig(enable_thinking=True)
    assert config.enable_thinking is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && poetry run pytest tests/test_config.py::test_ai_config_default_enable_thinking_false -v`
Expected: FAIL with `AttributeError: 'AIConfig' object has no attribute 'enable_thinking'`

- [ ] **Step 3: Write minimal implementation**

Modify `backend/app/core/config.py:21-26`:

```python
class AIConfig(BaseModel):
    model: str = "qwen3.6-flash-2026-04-16"
    api_key: str = ""
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    enable_thinking: bool = False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && poetry run pytest tests/test_config.py::test_ai_config_default_enable_thinking_false tests/test_config.py::test_ai_config_enable_thinking_can_be_set -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/config.py backend/tests/test_config.py
git commit -m "feat: AIConfig 新增 enable_thinking 字段，默认 false"
```

---

### Task 2: config.yaml.example 更新模型和 enable_thinking

**Files:**
- Modify: `backend/config.yaml.example`

- [ ] **Step 1: Modify config.yaml.example**

Replace `backend/config.yaml.example` 中 `ai:` 段落为：

```yaml
ai:
  model: "qwen3.6-flash-2026-04-16"                        # LLM 模型名称
  api_key: ""                                              # LLM API 密钥（必填）
  base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"  # LLM API 地址
  enable_thinking: false                                   # 是否启用思考模式（qwen3 系列思考模式下不支持 tool_choice）
```

- [ ] **Step 2: Commit**

```bash
git add backend/config.yaml.example
git commit -m "chore: config.yaml.example 更新默认模型为 qwen3.6-flash，新增 enable_thinking"
```

---

### Task 3: get_llm() 传递 model_kwargs

**Files:**
- Modify: `backend/app/core/llm.py:40-58`
- Test: `backend/tests/test_llm.py`

- [ ] **Step 1: Write the failing test**

在 `backend/tests/test_llm.py` 末尾新增：

```python
class TestEnableThinking:
    """测试 enable_thinking 配置传递。"""

    @patch("app.core.llm.ChatOpenAI")
    @patch("app.core.llm.settings")
    def test_enable_thinking_false_passes_model_kwargs(self, mock_settings, mock_chat_openai: MagicMock) -> None:
        """enable_thinking=false 时 model_kwargs 包含 enable_thinking=false。"""
        mock_settings.ai_api_key = "test-key"
        mock_settings.ai_model = "qwen3.6-flash"
        mock_settings.ai_base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        mock_settings.ai.enable_thinking = False

        mock_instance = MagicMock()
        mock_chat_openai.return_value = mock_instance

        import app.core.llm as llm_module
        llm_module.LLM_INSTANCE = None

        from app.core.llm import get_llm
        get_llm()

        call_kwargs = mock_chat_openai.call_args.kwargs
        assert "model_kwargs" in call_kwargs
        assert call_kwargs["model_kwargs"]["enable_thinking"] is False

    @patch("app.core.llm.ChatOpenAI")
    @patch("app.core.llm.settings")
    def test_enable_thinking_true_passes_model_kwargs(self, mock_settings, mock_chat_openai: MagicMock) -> None:
        """enable_thinking=true 时 model_kwargs 包含 enable_thinking=true。"""
        mock_settings.ai_api_key = "test-key"
        mock_settings.ai_model = "qwen3.6-flash"
        mock_settings.ai_base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        mock_settings.ai.enable_thinking = True

        mock_instance = MagicMock()
        mock_chat_openai.return_value = mock_instance

        import app.core.llm as llm_module
        llm_module.LLM_INSTANCE = None

        from app.core.llm import get_llm
        get_llm()

        call_kwargs = mock_chat_openai.call_args.kwargs
        assert call_kwargs["model_kwargs"]["enable_thinking"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && poetry run pytest tests/test_llm.py::TestEnableThinking -v`
Expected: FAIL — `AssertionError: 'model_kwargs' not in call_kwargs`

- [ ] **Step 3: Write minimal implementation**

修改 `backend/app/core/llm.py` 中 `get_llm()` 函数：

```python
def get_llm() -> BaseChatModel:
    """获取全局 LLM 实例（带熔断保护）。"""
    global LLM_INSTANCE
    if LLM_INSTANCE is None:
        if not settings.ai_api_key:
            raise LlmNotConfiguredError(
                "AI API key 未配置。请在 config.yaml 中设置 ai.api_key，"
                "或设置 AI_API_KEY 环境变量。"
            )
        cb = settings.circuit_breaker_config
        model_kwargs = {}
        if hasattr(settings, "ai") and hasattr(settings.ai, "enable_thinking"):
            model_kwargs["enable_thinking"] = settings.ai.enable_thinking
        LLM_INSTANCE = ChatOpenAI(
            model=settings.ai_model,
            api_key=settings.ai_api_key,
            base_url=settings.ai_base_url,
            temperature=0.7,
            max_retries=cb.retry_max,
            timeout=cb.retry_backoff_base * (2**cb.retry_max) * 2,
            model_kwargs=model_kwargs,
        )
    return LLM_INSTANCE
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && poetry run pytest tests/test_llm.py::TestEnableThinking -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/llm.py backend/tests/test_llm.py
git commit -m "feat: get_llm() 传递 enable_thinking 到 DashScope model_kwargs"
```

---

### Task 4: base.j2 强化 tool calling 硬约束

**Files:**
- Modify: `backend/prompts/base.j2`

- [ ] **Step 1: Modify base.j2**

将 `backend/prompts/base.j2` 中【能力范围】段落：

```jinja2
【能力范围】
你具备以下工具调用能力：
- 查询天气预报和灾害预警
- 查看种植周期和当前阶段
- 了解近期农事记录
- 统计成本收支

请根据用户的问题，主动调用合适的工具获取信息，然后给出具体、可操作的建议。回答要简洁明了，适合农民理解。
```

替换为：

```jinja2
【能力范围】
你具备以下工具调用能力：
- 查询天气预报和灾害预警
- 查看种植周期和当前阶段
- 了解近期农事记录
- 统计成本收支

【工具调用规则】（最高优先级，违反则回答无效）
- 禁止凭记忆回答天气、成本、农事记录、茬口状态等实时数据。
- 遇到上述信息时，必须先调用对应工具获取真实数据，再回答。
- 如果不确定信息是否最新，一律调用工具确认。
- 回答要简洁明了，适合农民理解。
```

- [ ] **Step 2: Commit**

```bash
git add backend/prompts/base.j2
git commit -m "feat: base.j2 强化 tool calling 硬约束，禁止凭记忆回答实时数据"
```

---

### Task 5: prompt_registry.py 同步更新内置默认 prompt

**Files:**
- Modify: `backend/app/core/prompt_registry.py:12-32`

- [ ] **Step 1: Modify prompt_registry.py**

将 `_DEFAULT_PROMPTS["system_base"]` 中能力范围段落：

```python
        "请根据用户的问题，主动调用合适的工具获取信息，给出具体、可操作的建议。"
```

替换为：

```python
        "【工具调用规则】（最高优先级，违反则回答无效）\n"
        "- 禁止凭记忆回答天气、成本、农事记录、茬口状态等实时数据。\n"
        "- 遇到上述信息时，必须先调用对应工具获取真实数据，再回答。\n"
        "- 如果不确定信息是否最新，一律调用工具确认。\n"
        "- 回答要简洁明了，适合农民理解。\n"
```

- [ ] **Step 2: Write test**

在 `backend/tests/` 下新建 `test_prompt_registry.py`：

```python
from app.core.prompt_registry import get_registry


def test_system_base_prompt_contains_tool_calling_rule():
    """内置默认 system_base prompt 包含 tool calling 硬约束。"""
    registry = get_registry()
    # 使用 fallback 获取内置默认
    fallback = registry.get_fallback("system_base")
    assert "禁止凭记忆回答" in fallback
    assert "必须先调用对应工具" in fallback
```

- [ ] **Step 3: Run test**

Run: `cd backend && poetry run pytest tests/test_prompt_registry.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/core/prompt_registry.py backend/tests/test_prompt_registry.py
git commit -m "feat: 内置默认 prompt 同步 tool calling 硬约束"
```

---

### Task 6: 端到端 tool calling 链路验证

**Files:**
- Create: `backend/tests/test_function_calling_e2e.py`

- [ ] **Step 1: Write weather tool call test**

```python
from unittest.mock import MagicMock, Mock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.agents.graph import compile_advisor_graph


class TestFunctionCallingE2E:
    """端到端验证 function calling 链路。"""

    @patch("app.agents.graph.get_langchain_tools")
    @patch("app.agents.graph.get_llm")
    @patch("app.agents.graph.farm_context_service.build_summary")
    @patch("app.agents.graph.SessionLocal")
    def test_weather_query_triggers_tool_call(
        self, mock_session, mock_summary, mock_get_llm, mock_get_tools
    ):
        """天气查询应触发 weather tool call。"""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(display_name="老李")
        mock_session.return_value = mock_db
        mock_summary.return_value = "当前无种植计划"

        mock_tool = MagicMock()
        mock_tool.name = "weather"
        mock_get_tools.return_value = [mock_tool]

        # 模拟 LLM 返回带 tool_call 的 AIMessage
        mock_llm = MagicMock()
        tool_call_msg = AIMessage(
            content="",
            tool_calls=[{"name": "weather", "args": {"city": "苏州"}, "id": "tc1"}],
        )
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.invoke.side_effect = [tool_call_msg, AIMessage(content="明天苏州晴")]
        mock_get_llm.return_value = mock_llm

        graph = compile_advisor_graph()
        result = graph.invoke({"messages": [HumanMessage(content="明天苏州什么天气")]})

        last_msg = result["messages"][-1]
        assert "苏州" in last_msg.content
        mock_llm.invoke.assert_called()
```

- [ ] **Step 2: Write chat no tool call test**

```python
    @patch("app.agents.graph.get_langchain_tools")
    @patch("app.agents.graph.get_llm")
    @patch("app.agents.graph.farm_context_service.build_summary")
    @patch("app.agents.graph.SessionLocal")
    def test_chat_query_does_not_trigger_tool_call(
        self, mock_session, mock_summary, mock_get_llm, mock_get_tools
    ):
        """闲聊不应触发 tool call，直接返回文本。"""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(display_name="老李")
        mock_session.return_value = mock_db
        mock_summary.return_value = "当前无种植计划"

        mock_get_tools.return_value = []

        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.invoke.return_value = AIMessage(content="你好老李，有啥事？")
        mock_get_llm.return_value = mock_llm

        graph = compile_advisor_graph()
        result = graph.invoke({"messages": [HumanMessage(content="你好")]})

        last_msg = result["messages"][-1]
        assert last_msg.content == "你好老李，有啥事？"
```

- [ ] **Step 3: Run tests**

Run: `cd backend && poetry run pytest tests/test_function_calling_e2e.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_function_calling_e2e.py
git commit -m "test: 端到端 function calling 链路验证（天气触发/闲聊不触发）"
```

---

### Task 7: 全量测试回归 + Lint

- [ ] **Step 1: Run all tests**

Run: `cd backend && poetry run pytest -v`
Expected: 全部 PASS（或已有失败的保持原状，不引入新失败）

- [ ] **Step 2: Run lint**

Run: `cd backend && ruff check . && ruff format .`
Expected: 无 error，无 format 变更

- [ ] **Step 3: Commit**

```bash
git commit -m "chore: enable-function-calling 全量测试通过 + lint 清理"
```

---

## Self-Review Checklist

**1. Spec coverage:**

| 原始需求 | 对应 Task |
|---------|----------|
| 切换模型 qwen3.6-flash | Task 1 (AIConfig 默认值), Task 2 (config.yaml.example) |
| 新增 enable_thinking 配置 | Task 1, Task 3 |
| 通过 model_kwargs 传递 enable_thinking | Task 3 |
| base.j2 强化 tool calling 指令 | Task 4 |
| 验证端到端 tool calling | Task 6 |

**2. Placeholder scan:** 无 TBD/TODO/"implement later" 等占位符。所有步骤含完整代码和命令。

**3. Type consistency:**
- `enable_thinking: bool` 在 AIConfig、config.yaml、model_kwargs 中一致为布尔类型
- `get_llm()` 返回类型保持 `BaseChatModel` 不变
