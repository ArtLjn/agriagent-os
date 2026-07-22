"""外部 RAG 知识 selector 测试。"""

import pytest

from app.context.builder import ContextBuilder
from app.context.models import ContextBundle
from app.context.renderer import ContextRenderer
from app.context.rag_provider import RAGKnowledgeProvider
from app.context.selectors.knowledge import KnowledgeSelector
from app.infra.quillrag_client import QuillRAGDocument, QuillRAGRetrieveResult
from app.shared.config import RAGServiceConfig


PLACEHOLDER_API_KEY = "placeholder-rag-key"


class FakeRAGClient:
    def __init__(self, result: QuillRAGRetrieveResult) -> None:
        self.result = result
        self.calls: list[dict] = []

    def retrieve(self, **kwargs) -> QuillRAGRetrieveResult:
        self.calls.append(kwargs)
        return self.result


def _provider(
    result: QuillRAGRetrieveResult,
    *,
    fallback_enabled: bool = True,
) -> RAGKnowledgeProvider:
    return RAGKnowledgeProvider(
        client=FakeRAGClient(result),
        config=RAGServiceConfig(
            enabled=True,
            url="http://rag.local",
            fallback_enabled=fallback_enabled,
            api_key=PLACEHOLDER_API_KEY,
            default_collection="agri_knowledge",
            default_mode="hybrid",
            top_k=3,
            use_hyde=False,
        ),
    )


def test_knowledge_selector_generates_rag_knowledge_block() -> None:
    selector = KnowledgeSelector(
        provider=_provider(
            QuillRAGRetrieveResult(
                ok=True,
                actual_mode="bm25",
                warning="hybrid_to_bm25_fallback",
                results=[
                    QuillRAGDocument(
                        content="黄瓜霜霉病初期可摘除病叶，注意通风降湿。",
                        score=0.873,
                        doc_id="cucumber-disease",
                        chunk_index=4,
                        metadata={"source": "agri.md", "raw_json": {"large": "data"}},
                    )
                ],
            )
        )
    )

    blocks = selector.select(query="黄瓜叶片有黄斑怎么处理")

    assert len(blocks) == 1
    block = blocks[0]
    assert block.key == "rag_knowledge"
    assert block.source == "external_rag"
    assert "来源：cucumber-disease#4" in block.content
    assert "分数：0.873" in block.content
    assert "黄瓜霜霉病初期" in block.content
    assert "raw_json" not in block.content
    assert PLACEHOLDER_API_KEY not in block.content
    assert block.metadata["rag_called"] is True
    assert block.metadata["actual_mode"] == "bm25"
    assert block.metadata["warning"] == "hybrid_to_bm25_fallback"


def test_knowledge_selector_keeps_safe_rag_source_trace_metadata() -> None:
    selector = KnowledgeSelector(
        provider=_provider(
            QuillRAGRetrieveResult(
                ok=True,
                actual_mode="hybrid",
                results=[
                    QuillRAGDocument(
                        content="黄瓜霜霉病原始正文不会进入 metadata 摘要。",
                        score=0.91,
                        doc_id="cucumber-guide",
                        chunk_index=4,
                        metadata={
                            "source": "guide.md",
                            "api_key": PLACEHOLDER_API_KEY,
                            "raw_chunk": "原始 chunk",
                        },
                    )
                ],
            )
        )
    )

    block = selector.select(query="黄瓜霜霉病怎么处理")[0]

    assert block.metadata["source_count"] == 1
    assert block.metadata["top_score"] == 0.91
    assert block.metadata["sources"] == [
        {
            "doc_id": "cucumber-guide",
            "chunk_index": 4,
            "score": 0.91,
            "metadata": {"source": "guide.md"},
        }
    ]
    assert PLACEHOLDER_API_KEY not in str(block.metadata)
    assert "raw_chunk" not in str(block.metadata)


def test_knowledge_selector_returns_empty_block_for_empty_results() -> None:
    selector = KnowledgeSelector(
        provider=_provider(
            QuillRAGRetrieveResult(ok=True, actual_mode="hybrid", results=[])
        )
    )

    assert selector.select(query="番茄怎么育苗") == []
    assert selector.last_metadata["rag_called"] is True
    assert selector.last_metadata["rag_empty"] is True


def test_knowledge_selector_fallback_hides_failure_from_prompt() -> None:
    selector = KnowledgeSelector(
        provider=_provider(
            QuillRAGRetrieveResult(
                ok=False,
                error_code="network_error",
                error_message="connection failed",
            )
        )
    )

    blocks = selector.select(query="番茄苗猝倒病怎么处理")

    assert blocks == []
    assert selector.last_metadata["rag_unavailable"] is True
    assert selector.last_metadata["rag_error_code"] == "network_error"


def test_builder_attaches_rag_fallback_metadata_to_bundle(db_session) -> None:
    selector = KnowledgeSelector(
        provider=_provider(
            QuillRAGRetrieveResult(
                ok=False,
                error_code="timeout",
                error_message="request timed out",
            )
        )
    )
    builder = ContextBuilder(selectors=[selector], max_tokens=128)

    bundle = builder.build(
        db=db_session,
        farm_id=1,
        query="番茄苗猝倒病怎么处理",
    )

    metadata = bundle.metadata["selector_metadata"]["knowledge"]
    assert metadata["rag_called"] is True
    assert metadata["rag_unavailable"] is True
    assert metadata["rag_error_code"] == "timeout"
    assert PLACEHOLDER_API_KEY not in str(bundle.summary())


def test_builder_propagates_rag_error_when_fallback_disabled(db_session) -> None:
    selector = KnowledgeSelector(
        provider=_provider(
            QuillRAGRetrieveResult(
                ok=False,
                error_code="http_503",
                error_message="service unavailable",
            ),
            fallback_enabled=False,
        )
    )
    builder = ContextBuilder(selectors=[selector], max_tokens=128)

    with pytest.raises(Exception) as excinfo:
        builder.build(
            db=db_session,
            farm_id=1,
            query="黄瓜霜霉病怎么处理",
        )

    exc = excinfo.value
    assert exc.__class__.__name__ == "RAGUnavailableError"
    assert getattr(exc, "error_code") == "http_503"
    assert getattr(exc, "error_message") == "service unavailable"


def test_rag_prompt_and_debug_summary_do_not_expose_api_key_or_raw_json() -> None:
    selector = KnowledgeSelector(
        provider=_provider(
            QuillRAGRetrieveResult(
                ok=True,
                actual_mode="hybrid",
                results=[
                    QuillRAGDocument(
                        content="番茄定植后缓苗期少量多次浇水。",
                        score=0.8,
                        doc_id="tomato-guide",
                        chunk_index=1,
                        metadata={
                            "source": "guide.md",
                            "api_key": PLACEHOLDER_API_KEY,
                            "payload": {"raw": "json"},
                        },
                    )
                ],
            )
        )
    )
    blocks = selector.select(query="番茄定植后怎么浇水")
    bundle = ContextBundle(
        blocks=blocks,
        token_budget=300,
        token_estimate=sum(block.token_estimate or 0 for block in blocks),
    )

    prompt_text = ContextRenderer().render_prompt_text(bundle)
    debug_summary = bundle.summary()

    assert "## Evidence" in prompt_text
    assert PLACEHOLDER_API_KEY not in prompt_text
    assert "payload" not in prompt_text
    assert PLACEHOLDER_API_KEY not in str(debug_summary)
    assert "api_key" not in str(debug_summary)
