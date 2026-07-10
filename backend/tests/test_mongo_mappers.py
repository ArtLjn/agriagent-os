"""MongoDB 文档 mapper 测试。"""

from datetime import datetime

import pytest

from app.models.data_flywheel import (
    AgentCaseDraft,
    AgentDataFlywheelPrelabel,
    AgentRepairPack,
    AgentReviewIssueChain,
)
from app.models.agent_record import AgentRecord
from app.models.conversation import Conversation, ConversationMessage
from app.models.guardrails_log import GuardrailsLog
from app.models.trace import TraceRecord


@pytest.mark.no_db
def test_trace_record_mapper_uses_camel_case_fields_and_restores_model():
    from app.infra.mongo_mappers import (
        trace_record_from_mongo_doc,
        trace_record_to_mongo_doc,
    )

    created_at = datetime(2026, 6, 26, 8, 0, 0)
    start_time = datetime(2026, 6, 26, 8, 0, 1)
    end_time = datetime(2026, 6, 26, 8, 0, 3)
    record = TraceRecord(
        id=101,
        request_id="req-001",
        session_id="sess-001",
        farm_id=7,
        conversation_message_id=9001,
        round_index=2,
        node_type="llm_call",
        node_name="answer_user",
        status="success",
        input_data={"messages": [{"role": "user", "content": "hello"}]},
        output_data='{"reply": "world"}',
        token_usage='{"promptTokens": 3, "completionTokens": 4}',
        error_message=None,
        start_time=start_time,
        end_time=end_time,
        duration_ms=2000,
        created_at=created_at,
    )

    doc = trace_record_to_mongo_doc(record)

    assert doc == {
        "mysqlId": 101,
        "requestId": "req-001",
        "sessionId": "sess-001",
        "farmId": 7,
        "conversationMessageId": 9001,
        "roundIndex": 2,
        "nodeType": "llm_call",
        "nodeName": "answer_user",
        "status": "success",
        "input": {"messages": [{"role": "user", "content": "hello"}]},
        "output": {"reply": "world"},
        "tokenUsage": {"promptTokens": 3, "completionTokens": 4},
        "errorMessage": None,
        "startTime": start_time,
        "endTime": end_time,
        "durationMs": 2000,
        "createdAt": created_at,
    }
    assert "input_data" not in doc
    assert "created_at" not in doc

    restored = trace_record_from_mongo_doc({**doc, "_id": "mongo-id"})

    assert restored.id == 101
    assert restored.request_id == "req-001"
    assert restored.farm_id == 7
    assert restored.input_data == {"messages": [{"role": "user", "content": "hello"}]}
    assert restored.output_data == {"reply": "world"}
    assert restored.token_usage == {"promptTokens": 3, "completionTokens": 4}
    assert restored.created_at == created_at


