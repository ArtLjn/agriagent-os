"""Context 架构端到端验收套件。"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy.orm import sessionmaker

import app.context.policy as policy_module
from app.application.chat.task_state_updater import (
    TaskStateTurn,
    update_task_state_after_turn,
)
from app.context.builder import ContextBuilder
from app.context.models import ContextBlock, ContextBundle
from app.context.policy import ContextBuildRequest, ContextPolicy
from app.context.rag_provider import RAGKnowledgeProvider
from app.context.renderer import ContextRenderer
from app.context.selectors.knowledge import KnowledgeSelector
from app.infra.quillrag_client import QuillRAGDocument, QuillRAGRetrieveResult
from app.memory.explicit import ExplicitMemoryTurn, record_explicit_memory_after_turn
from app.memory.long_term.store import SQLLongTermMemoryStore
from app.memory.service import InMemoryMemoryService
from app.shared.config import RAGServiceConfig


USER_ID = "test-user-001"
FARM_ID = 1
RAG_PLACEHOLDER_KEY = "placeholder-acceptance-rag-key"
RAG_SECRET_MARKER = "rag-secret-should-not-leak"
RAG_RAW_CHUNK = "黄瓜霜霉病原始 RAG chunk 全文不应进入 trace。" * 30


class RecordingCollector:
    """收集 ContextBuilder trace 记录。"""

    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    def record(self, **kwargs: Any) -> None:
        self.records.append(kwargs)


class FakeRAGClient:
    """替代真实 RAG HTTP client 的可观测 fake。"""

    calls: list[dict[str, Any]] = []

    def retrieve(self, **kwargs: Any) -> QuillRAGRetrieveResult:
        self.calls.append(kwargs)
        return QuillRAGRetrieveResult(
            ok=True,
            actual_mode="hybrid",
            warning="fake_provider",
            results=[
                QuillRAGDocument(
                    content=RAG_RAW_CHUNK,
                    score=0.94,
                    doc_id="cucumber-disease-guide",
                    chunk_index=7,
                    metadata={
                        "source": "fake-guide.md",
                        "title": "黄瓜病害防治",
                        "api_key": RAG_SECRET_MARKER,
                        "raw_chunk": RAG_RAW_CHUNK,
                    },
                )
            ],
        )


class AcceptanceKnowledgeSelector(KnowledgeSelector):
    """让 Runtime policy 触发真实 selector 逻辑，但只使用 fake RAG client。"""

    def __init__(self) -> None:
        super().__init__(
            provider=RAGKnowledgeProvider(
                client=FakeRAGClient(),
                config=RAGServiceConfig(
                    enabled=True,
                    url="http://rag.fake.local",
                    api_key=RAG_PLACEHOLDER_KEY,
                    fallback_enabled=True,
                    default_collection="acceptance_knowledge",
                    default_mode="hybrid",
                    top_k=3,
                    use_hyde=False,
                ),
            )
        )


@pytest.fixture()
def fake_policy_rag(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    FakeRAGClient.calls = []
    monkeypatch.setattr(policy_module, "KnowledgeSelector", AcceptanceKnowledgeSelector)
    yield
    FakeRAGClient.calls = []


def _block(key: str, content: str, *, source: str = "acceptance") -> ContextBlock:
    return ContextBlock(
        key=key,
        source=source,
        purpose=f"{key} 验收",
        content=content,
        priority=80,
        token_estimate=8,
    )


def _runtime_bundle(
    db_session,
    request: ContextBuildRequest,
    *,
    memory_context=None,
    collector: RecordingCollector | None = None,
) -> ContextBundle:
    return ContextBuilder(
        policy=ContextPolicy(rag_enabled=True),
        trace_collector=collector,
    ).build_runtime_context_bundle(
        db=db_session,
        request=request,
        memory_context=memory_context,
    )


def test_sectioned_context_renderer_keeps_stable_runtime_sections() -> None:
    bundle = ContextBundle(
        blocks=[
            _block("output_contract", "输出必须给出可执行步骤"),
            _block("farm", "农场：默认农场"),
            _block("rag_knowledge", "外部证据：黄瓜病害防治摘要", source="external_rag"),
            _block("active_task_state", "目标：制定番茄补光计划"),
            _block("assistant_role", "你是农业经营助手"),
        ],
        token_budget=500,
        token_estimate=40,
    )

    document = ContextRenderer().render_document(bundle)
    prompt = document.render_prompt_text()

    assert [section.name for section in document.sections] == [
        "Role & Policies",
        "Task",
        "Evidence",
        "Context",
        "Output",
    ]
    assert [block.key for block in document.sections[0].blocks] == ["assistant_role"]
    assert [block.key for block in document.sections[1].blocks] == [
        "active_task_state"
    ]
    assert [block.key for block in document.sections[2].blocks] == ["rag_knowledge"]
    assert [block.key for block in document.sections[3].blocks] == ["farm"]
    assert [block.key for block in document.sections[4].blocks] == ["output_contract"]
    assert prompt.index("## Role & Policies") < prompt.index("## Task")
    assert prompt.index("## Evidence") < prompt.index("## Context")
    assert prompt.index("## Context") < prompt.index("## Output")


def test_runtime_context_routes_fake_rag_to_evidence_for_diagnosis_and_skips_accounting(
    db_session,
    fake_policy_rag,
) -> None:
    diagnosis_bundle = _runtime_bundle(
        db_session,
        ContextBuildRequest(
            intent="query_diagnosis",
            query="黄瓜叶片有黄斑怎么防治",
            farm_id=FARM_ID,
            user_id=USER_ID,
            session_id="session-rag-diagnosis",
        ),
    )

    diagnosis_doc = ContextRenderer().render_document(diagnosis_bundle)
    evidence = next(
        section for section in diagnosis_doc.sections if section.name == "Evidence"
    )
    rag_block = next(block for block in evidence.blocks if block.key == "rag_knowledge")

    assert FakeRAGClient.calls == [
        {
            "query": "黄瓜叶片有黄斑怎么防治",
            "collection": "acceptance_knowledge",
            "mode": "hybrid",
            "top_k": 3,
            "filters": {},
            "use_hyde": False,
        }
    ]
    assert rag_block.source == "external_rag"
    assert "cucumber-disease-guide#7" in rag_block.content
    assert diagnosis_bundle.metadata["selector_metadata"]["knowledge"][
        "rag_called"
    ] is True

    FakeRAGClient.calls = []
    accounting_bundle = _runtime_bundle(
        db_session,
        ContextBuildRequest(
            intent="finance",
            query="查一下今天账单",
            selected_tool_names=["manage_cost"],
            farm_id=FARM_ID,
            user_id=USER_ID,
            session_id="session-rag-accounting",
        ),
    )

    assert FakeRAGClient.calls == []
    assert "rag_knowledge" not in {block.key for block in accounting_bundle.blocks}
    assert "knowledge" not in accounting_bundle.metadata.get("selector_metadata", {})


@pytest.mark.asyncio
async def test_task_state_written_after_missing_info_is_visible_in_next_runtime_context(
    db_session,
) -> None:
    await update_task_state_after_turn(
        db_session,
        TaskStateTurn(
            farm_id=FARM_ID,
            user_id=USER_ID,
            session_id="session-task-acceptance",
            user_input="帮我给番茄做一个补光计划",
            assistant_reply="可以。还需要补充：补光灯功率、棚室面积。",
        ),
    )

    bundle = _runtime_bundle(
        db_session,
        ContextBuildRequest(
            intent="plan",
            query="继续刚才的补光计划",
            farm_id=FARM_ID,
            user_id=USER_ID,
            session_id="session-task-acceptance",
        ),
    )
    document = ContextRenderer().render_document(bundle)
    task_section = next(
        section for section in document.sections if section.name == "Task"
    )
    task_block = next(
        block for block in task_section.blocks if block.key == "active_task_state"
    )

    assert "目标：帮我给番茄做一个补光计划" in task_block.content
    assert "状态：waiting_user" in task_block.content
    assert "缺失信息：补光灯功率；棚室面积" in task_block.content
    assert task_block.metadata["cache_scope"] == "session"


@pytest.mark.asyncio
async def test_explicit_long_term_memory_is_injected_for_new_session_same_farm_user(
    db_session,
) -> None:
    await record_explicit_memory_after_turn(
        db_session,
        ExplicitMemoryTurn(
            farm_id=FARM_ID,
            user_id=USER_ID,
            session_id="session-memory-source",
            user_input="记住我以后用亩",
            assistant_reply="好的，以后默认用亩。",
        ),
    )
    service = InMemoryMemoryService(
        long_term=SQLLongTermMemoryStore(
            session_factory=sessionmaker(bind=db_session.get_bind())
        )
    )
    memory_context = await service.build_context(
        user_id=USER_ID,
        farm_id=FARM_ID,
        session_id="session-memory-new",
    )

    bundle = _runtime_bundle(
        db_session,
        ContextBuildRequest(
            intent="chat",
            query="以后面积怎么表达",
            farm_id=FARM_ID,
            user_id=USER_ID,
            session_id="session-memory-new",
        ),
        memory_context=memory_context,
    )
    document = ContextRenderer().render_document(bundle)
    context_section = next(
        section for section in document.sections if section.name == "Context"
    )
    memory_block = next(
        block for block in context_section.blocks if block.key == "long_term_memory"
    )

    assert memory_context.session_id == "session-memory-new"
    assert "偏好：以后用亩" in memory_block.content
    assert memory_block.metadata["cache_scope"] == "farm_user"


def test_context_trace_payload_keeps_only_safe_acceptance_summary(
    db_session,
    fake_policy_rag,
) -> None:
    collector = RecordingCollector()

    bundle = _runtime_bundle(
        db_session,
        ContextBuildRequest(
            intent="query_diagnosis",
            query="黄瓜霜霉病怎么处理 Authorization: Bearer raw-query-token",
            farm_id=FARM_ID,
            user_id=USER_ID,
            session_id="session-trace-acceptance",
        ),
        collector=collector,
    )

    assert {block.key for block in bundle.blocks} >= {"farm", "rag_knowledge"}
    assert len(collector.records) == 1
    record = collector.records[0]
    output = record["output_data"]
    output_text = str(output)

    assert set(record["input_data"]) == {
        "block_count",
        "selected_keys",
        "policy_intent",
    }
    assert record["input_data"]["policy_intent"] == "query_diagnosis"
    assert "selected_blocks" in output
    assert "sections" in output
    assert "selector_metadata" in output
    assert output["selector_metadata"]["knowledge"]["source_count"] == 1
    assert output["selected_blocks"][
        [block["key"] for block in output["selected_blocks"]].index("rag_knowledge")
    ]["rag"]["sources"] == [
        {
            "doc_id": "cucumber-disease-guide",
            "chunk_index": 7,
            "score": 0.94,
            "metadata": {
                "source": "fake-guide.md",
                "title": "黄瓜病害防治",
            },
        }
    ]
    assert RAG_RAW_CHUNK not in output_text
    assert RAG_PLACEHOLDER_KEY not in output_text
    assert RAG_SECRET_MARKER not in output_text
    assert "raw-query-token" not in output_text
    assert "raw_chunk" not in output_text
