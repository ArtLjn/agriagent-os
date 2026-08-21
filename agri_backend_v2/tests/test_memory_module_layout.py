"""Memory 目录职责拆分和注入策略的回归测试。"""

from agent.domains.harness.context.builder import build_context_bundle
from agent.domains.harness.memory import long_term, models, policy, service, short_term


def test_service_keeps_stable_facade_for_existing_callers() -> None:
    """旧入口必须指向拆分后的实现，避免调用方重新持有存储细节。"""
    assert service.get_session_view is short_term.get_session_view
    assert service.persist_session_turn is short_term.persist_session_turn
    assert service.observe is long_term.observe
    assert service.search is long_term.search
    assert service.resolve_memory_policy is policy.resolve_memory_policy


def test_memory_models_keep_tenant_scope_explicit() -> None:
    scope = models.MemoryScope(
        user_id="user-1",
        farm_id=7,
        scope="farm",
        domain="planting",
    )

    assert scope.as_dict() == {
        "user_id": "user-1",
        "farm_id": 7,
        "scope": "farm",
        "domain": "planting",
    }


def test_long_term_memory_requires_explicit_policy_trigger() -> None:
    default = policy.resolve_memory_policy()
    dependency = policy.resolve_memory_policy(
        context_dependencies=("session_summary", "long_term_memory")
    )

    assert default.include_short_term is True
    assert default.include_long_term is False
    assert dependency.include_long_term is True
    assert dependency.long_term_reason == "skill_dependency"


def test_context_builder_uses_memory_policy_dependency() -> None:
    bundle = build_context_bundle(
        "查询我的农场偏好",
        {
            "conversation_id": "conversation-1",
            "user_id": "user-1",
            "farm_id": 7,
            "memory_hits": [{"content": "偏好有机种植"}],
        },
        context_dependencies=["long_term_memory"],
    )

    assert any(block.key == "memory_hits" for block in bundle.blocks)
