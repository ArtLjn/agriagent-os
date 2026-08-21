"""Conversation snapshot 迁移校验与只创建不覆盖测试。"""

from agent.platforms.persistence.mongo.migration import (
    build_migration_report,
    build_state_candidate,
    validate_snapshot,
)


def _messages() -> list[dict]:
    return [
        {
            "userId": "user-1",
            "farmId": 1,
            "conversationId": "conversation-1",
            "turnId": "turn-1",
            "role": "user",
            "content": "查询天气",
        },
        {
            "userId": "user-1",
            "farmId": 1,
            "conversationId": "conversation-1",
            "turnId": "turn-1",
            "role": "assistant",
            "content": "天气晴朗",
        },
    ]


def test_migration_candidate_contains_state_only_and_no_message_content() -> None:
    candidate = build_state_candidate(_messages())

    assert candidate["conversationRevision"] == 1
    assert "content" not in candidate
    assert candidate["migration"]["messageCount"] == 2


def test_migration_report_does_not_overwrite_existing_state() -> None:
    report = build_migration_report(
        _messages(),
        [
            {
                "userId": "user-1",
                "farmId": 1,
                "conversationId": "conversation-1",
                "conversationRevision": 5,
            }
        ],
    )

    assert report["entries"][0]["action"] == "validate_only"
    assert report["entries"][0]["candidate"] is None
    assert report["delete_performed"] is False
    assert report["rollback"]["can_rollback"] is True
    assert "conversationMessages" in report["rollback"]["protected_collections"]


def test_migration_marks_incomplete_turn_as_divergence() -> None:
    validation = validate_snapshot(_messages()[:-1])

    assert validation.divergent is True
    assert "incomplete_turn" in validation.issue_codes
