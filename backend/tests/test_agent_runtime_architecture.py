"""Agent Runtime 架构边界测试。"""

import ast
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage


def test_agent_graph_is_compatibility_facade():
    """graph.py 保持薄兼容入口，真实实现位于 runtime。"""
    import app.agent.graph as graph
    import app.agent.runtime.graph_factory as graph_factory
    import app.agent.runtime.nodes as nodes
    import app.agent.runtime.tool_executor as tool_executor

    assert graph.compile_advisor_graph is graph_factory.compile_advisor_graph
    assert graph._llm_node is nodes._llm_node
    assert graph._parallel_tool_node is tool_executor._parallel_tool_node


def test_agent_state_exposes_prepared_runtime_inputs():
    """Runtime state 暴露 Application 预构建输入口。"""
    from app.agent.runtime.state import AgentState

    annotations = AgentState.__annotations__

    assert "system_prompt" in annotations
    assert "context_bundle" in annotations
    assert "selected_tool_names" in annotations


def test_legacy_agent_entrypoints_do_not_duplicate_pending_execution():
    """兼容入口只能委托 pending action executor，不能保留执行逻辑。"""
    app_dir = Path(__file__).resolve().parents[1] / "app"
    guarded_files = [
        app_dir / "services" / "agent_service.py",
        app_dir / "agent" / "advisor.py",
    ]
    forbidden_function_names = {
        "_execute_pending_action",
        "_execute_advisor_pending_action",
    }

    violations = []
    for file_path in guarded_files:
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
        relative_path = file_path.relative_to(app_dir)
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef):
                if node.name in forbidden_function_names:
                    violations.append(f"{relative_path}: defines {node.name}")
            if not isinstance(node, ast.Call):
                continue
            if (
                isinstance(node.func, ast.Name)
                and node.func.id in forbidden_function_names
            ):
                violations.append(f"{relative_path}: calls {node.func.id}")
            if _is_manager_execute_pending_skill(node):
                violations.append(f"{relative_path}: executes pending.skill_name")
            if _is_get_langchain_tools_with_farm_id(node):
                violations.append(f"{relative_path}: calls get_langchain_tools")

    assert violations == []


def _is_manager_execute_pending_skill(node: ast.Call) -> bool:
    if not isinstance(node.func, ast.Attribute) or node.func.attr != "execute":
        return False
    if not isinstance(node.func.value, ast.Name) or node.func.value.id != "manager":
        return False
    if not node.args or not isinstance(node.args[0], ast.Attribute):
        return False
    first_arg = node.args[0]
    return (
        first_arg.attr == "skill_name"
        and isinstance(first_arg.value, ast.Name)
        and first_arg.value.id == "pending"
    )


def _is_get_langchain_tools_with_farm_id(node: ast.Call) -> bool:
    if not isinstance(node.func, ast.Name) or node.func.id != "get_langchain_tools":
        return False
    return any(keyword.arg == "farm_id" for keyword in node.keywords)


def test_agent_application_does_not_import_legacy_chat_orchestration():
    """Agent Application 不应依赖旧 service 聊天编排入口。"""
    app_dir = Path(__file__).resolve().parents[1] / "app"
    application_dir = app_dir / "agent" / "application"
    forbidden_names = {"chat_with_agent", "stream_chat_with_agent"}

    violations = []
    for file_path in application_dir.rglob("*.py"):
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
        service_aliases = set()
        for node in ast.walk(tree):
            relative_path = file_path.relative_to(app_dir)
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "app.services.agent_service":
                        service_aliases.add(alias.asname or "app")
            elif isinstance(node, ast.ImportFrom):
                if node.module == "app.services.agent_service":
                    imported_names = {alias.name for alias in node.names}
                    forbidden_imports = sorted(imported_names & forbidden_names)
                    if forbidden_imports:
                        violations.append(
                            f"{relative_path}: {', '.join(forbidden_imports)}"
                        )
                elif node.module == "app.services":
                    for alias in node.names:
                        if alias.name == "agent_service":
                            service_aliases.add(alias.asname or alias.name)
            elif _uses_legacy_chat_service_attribute(node, service_aliases):
                violations.append(f"{relative_path}: uses legacy chat service")

    assert violations == []


