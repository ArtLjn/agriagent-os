"""agent session flywheel storage

Revision ID: 20260611_agent_session_flywheel
Revises: a3f1c9d8e7b4
Create Date: 2026-06-11 10:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "20260611_agent_session_flywheel"
down_revision: Union[str, None] = "a3f1c9d8e7b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    _add_conversation_columns(inspector)
    _add_message_columns(inspector)
    _create_agent_turns(inspector)
    _create_pending_plan_tables(inspector)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    _drop_pending_plan_tables(inspector)
    _drop_agent_turns(inspector)
    _drop_message_columns(inspector)
    _drop_conversation_columns(inspector)


def _columns(inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _tables(inspector) -> set[str]:
    return set(inspector.get_table_names())


def _add_conversation_columns(inspector) -> None:
    columns = _columns(inspector, "conversations")
    if "summary" not in columns:
        op.add_column("conversations", sa.Column("summary", sa.Text(), nullable=True))
    if "summary_updated_at" not in columns:
        op.add_column("conversations", sa.Column("summary_updated_at", sa.DateTime(), nullable=True))
    if "last_turn_id" not in columns:
        op.add_column("conversations", sa.Column("last_turn_id", sa.Integer(), nullable=True))
    if "last_event_seq" not in columns:
        op.add_column("conversations", sa.Column("last_event_seq", sa.Integer(), nullable=True))
    if "meta_json" not in columns:
        op.add_column("conversations", sa.Column("meta_json", sa.JSON(), nullable=True))


def _drop_conversation_columns(inspector) -> None:
    columns = _columns(inspector, "conversations")
    for column in ["meta_json", "last_event_seq", "last_turn_id", "summary_updated_at", "summary"]:
        if column in columns:
            op.drop_column("conversations", column)


def _add_message_columns(inspector) -> None:
    columns = _columns(inspector, "conversation_messages")
    indexes = {index["name"] for index in inspector.get_indexes("conversation_messages")}
    if "turn_id" not in columns:
        op.add_column("conversation_messages", sa.Column("turn_id", sa.Integer(), nullable=True))
    if "ix_conversation_messages_turn_id" not in indexes:
        op.create_index("ix_conversation_messages_turn_id", "conversation_messages", ["turn_id"])
    if "content_hash" not in columns:
        op.add_column("conversation_messages", sa.Column("content_hash", sa.String(length=64), nullable=True))
    if "meta_json" not in columns:
        op.add_column("conversation_messages", sa.Column("meta_json", sa.JSON(), nullable=True))


def _drop_message_columns(inspector) -> None:
    columns = _columns(inspector, "conversation_messages")
    indexes = {index["name"] for index in inspector.get_indexes("conversation_messages")}
    if "ix_conversation_messages_turn_id" in indexes:
        op.drop_index("ix_conversation_messages_turn_id", table_name="conversation_messages")
    for column in ["meta_json", "content_hash", "turn_id"]:
        if column in columns:
            op.drop_column("conversation_messages", column)


def _create_agent_turns(inspector) -> None:
    if "agent_turns" in _tables(inspector):
        return
    op.create_table(
        "agent_turns",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("farm_id", sa.Integer(), sa.ForeignKey("farms.id"), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=True),
        sa.Column("request_id", sa.String(length=16), nullable=False),
        sa.Column("user_message_id", sa.Integer(), sa.ForeignKey("conversation_messages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("assistant_message_id", sa.Integer(), sa.ForeignKey("conversation_messages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("input_preview", sa.Text(), nullable=True),
        sa.Column("reply_preview", sa.Text(), nullable=True),
        sa.Column("intent_count", sa.Integer(), nullable=True),
        sa.Column("selected_tools_count", sa.Integer(), nullable=True),
        sa.Column("tool_calls_count", sa.Integer(), nullable=True),
        sa.Column("token_total", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="success"),
        sa.Column("pending_plan_id", sa.String(length=64), nullable=True),
        sa.Column("event_file", sa.Text(), nullable=True),
        sa.Column("event_seq_start", sa.Integer(), nullable=True),
        sa.Column("event_seq_end", sa.Integer(), nullable=True),
        sa.Column("event_write_status", sa.String(length=20), nullable=False, server_default="not_started"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_agent_turns_farm_id", "agent_turns", ["farm_id"])
    op.create_index("ix_agent_turns_session_id", "agent_turns", ["session_id"])
    op.create_index("ix_agent_turns_request_id", "agent_turns", ["request_id"])
    op.create_index("ix_agent_turns_conversation_id", "agent_turns", ["conversation_id"])
    op.create_index("ix_agent_turns_created_at", "agent_turns", ["created_at"])
    op.create_index("ix_agent_turns_pending_plan_id", "agent_turns", ["pending_plan_id"])


def _drop_agent_turns(inspector) -> None:
    if "agent_turns" in _tables(inspector):
        op.drop_table("agent_turns")


def _create_pending_plan_tables(inspector) -> None:
    tables = _tables(inspector)
    if "agent_pending_plans" not in tables:
        op.create_table(
            "agent_pending_plans",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("plan_id", sa.String(length=64), nullable=False, unique=True),
            sa.Column("farm_id", sa.Integer(), sa.ForeignKey("farms.id"), nullable=False),
            sa.Column("session_id", sa.String(length=64), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
            sa.Column("current_step_index", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("raw_user_input", sa.Text(), nullable=True),
            sa.Column("router_decision_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("expires_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_agent_pending_plans_plan_id", "agent_pending_plans", ["plan_id"], unique=True)
        op.create_index("ix_agent_pending_plans_farm_id", "agent_pending_plans", ["farm_id"])
        op.create_index("ix_agent_pending_plans_session_id", "agent_pending_plans", ["session_id"])
        op.create_index("ix_agent_pending_plans_status", "agent_pending_plans", ["status"])
        op.create_index("ix_agent_pending_plans_expires_at", "agent_pending_plans", ["expires_at"])
    else:
        _upgrade_existing_pending_plans(inspector)
    if "agent_pending_plan_steps" not in tables:
        op.create_table(
            "agent_pending_plan_steps",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("plan_id", sa.String(length=64), nullable=False),
            sa.Column("step_index", sa.Integer(), nullable=False),
            sa.Column("skill_name", sa.String(length=100), nullable=False),
            sa.Column("params_json", sa.JSON(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
            sa.Column("requires_confirmation", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("confirmation_text", sa.Text(), nullable=True),
            sa.Column("result_json", sa.JSON(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_agent_pending_plan_steps_plan_id", "agent_pending_plan_steps", ["plan_id"])
        op.create_index("ix_agent_pending_plan_steps_skill_name", "agent_pending_plan_steps", ["skill_name"])
        op.create_index("ix_agent_pending_plan_steps_status", "agent_pending_plan_steps", ["status"])
    else:
        _upgrade_existing_pending_plan_steps(inspector)


def _upgrade_existing_pending_plans(inspector) -> None:
    columns = _columns(inspector, "agent_pending_plans")
    indexes = {index["name"] for index in inspector.get_indexes("agent_pending_plans")}
    if "router_decision_json" not in columns:
        op.add_column("agent_pending_plans", sa.Column("router_decision_json", sa.JSON(), nullable=True))
        if "router_decision" in columns:
            op.execute("UPDATE agent_pending_plans SET router_decision_json = router_decision")
    if "ix_agent_pending_plans_status" not in indexes:
        op.create_index("ix_agent_pending_plans_status", "agent_pending_plans", ["status"])
    if "ix_agent_pending_plans_expires_at" not in indexes:
        op.create_index("ix_agent_pending_plans_expires_at", "agent_pending_plans", ["expires_at"])


def _upgrade_existing_pending_plan_steps(inspector) -> None:
    columns = _columns(inspector, "agent_pending_plan_steps")
    indexes = {index["name"] for index in inspector.get_indexes("agent_pending_plan_steps")}
    if "skill_name" not in columns:
        op.add_column("agent_pending_plan_steps", sa.Column("skill_name", sa.String(length=100), nullable=True))
        if "tool_name" in columns:
            op.execute("UPDATE agent_pending_plan_steps SET skill_name = tool_name")
    if "params_json" not in columns:
        op.add_column("agent_pending_plan_steps", sa.Column("params_json", sa.JSON(), nullable=True))
        if "params" in columns:
            op.execute("UPDATE agent_pending_plan_steps SET params_json = params")
    if "status" not in columns:
        op.add_column(
            "agent_pending_plan_steps",
            sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        )
        if "execution_status" in columns:
            op.execute("UPDATE agent_pending_plan_steps SET status = execution_status")
    if "requires_confirmation" not in columns:
        op.add_column(
            "agent_pending_plan_steps",
            sa.Column("requires_confirmation", sa.Boolean(), nullable=False, server_default=sa.true()),
        )
    if "confirmation_text" not in columns:
        op.add_column("agent_pending_plan_steps", sa.Column("confirmation_text", sa.Text(), nullable=True))
    if "result_json" not in columns:
        op.add_column("agent_pending_plan_steps", sa.Column("result_json", sa.JSON(), nullable=True))
        if "result_payload" in columns:
            op.execute("UPDATE agent_pending_plan_steps SET result_json = result_payload")
    if "error_message" not in columns:
        op.add_column("agent_pending_plan_steps", sa.Column("error_message", sa.Text(), nullable=True))
        if "error_payload" in columns:
            op.execute("UPDATE agent_pending_plan_steps SET error_message = CAST(error_payload AS CHAR)")
    indexes = {index["name"] for index in inspector.get_indexes("agent_pending_plan_steps")}
    if "ix_agent_pending_plan_steps_skill_name" not in indexes:
        op.create_index("ix_agent_pending_plan_steps_skill_name", "agent_pending_plan_steps", ["skill_name"])
    if "ix_agent_pending_plan_steps_status" not in indexes:
        op.create_index("ix_agent_pending_plan_steps_status", "agent_pending_plan_steps", ["status"])


def _drop_pending_plan_tables(inspector) -> None:
    tables = _tables(inspector)
    if "agent_pending_plan_steps" in tables:
        op.drop_table("agent_pending_plan_steps")
    if "agent_pending_plans" in tables:
        op.drop_table("agent_pending_plans")
