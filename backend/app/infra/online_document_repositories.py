"""第 2 期在线文档对象 Repository 公开入口。"""

from __future__ import annotations

from app.infra.online_document_agent_record import (
    DualWriteAgentRecordRepository,
    MongoAgentRecordRepository,
    MongoReadAgentRecordRepository,
    MySQLAgentRecordRepository,
    build_agent_record_repository,
)
from app.infra.online_document_common import (
    AgentRecordRepository,
    ConversationMessageRepository,
    GuardrailsLogRepository,
    RepositoryPage,
)
from app.infra.online_document_conversation import (
    DualWriteConversationMessageRepository,
    MongoConversationMessageRepository,
    MongoReadConversationMessageRepository,
    MySQLConversationMessageRepository,
    build_conversation_message_repository,
)
from app.infra.online_document_guardrails import (
    DualWriteGuardrailsLogRepository,
    MongoGuardrailsLogRepository,
    MongoReadGuardrailsLogRepository,
    MySQLGuardrailsLogRepository,
    build_guardrails_log_repository,
)

__all__ = [
    "AgentRecordRepository",
    "ConversationMessageRepository",
    "DualWriteAgentRecordRepository",
    "DualWriteConversationMessageRepository",
    "DualWriteGuardrailsLogRepository",
    "GuardrailsLogRepository",
    "MongoAgentRecordRepository",
    "MongoConversationMessageRepository",
    "MongoGuardrailsLogRepository",
    "MongoReadAgentRecordRepository",
    "MongoReadConversationMessageRepository",
    "MongoReadGuardrailsLogRepository",
    "MySQLAgentRecordRepository",
    "MySQLConversationMessageRepository",
    "MySQLGuardrailsLogRepository",
    "RepositoryPage",
    "build_agent_record_repository",
    "build_conversation_message_repository",
    "build_guardrails_log_repository",
]