@pytest.mark.no_db
def test_data_flywheel_mappers_preserve_business_ids_and_json_documents():
    from app.infra.mongo_mappers import (
        case_draft_from_mongo_doc,
        case_draft_to_mongo_doc,
        prelabel_from_mongo_doc,
        prelabel_to_mongo_doc,
        repair_pack_from_mongo_doc,
        repair_pack_to_mongo_doc,
        review_issue_chain_from_mongo_doc,
        review_issue_chain_to_mongo_doc,
    )

    created_at = datetime(2026, 6, 26, 9, 0, 0)
    updated_at = datetime(2026, 6, 26, 10, 0, 0)
    reviewed_at = datetime(2026, 6, 26, 11, 0, 0)
    resolved_at = datetime(2026, 6, 26, 12, 0, 0)

    case_draft = AgentCaseDraft(
        id=201,
        farm_id=7,
        draft_id="draft-001",
        source_sample_id="sample-001",
        target_type="regression",
        status="draft",
        case_json='{"steps": [{"tool": "weather"}]}',
        created_by="reviewer-1",
        created_at=created_at,
        updated_at=updated_at,
    )
    repair_pack = AgentRepairPack(
        id=202,
        farm_id=7,
        pack_id="pack-001",
        fix_target="router",
        labels='[{"name": "bad_intent"}]',
        source_sample_ids=["sample-001"],
        source_label_ids=[301],
        dedup_key="dedup-001",
        status="ready",
        export_path="/tmp/pack.json",
        manifest_json={"files": ["a.py"]},
        export_error=None,
        repair_note="fix prompt",
        verification_summary={"passed": True},
        created_by="reviewer-1",
        resolved_by="reviewer-2",
        resolved_at=resolved_at,
        created_at=created_at,
        updated_at=updated_at,
    )
    issue_chain = AgentReviewIssueChain(
        id=203,
        farm_id=7,
        chain_id="chain-001",
        session_id="sess-001",
        trigger_turn_id=11,
        context_turn_ids=[9, 10],
        result_turn_ids=[12],
        status="open",
        severity="high",
        dominant_signal="intent_mismatch",
        final_labels=[{"name": "bad_intent"}],
        source_label_ids=[301],
        root_cause="wrong route",
        expected_behavior="choose weather",
        fix_target="router",
        reviewer_comment="needs fix",
        false_positive_reason=None,
        missing_evidence=["trace"],
        ai_judge={"score": 0.9},
        reviewer_id="reviewer-1",
        reviewed_at=reviewed_at,
        created_at=created_at,
        updated_at=updated_at,
    )
    prelabel = AgentDataFlywheelPrelabel(
        id=204,
        farm_id=7,
        sample_id="sample-001",
        sample_type="turn",
        session_id="sess-001",
        turn_id=11,
        request_id="req-001",
        source="llm_judge",
        status="pending",
        labels=[{"name": "bad_intent"}],
        root_cause="wrong route",
        severity="medium",
        confidence=0.82,
        reason="judge reason",
        recommended_fix="update examples",
        judge_model="glm-4.6",
        prompt_version="v1",
        raw_response={"choices": [{"text": "bad"}]},
        accepted_label_ids=[301],
        reviewed_by="reviewer-1",
        reviewed_at=reviewed_at,
        created_at=created_at,
        updated_at=updated_at,
    )

    case_doc = case_draft_to_mongo_doc(case_draft)
    pack_doc = repair_pack_to_mongo_doc(repair_pack)
    chain_doc = review_issue_chain_to_mongo_doc(issue_chain)
    prelabel_doc = prelabel_to_mongo_doc(prelabel)

    assert case_doc["mysqlId"] == 201
    assert case_doc["farmId"] == 7
    assert case_doc["draftId"] == "draft-001"
    assert case_doc["caseJson"] == {"steps": [{"tool": "weather"}]}
    assert isinstance(case_doc["caseJson"], dict)

    assert pack_doc["mysqlId"] == 202
    assert pack_doc["packId"] == "pack-001"
    assert pack_doc["sourceSampleIds"] == ["sample-001"]
    assert isinstance(pack_doc["labels"], list)
    assert isinstance(pack_doc["manifestJson"], dict)

    assert chain_doc["mysqlId"] == 203
    assert chain_doc["chainId"] == "chain-001"
    assert chain_doc["contextTurnIds"] == [9, 10]
    assert chain_doc["aiJudge"] == {"score": 0.9}
    assert isinstance(chain_doc["missingEvidence"], list)

    assert prelabel_doc["mysqlId"] == 204
    assert prelabel_doc["sampleId"] == "sample-001"
    assert prelabel_doc["rawResponse"] == {"choices": [{"text": "bad"}]}
    assert isinstance(prelabel_doc["labels"], list)

    restored_case = case_draft_from_mongo_doc({**case_doc, "_id": "case-mongo-id"})
    restored_pack = repair_pack_from_mongo_doc({**pack_doc, "_id": "pack-mongo-id"})
    restored_chain = review_issue_chain_from_mongo_doc(
        {**chain_doc, "_id": "chain-mongo-id"}
    )
    restored_prelabel = prelabel_from_mongo_doc(
        {**prelabel_doc, "_id": "prelabel-mongo-id"}
    )

    assert restored_case.id == 201
    assert restored_case.case_json == {"steps": [{"tool": "weather"}]}
    assert restored_pack.id == 202
    assert restored_pack.source_sample_ids == ["sample-001"]
    assert restored_chain.id == 203
    assert restored_chain.ai_judge == {"score": 0.9}
    assert restored_prelabel.id == 204
    assert restored_prelabel.raw_response == {"choices": [{"text": "bad"}]}
    assert restored_prelabel.reviewed_at == reviewed_at


