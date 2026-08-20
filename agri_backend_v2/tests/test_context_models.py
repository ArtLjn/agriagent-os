"""Context 数据模型契约测试。"""

from agent.domains.harness.context.models import (
    BudgetDecision,
    ContextBlock,
    ContextBlockStatus,
    ContextBundle,
    ContextSource,
    ConversationSnapshot,
    MemoryHit,
    MemoryHitStatus,
    MemoryObservation,
    ObservationStatus,
    SourceStatus,
    TokenBudget,
)


def test_conversation_snapshot_round_trip_preserves_nested_contract() -> None:
    snapshot = ConversationSnapshot(
        conversation_id="conversation-1",
        user_id="user-1",
        farm_uid="farm-uid-1",
        farm_id=12,
        scope="user:user-1/farm:farm-uid-1/conversation:conversation-1",
        conversation_revision=8,
        summary_revision=3,
        reset_generation=2,
        source=ContextSource.CONVERSATION_MESSAGES,
        source_status=SourceStatus.MONGO,
        recent_turns=[
            {"turn_id": "turn-1", "messages": [{"role": "user", "content": "你好"}]}
        ],
        summary="用户正在规划番茄种植。",
        pending_action={"type": "write_confirm", "status": "pending"},
    )

    restored = ConversationSnapshot.from_dict(snapshot.to_dict())

    assert restored == snapshot
    assert restored.revision == 8
    assert restored.to_json() == snapshot.to_json()


def test_context_bundle_json_round_trip_preserves_tenant_fields() -> None:
    bundle = ContextBundle(
        conversation_id="conversation-1",
        turn_id="turn-1",
        user_id="user-1",
        farm_uid="farm-uid-1",
        farm_id=12,
        scope="farm:farm-uid-1",
        conversation_revision=8,
        summary_revision=3,
        reset_generation=2,
        source_status=SourceStatus.MONGO,
        blocks=[
            ContextBlock(
                key="task_input",
                content="查询明天天气",
                source=ContextSource.CURRENT_TURN,
                user_id="user-1",
                farm_uid="farm-uid-1",
                farm_id=12,
                scope="farm:farm-uid-1",
                required=True,
                estimated_tokens=16,
                status=ContextBlockStatus.INCLUDED,
                source_status=SourceStatus.MONGO,
            )
        ],
        budget=TokenBudget(
            model_context_tokens=4096,
            response_reserve_tokens=512,
            safety_margin_tokens=128,
            message_tokens=100,
            used_tokens=100,
        ),
    )

    restored = ContextBundle.from_dict(bundle.to_dict())

    assert restored == bundle
    assert restored.user_id == "user-1"
    assert restored.farm_uid == "farm-uid-1"
    assert restored.farm_id == 12
    assert restored.blocks[0].scope == "farm:farm-uid-1"


def test_context_block_status_and_budget_are_serializable() -> None:
    block = ContextBlock(
        key="session_summary",
        content="窗口外历史摘要",
        source=ContextSource.CONVERSATION_STATE,
        user_id="user-1",
        farm_uid="farm-uid-1",
        status=ContextBlockStatus.COMPRESSED,
        source_status=SourceStatus.STALE,
        estimated_tokens=40,
        drop_reason="压缩到最小摘要",
    )
    budget = TokenBudget(
        model_context_tokens=1000,
        response_reserve_tokens=200,
        safety_margin_tokens=100,
        used_tokens=700,
        decision=BudgetDecision.COMPRESSED,
    )

    assert ContextBlock.from_dict(block.to_dict()) == block
    assert TokenBudget.from_dict(budget.to_dict()) == budget
    assert budget.usable_tokens == 700
    assert '"status": "compressed"' in block.to_json()
    assert '"decision": "compressed"' in budget.to_json()


def test_memory_models_keep_scope_and_status_on_round_trip() -> None:
    observation = MemoryObservation(
        observation_id="observation-1",
        user_id="user-1",
        farm_uid="farm-uid-1",
        farm_id=12,
        scope="conversation:conversation-1",
        conversation_id="conversation-1",
        turn_id="turn-1",
        status=ObservationStatus.ACCEPTED,
        source_status=SourceStatus.MONGO,
    )
    hit = MemoryHit(
        memory_id="memory-1",
        content="用户偏好使用有机肥。",
        user_id="user-1",
        farm_uid="farm-uid-1",
        farm_id=12,
        scope="farm:farm-uid-1",
        source_status=SourceStatus.MONGO,
        status=MemoryHitStatus.ACTIVE,
        revision=4,
    )

    assert MemoryObservation.from_dict(observation.to_dict()) == observation
    assert MemoryHit.from_dict(hit.to_dict()) == hit
    assert hit.to_dict()["scope"] == "farm:farm-uid-1"
