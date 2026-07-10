"""MySQL ORM 行与 MongoDB 文档之间的纯映射函数。"""

from __future__ import annotations

import json
import hashlib
from collections.abc import Mapping
from typing import Any, TypeVar

from app.models.agent_record import AgentRecord
from app.models.conversation import ConversationMessage
from app.models.data_flywheel import (
    AgentCaseDraft,
    AgentDataFlywheelPrelabel,
    AgentRepairPack,
    AgentReviewIssueChain,
)
from app.models.guardrails_log import GuardrailsLog
from app.models.trace import TraceRecord

ModelT = TypeVar("ModelT")


def _json_value(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _json_document(value: Any) -> tuple[Any, str | None]:
    if value is None:
        return None, None
    if isinstance(value, str):
        try:
            return json.loads(value), None
        except json.JSONDecodeError:
            return None, value
    return value, None


def _sha256_text(value: str | None) -> str | None:
    if value is None:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _model_from_doc(
    model_cls: type[ModelT],
    doc: Mapping[str, Any],
    fields: dict[str, str],
    json_fields: set[str] | None = None,
) -> ModelT:
    json_field_names = json_fields or set()
    values = {}
    for doc_field, model_field in fields.items():
        if doc_field in doc:
            value = doc[doc_field]
            values[model_field] = (
                _json_value(value) if doc_field in json_field_names else value
            )
    if "mysqlId" in doc:
        values["id"] = doc["mysqlId"]
    return model_cls(**values)


def trace_record_to_mongo_doc(record: TraceRecord) -> dict[str, Any]:
    return {
        "mysqlId": record.id,
        "requestId": record.request_id,
        "sessionId": record.session_id,
        "farmId": record.farm_id,
        "conversationMessageId": record.conversation_message_id,
        "roundIndex": record.round_index,
        "nodeType": record.node_type,
        "nodeName": record.node_name,
        "status": record.status,
        "input": _json_value(record.input_data),
        "output": _json_value(record.output_data),
        "tokenUsage": _json_value(record.token_usage),
        "errorMessage": record.error_message,
        "startTime": record.start_time,
        "endTime": record.end_time,
        "durationMs": record.duration_ms,
        "createdAt": record.created_at,
    }


def trace_record_from_mongo_doc(doc: Mapping[str, Any]) -> TraceRecord:
    return _model_from_doc(
        TraceRecord,
        doc,
        {
            "requestId": "request_id",
            "sessionId": "session_id",
            "farmId": "farm_id",
            "conversationMessageId": "conversation_message_id",
            "roundIndex": "round_index",
            "nodeType": "node_type",
            "nodeName": "node_name",
            "status": "status",
            "input": "input_data",
            "output": "output_data",
            "tokenUsage": "token_usage",
            "errorMessage": "error_message",
            "startTime": "start_time",
            "endTime": "end_time",
            "durationMs": "duration_ms",
            "createdAt": "created_at",
        },
        json_fields={"input", "output", "tokenUsage"},
    )


def conversation_message_to_mongo_doc(
    message: ConversationMessage,
    *,
    farm_id: int | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    conversation = getattr(message, "conversation", None)
    resolved_farm_id = farm_id
    if resolved_farm_id is None and conversation is not None:
        resolved_farm_id = getattr(conversation, "farm_id", None)
    resolved_session_id = session_id
    if resolved_session_id is None and conversation is not None:
        resolved_session_id = getattr(conversation, "session_id", None)
    meta_value = message.meta_json if message.meta_json is not None else message.meta
    meta_doc, legacy_meta_text = _json_document(meta_value)
    return {
        "mysqlId": message.id,
        "farmId": resolved_farm_id,
        "conversationId": message.conversation_id,
        "sessionId": resolved_session_id,
        "role": message.role,
        "content": message.content,
        "contentHash": message.content_hash or _sha256_text(message.content),
        "turnId": message.turn_id,
        "meta": meta_doc,
        "legacyMetaText": legacy_meta_text,
        "createdAt": message.created_at,
    }


def conversation_message_from_mongo_doc(
    doc: Mapping[str, Any],
) -> ConversationMessage:
    fields = {
        "conversationId": "conversation_id",
        "role": "role",
        "content": "content",
        "contentHash": "content_hash",
        "turnId": "turn_id",
        "meta": "meta_json",
        "legacyMetaText": "meta",
        "createdAt": "created_at",
    }
    doc_values = dict(doc)
    if doc_values.get("createdAt") is None:
        fallback_time = _object_id_generation_time(doc_values.get("_id"))
        if fallback_time is not None:
            doc_values["createdAt"] = fallback_time
    message = _model_from_doc(
        ConversationMessage,
        doc_values,
        fields,
    )
    if message.meta is None and message.meta_json is not None:
        message.meta = json.dumps(message.meta_json, ensure_ascii=False)
    return message


def _object_id_generation_time(value: Any) -> Any:
    generation_time = getattr(value, "generation_time", None)
    if generation_time is None:
        return None
    return generation_time.replace(tzinfo=None)


def agent_record_to_mongo_doc(record: AgentRecord) -> dict[str, Any]:
    meta_doc, legacy_meta_text = _json_document(record.meta)
    return {
        "mysqlId": record.id,
        "farmId": record.farm_id,
        "userId": record.user_id,
        "conversationId": record.conversation_id,
        "cycleId": record.cycle_id,
        "recordType": record.record_type,
        "content": record.content,
        "meta": meta_doc,
        "legacyMetaText": legacy_meta_text,
        "createdAt": record.created_at,
    }


def agent_record_from_mongo_doc(doc: Mapping[str, Any]) -> AgentRecord:
    record = _model_from_doc(
        AgentRecord,
        doc,
        {
            "farmId": "farm_id",
            "userId": "user_id",
            "conversationId": "conversation_id",
            "cycleId": "cycle_id",
            "recordType": "record_type",
            "content": "content",
            "legacyMetaText": "meta",
            "createdAt": "created_at",
        },
    )
    if record.meta is None and "meta" in doc:
        record.meta = json.dumps(doc.get("meta"), ensure_ascii=False)
    return record


def guardrails_log_to_mongo_doc(log: GuardrailsLog) -> dict[str, Any]:
    return {
        "mysqlId": log.id,
        "farmId": log.farm_id,
        "triggerType": log.trigger_type,
        "triggerDetail": log.trigger_detail,
        "sourceText": log.source_text,
        "sourceTextHash": _sha256_text(log.source_text),
        "createdAt": log.created_at,
    }


def guardrails_log_from_mongo_doc(doc: Mapping[str, Any]) -> GuardrailsLog:
    return _model_from_doc(
        GuardrailsLog,
        doc,
        {
            "farmId": "farm_id",
            "triggerType": "trigger_type",
            "triggerDetail": "trigger_detail",
            "sourceText": "source_text",
            "createdAt": "created_at",
        },
    )


def case_draft_to_mongo_doc(draft: AgentCaseDraft) -> dict[str, Any]:
    return {
        "mysqlId": draft.id,
        "farmId": draft.farm_id,
        "draftId": draft.draft_id,
        "sourceSampleId": draft.source_sample_id,
        "targetType": draft.target_type,
        "status": draft.status,
        "caseJson": _json_value(draft.case_json),
        "createdBy": draft.created_by,
        "createdAt": draft.created_at,
        "updatedAt": draft.updated_at,
    }


def case_draft_from_mongo_doc(doc: Mapping[str, Any]) -> AgentCaseDraft:
    return _model_from_doc(
        AgentCaseDraft,
        doc,
        {
            "farmId": "farm_id",
            "draftId": "draft_id",
            "sourceSampleId": "source_sample_id",
            "targetType": "target_type",
            "status": "status",
            "caseJson": "case_json",
            "createdBy": "created_by",
            "createdAt": "created_at",
            "updatedAt": "updated_at",
        },
        json_fields={"caseJson"},
    )


def repair_pack_to_mongo_doc(pack: AgentRepairPack) -> dict[str, Any]:
    return {
        "mysqlId": pack.id,
        "farmId": pack.farm_id,
        "packId": pack.pack_id,
        "fixTarget": pack.fix_target,
        "labels": _json_value(pack.labels),
        "sourceSampleIds": _json_value(pack.source_sample_ids),
        "sourceLabelIds": _json_value(pack.source_label_ids),
        "dedupKey": pack.dedup_key,
        "status": pack.status,
        "exportPath": pack.export_path,
        "manifestJson": _json_value(pack.manifest_json),
        "exportError": pack.export_error,
        "repairNote": pack.repair_note,
        "verificationSummary": _json_value(pack.verification_summary),
        "createdBy": pack.created_by,
        "resolvedBy": pack.resolved_by,
        "resolvedAt": pack.resolved_at,
        "createdAt": pack.created_at,
        "updatedAt": pack.updated_at,
    }


def repair_pack_from_mongo_doc(doc: Mapping[str, Any]) -> AgentRepairPack:
    return _model_from_doc(
        AgentRepairPack,
        doc,
        {
            "farmId": "farm_id",
            "packId": "pack_id",
            "fixTarget": "fix_target",
            "labels": "labels",
            "sourceSampleIds": "source_sample_ids",
            "sourceLabelIds": "source_label_ids",
            "dedupKey": "dedup_key",
            "status": "status",
            "exportPath": "export_path",
            "manifestJson": "manifest_json",
            "exportError": "export_error",
            "repairNote": "repair_note",
            "verificationSummary": "verification_summary",
            "createdBy": "created_by",
            "resolvedBy": "resolved_by",
            "resolvedAt": "resolved_at",
            "createdAt": "created_at",
            "updatedAt": "updated_at",
        },
        json_fields={
            "labels",
            "sourceSampleIds",
            "sourceLabelIds",
            "manifestJson",
            "verificationSummary",
        },
    )


def review_issue_chain_to_mongo_doc(chain: AgentReviewIssueChain) -> dict[str, Any]:
    return {
        "mysqlId": chain.id,
        "farmId": chain.farm_id,
        "chainId": chain.chain_id,
        "sessionId": chain.session_id,
        "triggerTurnId": chain.trigger_turn_id,
        "contextTurnIds": _json_value(chain.context_turn_ids),
        "resultTurnIds": _json_value(chain.result_turn_ids),
        "status": chain.status,
        "severity": chain.severity,
        "dominantSignal": chain.dominant_signal,
        "finalLabels": _json_value(chain.final_labels),
        "sourceLabelIds": _json_value(chain.source_label_ids),
        "rootCause": chain.root_cause,
        "expectedBehavior": chain.expected_behavior,
        "fixTarget": chain.fix_target,
        "reviewerComment": chain.reviewer_comment,
        "falsePositiveReason": chain.false_positive_reason,
        "missingEvidence": _json_value(chain.missing_evidence),
        "aiJudge": _json_value(chain.ai_judge),
        "reviewerId": chain.reviewer_id,
        "reviewedAt": chain.reviewed_at,
        "createdAt": chain.created_at,
        "updatedAt": chain.updated_at,
    }


def review_issue_chain_from_mongo_doc(doc: Mapping[str, Any]) -> AgentReviewIssueChain:
    return _model_from_doc(
        AgentReviewIssueChain,
        doc,
        {
            "farmId": "farm_id",
            "chainId": "chain_id",
            "sessionId": "session_id",
            "triggerTurnId": "trigger_turn_id",
            "contextTurnIds": "context_turn_ids",
            "resultTurnIds": "result_turn_ids",
            "status": "status",
            "severity": "severity",
            "dominantSignal": "dominant_signal",
            "finalLabels": "final_labels",
            "sourceLabelIds": "source_label_ids",
            "rootCause": "root_cause",
            "expectedBehavior": "expected_behavior",
            "fixTarget": "fix_target",
            "reviewerComment": "reviewer_comment",
            "falsePositiveReason": "false_positive_reason",
            "missingEvidence": "missing_evidence",
            "aiJudge": "ai_judge",
            "reviewerId": "reviewer_id",
            "reviewedAt": "reviewed_at",
            "createdAt": "created_at",
            "updatedAt": "updated_at",
        },
        json_fields={
            "contextTurnIds",
            "resultTurnIds",
            "finalLabels",
            "sourceLabelIds",
            "missingEvidence",
            "aiJudge",
        },
    )


def prelabel_to_mongo_doc(prelabel: AgentDataFlywheelPrelabel) -> dict[str, Any]:
    return {
        "mysqlId": prelabel.id,
        "farmId": prelabel.farm_id,
        "sampleId": prelabel.sample_id,
        "sampleType": prelabel.sample_type,
        "sessionId": prelabel.session_id,
        "turnId": prelabel.turn_id,
        "requestId": prelabel.request_id,
        "source": prelabel.source,
        "status": prelabel.status,
        "labels": _json_value(prelabel.labels),
        "rootCause": prelabel.root_cause,
        "severity": prelabel.severity,
        "confidence": prelabel.confidence,
        "reason": prelabel.reason,
        "recommendedFix": prelabel.recommended_fix,
        "judgeModel": prelabel.judge_model,
        "promptVersion": prelabel.prompt_version,
        "rawResponse": _json_value(prelabel.raw_response),
        "acceptedLabelIds": _json_value(prelabel.accepted_label_ids),
        "reviewedBy": prelabel.reviewed_by,
        "reviewedAt": prelabel.reviewed_at,
        "createdAt": prelabel.created_at,
        "updatedAt": prelabel.updated_at,
    }


def prelabel_from_mongo_doc(doc: Mapping[str, Any]) -> AgentDataFlywheelPrelabel:
    return _model_from_doc(
        AgentDataFlywheelPrelabel,
        doc,
        {
            "farmId": "farm_id",
            "sampleId": "sample_id",
            "sampleType": "sample_type",
            "sessionId": "session_id",
            "turnId": "turn_id",
            "requestId": "request_id",
            "source": "source",
            "status": "status",
            "labels": "labels",
            "rootCause": "root_cause",
            "severity": "severity",
            "confidence": "confidence",
            "reason": "reason",
            "recommendedFix": "recommended_fix",
            "judgeModel": "judge_model",
            "promptVersion": "prompt_version",
            "rawResponse": "raw_response",
            "acceptedLabelIds": "accepted_label_ids",
            "reviewedBy": "reviewed_by",
            "reviewedAt": "reviewed_at",
            "createdAt": "created_at",
            "updatedAt": "updated_at",
        },
        json_fields={"labels", "rawResponse", "acceptedLabelIds"},
    )
