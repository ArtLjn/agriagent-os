"""Context trace payload 安全摘要测试。"""

from __future__ import annotations

from typing import Any

from app.context.builder import ContextBuilder
from app.context.models import ContextBlock, ContextBundle
from app.context.trace import build_context_trace_payload


class StaticSelector:
    def __init__(self, block: ContextBlock) -> None:
        self.block = block

    def select(self, **_kwargs: Any) -> list[ContextBlock]:
        return [self.block]


class RecordingCollector:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    def record(self, **kwargs: Any) -> None:
        self.records.append(kwargs)


class FailingCollector:
    def record(self, **_kwargs: Any) -> None:
        raise RuntimeError("trace backend unavailable")


def test_context_trace_payload_keeps_only_safe_block_preview() -> None:
    full_content = (
        "完整上下文正文不应进入 trace。"
        "Authorization: Bearer secret-token-123。"
        "mongodb://trace-user:trace-pass@mongo.internal:27017/farm。"
        "这是一段很长的调试内容" * 20
    )
    bundle = ContextBundle(
        blocks=[
            ContextBlock(
                key="farm",
                source="farm",
                purpose="农场状态",
                content=full_content,
                priority=90,
                required=True,
                metadata={
                    "layer": "context",
                    "cache_scope": "request",
                    "api_key": "secret-api-key",
                },
            )
        ],
        token_budget=300,
        token_estimate=120,
        metadata={
            "allowlist_filtered_keys": ["weather_snapshot"],
            "selector_errors": [
                {"selector": "BrokenSelector", "error": "boom password=hidden"}
            ],
        },
    )

    payload = build_context_trace_payload(bundle)
    payload_text = str(payload)

    assert payload["token_budget"] == 300
    assert payload["selected_blocks"][0]["key"] == "farm"
    assert payload["selected_blocks"][0]["preview"]
    assert len(payload["selected_blocks"][0]["preview"]) <= 160
    assert full_content not in payload_text
    assert "secret-token-123" not in payload_text
    assert "trace-pass" not in payload_text
    assert "secret-api-key" not in payload_text
    assert payload["allowlist_filtered_keys"] == ["weather_snapshot"]


def test_context_trace_payload_preserves_rag_diagnostics_without_raw_chunks() -> None:
    raw_chunk = "黄瓜霜霉病原始 chunk 全文不应保存。" * 30
    bundle = ContextBundle(
        blocks=[
            ContextBlock(
                key="rag_knowledge",
                source="external_rag",
                purpose="外部农技知识检索",
                content=raw_chunk,
                priority=35,
                metadata={
                    "collection": "agri_knowledge",
                    "requested_mode": "hybrid",
                    "actual_mode": "bm25",
                    "warning": "hybrid_to_bm25_fallback",
                    "result_count": 3,
                    "top_score": 0.91,
                    "sources": [
                        {
                            "doc_id": "cucumber-guide",
                            "chunk_index": 4,
                            "score": 0.91,
                            "metadata": {
                                "source": "guide.md",
                                "api_key": "rag-secret",
                                "raw_chunk": raw_chunk,
                            },
                        }
                    ],
                    "Authorization": "Bearer rag-auth-token",
                },
            )
        ],
        token_budget=400,
        token_estimate=180,
    )

    payload = build_context_trace_payload(bundle)
    rag_summary = payload["selected_blocks"][0]["rag"]
    payload_text = str(payload)

    assert rag_summary["collection"] == "agri_knowledge"
    assert rag_summary["mode"] == "hybrid"
    assert rag_summary["actual_mode"] == "bm25"
    assert rag_summary["warning"] == "hybrid_to_bm25_fallback"
    assert rag_summary["source_count"] == 3
    assert rag_summary["top_score"] == 0.91
    assert rag_summary["sources"][0]["doc_id"] == "cucumber-guide"
    assert rag_summary["sources"][0]["metadata"] == {"source": "guide.md"}
    assert raw_chunk not in payload_text
    assert "rag-secret" not in payload_text
    assert "rag-auth-token" not in payload_text


def test_context_trace_payload_redacts_prefixed_secret_keys_and_text() -> None:
    bundle = ContextBundle(
        blocks=[
            ContextBlock(
                key="farm",
                source="farm",
                purpose="农场状态",
                content="block metadata 包含 api_token=DEPKEY",
                priority=90,
                metadata={
                    "layer": "context",
                    "required_reason": "refresh_token=REALTOKEN",
                    "selected_by_skill_dependencies": [
                        "embedding_api_key: EMBEDKEY",
                        "api_token=DEPKEY",
                    ],
                },
            )
        ],
        token_budget=300,
        token_estimate=120,
        metadata={
            "selector_errors": [
                {
                    "selector": "KnowledgeSelector",
                    "error": "rag_service_api_key=REALKEY",
                },
                {
                    "selector": "EmbeddingSelector",
                    "error": "embedding_api_key: EMBEDKEY",
                },
            ],
            "context_dependency_diagnostics": [
                {
                    "block_key": "rag_knowledge",
                    "dependencies": ["retrieve"],
                    "status": "selected",
                    "rag_service_api_key": "REALKEY",
                    "refresh_token": "REALTOKEN",
                    "embedding_api_key": "EMBEDKEY",
                    "api_token": "DEPKEY",
                }
            ],
            "policy": {
                "intent": "query",
                "selected_tool_names": ["search"],
                "enabled_layers": ["context"],
                "context_dependency_map": {},
                "rag_service_api_key": "REALKEY",
            },
            "selector_metadata": {
                "knowledge": {
                    "collection": "agri",
                    "actual_mode": "hybrid",
                    "warning": "api_token=DEPKEY",
                    "source_count": 1,
                    "sources": [
                        {
                            "doc_id": "doc-1",
                            "score": 0.8,
                            "metadata": {"embedding_api_key": "EMBEDKEY"},
                        }
                    ],
                }
            },
        },
    )

    payload_text = str(build_context_trace_payload(bundle))

    assert "REALKEY" not in payload_text
    assert "REALTOKEN" not in payload_text
    assert "EMBEDKEY" not in payload_text
    assert "DEPKEY" not in payload_text


def test_context_builder_record_trace_uses_safe_payload(db_session) -> None:
    collector = RecordingCollector()
    secret_content = "完整 prompt 正文不应进入 trace，token=raw-token。" * 30
    builder = ContextBuilder(
        selectors=[
            StaticSelector(
                ContextBlock(
                    key="farm",
                    source="farm",
                    purpose="农场状态",
                    content=secret_content,
                    priority=90,
                    metadata={"required_reason": "runtime", "password": "hidden"},
                )
            )
        ],
        max_tokens=256,
        trace_collector=collector,
    )

    bundle = builder.build(db=db_session, farm_id=1)
    record = collector.records[0]
    output_text = str(record["output_data"])

    assert record["input_data"]["block_count"] == len(bundle.blocks)
    assert record["input_data"]["selected_keys"] == ["farm"]
    assert "selected_blocks" in record["output_data"]
    assert secret_content not in output_text
    assert "raw-token" not in output_text
    assert "hidden" not in output_text


def test_context_builder_build_ignores_trace_collector_failure(db_session) -> None:
    builder = ContextBuilder(
        selectors=[
            StaticSelector(
                ContextBlock(
                    key="farm",
                    source="farm",
                    purpose="农场状态",
                    content="农场：默认农场",
                    priority=90,
                )
            )
        ],
        trace_collector=FailingCollector(),
    )

    bundle = builder.build(db=db_session, farm_id=1)

    assert [block.key for block in bundle.blocks] == ["farm"]