def test_reflection_logic_lives_in_reflector_boundary():
    """Runtime/Executor 只调用 Reflection 服务，不内联核心策略与检查。"""
    app_dir = Path(__file__).resolve().parents[1] / "app"
    guarded_files = [
        *sorted((app_dir / "agent" / "runtime").rglob("*.py")),
        *sorted((app_dir / "agent" / "executor").rglob("*.py")),
    ]
    forbidden_definitions = {
        "ReflectionIssue",
        "ReflectionResult",
        "ReflectionPolicy",
        "ReflectionTrigger",
        "ReflectionDecision",
        "ReflectionSeverity",
        "ReflectorService",
        "check_write_plan_consistency",
        "check_pending_plan_consistency",
        "check_tool_failure_success_reply",
        "check_required_tool_missing",
        "check_tool_result_final_contradiction",
    }
    forbidden_modules = {
        "app.agent.reflector.checks",
        "app.agent.reflector.policy",
    }
    forbidden_submodule_aliases = {"checks", "policy"}

    violations = []
    for file_path in guarded_files:
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
        relative_path = file_path.relative_to(app_dir)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
                if node.name in forbidden_definitions:
                    violations.append(f"{relative_path}: defines {node.name}")
            elif isinstance(node, ast.ImportFrom):
                if _is_forbidden_reflector_module(node.module or "", forbidden_modules):
                    violations.append(f"{relative_path}: imports {node.module}")
                elif _imports_reflector_submodule(node, forbidden_submodule_aliases):
                    imported = ", ".join(alias.name for alias in node.names)
                    violations.append(f"{relative_path}: imports {imported}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if _is_forbidden_reflector_module(alias.name, forbidden_modules):
                        violations.append(f"{relative_path}: imports {alias.name}")

    assert violations == []


def _is_forbidden_reflector_module(module: str, forbidden_modules: set[str]) -> bool:
    return (
        module in forbidden_modules
        or module
        in {
            "reflector.checks",
            "reflector.policy",
        }
        or module.endswith((".reflector.checks", ".reflector.policy"))
    )


def _imports_reflector_submodule(
    node: ast.ImportFrom,
    forbidden_names: set[str],
) -> bool:
    module = node.module or ""
    if module == "app.agent.reflector":
        return any(alias.name in forbidden_names for alias in node.names)
    return (module == "reflector" or module.endswith(".reflector")) and any(
        alias.name in forbidden_names for alias in node.names
    )


def _uses_legacy_chat_service_attribute(
    node: ast.AST,
    service_aliases: set[str],
) -> bool:
    if not isinstance(node, ast.Attribute):
        return False
    if node.attr not in {"chat_with_agent", "stream_chat_with_agent"}:
        return False
    path = _attribute_path(node)
    if path in {
        "app.services.agent_service.chat_with_agent",
        "app.services.agent_service.stream_chat_with_agent",
    }:
        return True
    if isinstance(node.value, ast.Name):
        return node.value.id in service_aliases
    return False


def _attribute_path(node: ast.AST) -> str:
    parts = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    return ".".join(reversed(parts))


@pytest.mark.asyncio
async def test_llm_node_consumes_prepared_runtime_inputs():
    """prepared 输入优先于 Runtime 内部 prompt/context/tools 选择。"""
    from app.agent.runtime.nodes import _llm_node
    from app.context.models import ContextBlock, ContextBundle

    weather_tool = MagicMock()
    weather_tool.name = "get_weather_forecast"
    status_tool = MagicMock()
    status_tool.name = "get_farm_status"

    prepared_context = ContextBundle(
        blocks=[
            ContextBlock(
                key="prepared",
                source="application",
                purpose="test",
                content="预构建上下文",
                priority=1,
            )
        ],
        token_budget=100,
        token_estimate=10,
    )
    llm = AsyncMock()
    llm.model_name = "test-model"
    llm.bind_tools = MagicMock(return_value=llm)
    llm.ainvoke = AsyncMock(return_value=AIMessage(content="准备好了", tool_calls=[]))

    with (
        patch("app.agent.runtime.nodes.check_quota", return_value=True),
        patch(
            "app.agent.runtime.nodes.get_langchain_tools",
            return_value=[weather_tool, status_tool],
        ),
        patch(
            "app.agent.runtime.nodes.select_tools",
            return_value=["get_farm_status"],
        ),
        patch("app.agent.runtime.nodes.expand_by_chain") as mock_expand,
        patch("app.agent.runtime.nodes.get_llm", return_value=llm),
        patch("app.agent.runtime.nodes._build_circuit_key", return_value="test/model"),
        patch("app.agent.runtime.nodes._record_llm_success"),
        patch("app.agent.runtime.nodes._record_llm_failure"),
        patch(
            "app.agent.runtime.nodes._get_runtime_context_bundle",
            new_callable=AsyncMock,
        ) as mock_runtime_context,
        patch(
            "app.agent.runtime.nodes._get_farm_context",
            new_callable=AsyncMock,
            return_value={
                "display_name": "农友",
                "farm_location": "睢宁",
                "farm_coords": "",
                "active_crops": "",
            },
        ) as mock_farm_context,
        patch("app.agent.runtime.nodes.get_prompt_cache") as mock_prompt_cache,
        patch("app.agent.runtime.nodes.get_composer") as mock_composer,
        patch("app.agent.runtime.nodes.increment_round", return_value=1),
        patch("app.agent.runtime.nodes.get_collector", return_value=MagicMock()),
        patch(
            "app.agent.runtime.nodes.sliding_window_compact",
            side_effect=lambda messages: messages,
        ),
        patch("app.agent.runtime.nodes._warm_tool_caches", new_callable=AsyncMock),
        patch("app.agent.runtime.nodes.settings") as mock_settings,
    ):
        mock_settings.ai.parallel_tool_calls = False
        mock_settings.ai.failover_max_retries = 1

        await _llm_node(
            {
                "messages": [
                    HumanMessage(content="继续"),
                    ToolMessage(content="已有工具结果", tool_call_id="tool-1"),
                ],
                "farm_id": 1,
                "farm_uid": "farm-uid-1",
                "intent": "agent",
                "user_id": "user-1",
                "session_id": "sess-1",
                "system_prompt": "预构建系统提示",
                "context_bundle": prepared_context,
                "selected_tool_names": ["get_weather_forecast"],
            }
        )

    llm.bind_tools.assert_called_once_with([weather_tool])
    mock_expand.assert_not_called()
    mock_runtime_context.assert_not_awaited()
    mock_farm_context.assert_awaited_once_with(1)
    mock_prompt_cache.assert_not_called()
    mock_composer.assert_not_called()
    rendered_messages = llm.ainvoke.await_args.args[0]
    assert rendered_messages[0].content.startswith("预构建系统提示")
    assert "预构建上下文" in rendered_messages[0].content


def test_agent_runtime_modules_are_within_size_limit():
    """Runtime 关键文件遵守项目单文件大小约束。"""
    runtime_dir = Path(__file__).resolve().parents[1] / "app" / "agent" / "runtime"
    files = [
        runtime_dir / "graph_factory.py",
        runtime_dir / "nodes.py",
        runtime_dir / "tool_executor.py",
        runtime_dir / "llm_support.py",
        runtime_dir / "messages.py",
    ]

    for file_path in files:
        line_count = len(file_path.read_text(encoding="utf-8").splitlines())
        assert line_count <= 500, f"{file_path.name} has {line_count} lines"


def test_current_architecture_has_no_empty_placeholder_directories():
    """当前代码树不应为了贴合设计保留空壳目录。"""
    app_dir = Path(__file__).resolve().parents[1] / "app"
    directories = [
        "bootstrap",
        "core",
        "modules/auth",
        "modules/farm",
        "agent/application",
        "agent/runtime",
        "agent/planner",
        "agent/executor",
        "agent/response",
        "agent/guardrails",
        "agent/sessions",
        "prompt",
        "context/selectors",
        "context/compressors",
        "memory/short_term",
        "memory/long_term",
        "memory/retrieval",
        "memory/consolidation",
        "evaluation/cases",
        "evaluation/runners",
        "evaluation/replay",
        "evaluation/metrics",
        "evaluation/reports",
        "evaluation/baselines",
        "observability",
        "infra",
    ]

    missing = [
        directory for directory in directories if not (app_dir / directory).is_dir()
    ]

    assert missing == []

    placeholder_dirs = []
    for directory in app_dir.rglob("*"):
        if not directory.is_dir() or directory.name == "__pycache__":
            continue
        files = [file for file in directory.iterdir() if file.is_file()]
        dirs = [
            child
            for child in directory.iterdir()
            if child.is_dir() and child.name != "__pycache__"
        ]
        if files and all(file.name == "__init__.py" for file in files) and not dirs:
            placeholder_dirs.append(directory.relative_to(app_dir).as_posix())

    assert placeholder_dirs == []


def test_guardrails_package_keeps_legacy_import_contract():
    """guardrails 迁为目录后仍保留旧导入语义。"""
    from app.agent.guardrails import check_input, filter_output

    assert check_input("今天浇水了吗") == (True, None)
    assert filter_output("手机号 13800000000") == "手机号 [手机号已隐藏]"


def test_agent_platform_subdomains_expose_domain_models():
    """Planner/Executor/Response/Sessions 暴露可演进的边界模型。"""
    from app.agent.executor import build_tool_execution_plan
    from app.agent.response import ResponseEvent, format_sse_event
    from app.agent.sessions import PendingActionSnapshot, TemporaryTaskState

    write_plan = build_tool_execution_plan("create_cost_record", {"amount": 10})
    read_plan = build_tool_execution_plan("get_farm_status", {})

    assert write_plan.permission_level == "write"
    assert write_plan.requires_confirmation is True
    assert read_plan.permission_level == "read"
    assert read_plan.requires_confirmation is False
    assert format_sse_event(ResponseEvent(type="content", payload={"content": "好"}))
    assert PendingActionSnapshot(action_id="act-1", name="create_cost")
    assert TemporaryTaskState(task_id="task-1", status="pending")
