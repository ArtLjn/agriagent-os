"""Legacy 最小 Runtime Scheduler。

仅保留为 task_graph planning compile artifact 的兼容测试对象；生产调度以
PendingPlan 顺序执行为准。
"""

from __future__ import annotations

from app.agent.task_graph.models import ExecutionState, TaskGraph, TaskGraphNode

_SCHEDULABLE_STATUSES = {"created", "running"}


def next_runnable_nodes(graph: TaskGraph, state: ExecutionState) -> list[TaskGraphNode]:
    if state.status not in _SCHEDULABLE_STATUSES:
        return []

    terminal = set(state.completed_node_ids)
    terminal.update(state.failed_node_ids)
    terminal.update(state.skipped_node_ids)
    terminal.update(state.dead_node_ids)

    optional_node_ids = _optional_node_ids(graph)
    ready = [
        node
        for node in graph.nodes
        if node.node_id not in terminal
        and all(
            _dependency_satisfied(
                dependency,
                state=state,
                optional_node_ids=optional_node_ids,
            )
            for dependency in node.depends_on
        )
    ]
    ready_ids = {node.node_id for node in ready}
    return [
        node
        for node in ready
        if not any(dependency in ready_ids for dependency in node.depends_on)
    ]


def blocked_by_terminal_dependency(
    graph: TaskGraph, state: ExecutionState
) -> list[TaskGraphNode]:
    """推导因失败、跳过或 dead 依赖而不能继续的节点。"""
    blocked_dependencies = set(state.failed_node_ids)
    blocked_dependencies.update(state.dead_node_ids)
    optional_node_ids = _optional_node_ids(graph)
    blocked_dependencies.update(
        node_id
        for node_id in state.skipped_node_ids
        if node_id not in optional_node_ids
    )
    terminal = set(state.completed_node_ids)
    terminal.update(blocked_dependencies)

    blocked_nodes: list[TaskGraphNode] = []
    changed = True
    while changed:
        changed = False
        for node in graph.nodes:
            if node.node_id in terminal:
                continue
            if any(
                dependency in blocked_dependencies for dependency in node.depends_on
            ):
                blocked_nodes.append(node)
                terminal.add(node.node_id)
                blocked_dependencies.add(node.node_id)
                changed = True
    return blocked_nodes


def _dependency_satisfied(
    dependency: str,
    *,
    state: ExecutionState,
    optional_node_ids: set[str],
) -> bool:
    if dependency in state.completed_node_ids:
        return True
    return dependency in optional_node_ids and dependency in state.skipped_node_ids


def _optional_node_ids(graph: TaskGraph) -> set[str]:
    return {node.node_id for node in graph.nodes if node.optional}
