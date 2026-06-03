"""Agent Runtime 架构边界测试。"""

from pathlib import Path


def test_agent_graph_is_compatibility_facade():
    """graph.py 保持薄兼容入口，真实实现位于 runtime。"""
    import app.agent.graph as graph
    import app.agent.runtime.graph_factory as graph_factory
    import app.agent.runtime.nodes as nodes
    import app.agent.runtime.tool_executor as tool_executor

    assert graph.compile_advisor_graph is graph_factory.compile_advisor_graph
    assert graph._llm_node is nodes._llm_node
    assert graph._parallel_tool_node is tool_executor._parallel_tool_node


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
