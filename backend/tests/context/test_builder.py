"""Context Builder 集成测试。"""

from app.context.builder import ContextBuilder
from app.context.models import ContextBlock
from app.context.policy import ContextBuildRequest, ContextPolicy
from app.memory.models import MemoryContext, MemoryMessage


class StaticSelector:
    def __init__(self, block: ContextBlock) -> None:
        self.block = block

    def select(self, **_kwargs) -> list[ContextBlock]:
        return [self.block]


class FakeCollector:
    def __init__(self) -> None:
        self.records: list[dict] = []

    def record(self, **kwargs) -> None:
        self.records.append(kwargs)


def test_builder_builds_bundle_and_records_trace(db_session) -> None:
    collector = FakeCollector()
    builder = ContextBuilder(
        selectors=[
            StaticSelector(
                ContextBlock(
                    key="farm",
                    source="farm",
                    purpose="农场状态",
                    content="农场：默认农场",
                    priority=90,
                    token_estimate=8,
                    required=True,
                )
            ),
            StaticSelector(
                ContextBlock(
                    key="retrieval",
                    source="retrieval",
                    purpose="检索结果",
                    content="检索内容" * 200,
                    priority=10,
                    token_estimate=100,
                    compressible=True,
                    min_tokens=20,
                )
            ),
        ],
        max_tokens=40,
        trace_collector=collector,
    )

    bundle = builder.build(db=db_session, farm_id=1, user_id="test-user-001")

    assert bundle.token_estimate <= 40
    assert bundle.blocks[0].key == "farm"
    assert collector.records[0]["node_type"] == "context_build"
    assert collector.records[0]["node_name"] == "context_bundle"
    assert (
        collector.records[0]["output_data"]["token_estimate"] == bundle.token_estimate
    )
    assert collector.records[0]["output_data"]["blocks"][0]["key"] == "farm"


def test_builder_legacy_farm_context_adapter_returns_runtime_shape(db_session) -> None:
    builder = ContextBuilder(max_tokens=256)

    farm_context = builder.build_farm_runtime_context(
        db=db_session,
        farm_id=1,
    )

    assert set(farm_context) == {
        "farm_location",
        "farm_coords",
        "display_name",
        "active_crops",
        "assistant_role",
        "assistant_role_prompt",
    }
    assert farm_context["display_name"] == "测试用户"


def test_builder_builds_runtime_context_bundle_with_policy_and_memory(
    db_session,
) -> None:
    memory_context = MemoryContext(
        user_id="test-user-001",
        farm_id=1,
        session_id="session-1",
        recent_messages=[MemoryMessage(role="user", content="后天呢")],
    )
    builder = ContextBuilder(policy=ContextPolicy(), max_tokens=256)

    bundle = builder.build_runtime_context_bundle(
        db=db_session,
        request=ContextBuildRequest(
            intent="query",
            selected_tool_names=["manage_cost"],
            farm_id=1,
            user_id="test-user-001",
            session_id="session-1",
        ),
        memory_context=memory_context,
    )

    block_keys = {block.key for block in bundle.blocks}
    assert {
        "farm",
        "user_settings",
        "cycle",
        "ledger",
        "short_term_recent",
    }.issubset(block_keys)
    assert bundle.metadata["policy"]["intent"] == "query"
    assert bundle.metadata["policy"]["selected_tool_names"] == ["manage_cost"]


def test_builder_trace_records_skill_dependency_context_status(db_session) -> None:
    collector = FakeCollector()
    builder = ContextBuilder(policy=ContextPolicy(), trace_collector=collector)

    bundle = builder.build_runtime_context_bundle(
        db=db_session,
        request=ContextBuildRequest(
            intent="agent",
            selected_tool_names=["settle_labor_payment"],
            farm_id=1,
            user_id="test-user-001",
        ),
    )

    diagnostics = bundle.metadata["context_dependency_diagnostics"]
    statuses = {item["block_key"]: item["status"] for item in diagnostics}
    assert statuses["workers"] in {"selected", "unavailable"}
    assert statuses["unpaid_labor"] in {"selected", "unavailable"}
    trace_output = collector.records[0]["output_data"]
    assert "context_dependency_diagnostics" in trace_output
    dependency_blocks = [
        block
        for block in trace_output["blocks"]
        if block["selected_by_skill_dependencies"]
    ]
    assert dependency_blocks