@pytest.mark.no_db
def test_phase_two_online_document_mappers_preserve_mysql_ids_and_legacy_meta():
    from app.infra.mongo_mappers import (
        agent_record_from_mongo_doc,
        agent_record_to_mongo_doc,
        conversation_message_from_mongo_doc,
        conversation_message_to_mongo_doc,
        guardrails_log_from_mongo_doc,
        guardrails_log_to_mongo_doc,
    )

    created_at = datetime(2026, 6, 26, 13, 0, 0)
    conversation = Conversation(id=10, farm_id=7, session_id="sess-1")
    message = ConversationMessage(
        id=301,
        conversation_id=10,
        role="assistant",
        content="已完成",
        meta='{"skills": ["crop-cycle"]}',
        turn_id=88,
        created_at=created_at,
    )
    message.conversation = conversation
    record = AgentRecord(
        id=302,
        farm_id=7,
        user_id="user-1",
        conversation_id=10,
        cycle_id=12,
        record_type="daily",
        content="{}",
        meta="not-json",
        created_at=created_at,
    )
    log = GuardrailsLog(
        id=303,
        farm_id=7,
        trigger_type="input_injection",
        trigger_detail="blocked",
        source_text="secret text",
        created_at=created_at,
    )

    message_doc = conversation_message_to_mongo_doc(message)
    record_doc = agent_record_to_mongo_doc(record)
    log_doc = guardrails_log_to_mongo_doc(log)

    assert message_doc["mysqlId"] == 301
    assert message_doc["farmId"] == 7
    assert message_doc["sessionId"] == "sess-1"
    assert message_doc["meta"] == {"skills": ["crop-cycle"]}
    assert message_doc["legacyMetaText"] is None
    assert record_doc["mysqlId"] == 302
    assert record_doc["meta"] is None
    assert record_doc["legacyMetaText"] == "not-json"
    assert log_doc["mysqlId"] == 303
    assert log_doc["sourceTextHash"]

    restored_message = conversation_message_from_mongo_doc(message_doc)
    restored_record = agent_record_from_mongo_doc(record_doc)
    restored_log = guardrails_log_from_mongo_doc(log_doc)

    assert restored_message.id == 301
    assert restored_message.meta_json == {"skills": ["crop-cycle"]}
    assert restored_record.id == 302
    assert restored_record.meta == "not-json"
    assert restored_log.id == 303
    assert restored_log.source_text == "secret text"


@pytest.mark.no_db
def test_conversation_message_from_mongo_doc_falls_back_to_object_id_time():
    from bson import ObjectId

    from app.infra.mongo_mappers import conversation_message_from_mongo_doc

    object_id = ObjectId()
    restored_message = conversation_message_from_mongo_doc(
        {
            "_id": object_id,
            "mysqlId": 1,
            "conversationId": 2,
            "role": "user",
            "content": "你好",
        }
    )

    assert restored_message.created_at == object_id.generation_time.replace(tzinfo=None)


@pytest.mark.no_db
def test_reverse_mappers_tolerate_missing_optional_fields():
    from app.infra.mongo_mappers import trace_record_from_mongo_doc

    restored = trace_record_from_mongo_doc(
        {
            "mysqlId": 101,
            "requestId": "req-001",
            "farmId": 7,
            "nodeType": "llm_call",
            "nodeName": "answer_user",
            "createdAt": datetime(2026, 6, 26, 8, 0, 0),
        }
    )

    assert restored.id == 101
    assert restored.session_id is None
    assert restored.input_data is None
    assert restored.token_usage is None
    assert restored.status is None


@pytest.mark.no_db
def test_reverse_mapper_only_parses_declared_json_fields():
    from app.infra.mongo_mappers import trace_record_from_mongo_doc

    restored = trace_record_from_mongo_doc(
        {
            "mysqlId": 101,
            "requestId": "123",
            "farmId": 7,
            "nodeType": "llm_call",
            "nodeName": "answer_user",
            "status": "false",
            "input": '{"prompt": "hello"}',
            "output": "{not-json",
            "tokenUsage": '[{"totalTokens": 7}]',
            "createdAt": datetime(2026, 6, 26, 8, 0, 0),
        }
    )

    assert restored.request_id == "123"
    assert restored.status == "false"
    assert restored.input_data == {"prompt": "hello"}
    assert restored.output_data == "{not-json"
    assert restored.token_usage == [{"totalTokens": 7}]
