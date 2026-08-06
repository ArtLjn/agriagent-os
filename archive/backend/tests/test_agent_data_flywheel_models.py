"""Agent 数据飞轮模型测试。"""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.shared.database import Base
from app.platforms.data_flywheel.models import (
    AgentCaseDraft,
    AgentDataFlywheelLabel,
    AgentDataFlywheelPrelabel,
    AgentRepairPack,
    AgentReviewIssueChain,
)
from app.domains.farm.models import Farm

pytestmark = pytest.mark.no_db


def _set_sqlite_pragma(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


_engine = create_engine(
    "sqlite:///tests/test_agent_data_flywheel_models.db",
    connect_args={"check_same_thread": False},
)
event.listen(_engine, "connect", _set_sqlite_pragma)
Session = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def setup_function():
    Base.metadata.drop_all(bind=_engine)
    Base.metadata.create_all(bind=_engine)
    db = Session()
    db.add(Farm(id=1, name="默认农场", user_id="user-1"))
    db.commit()
    db.close()


def test_agent_data_flywheel_label_round_trip():
    db = Session()
    label = AgentDataFlywheelLabel(
        farm_id=1,
        sample_id="turn:1:sess-1:12",
        sample_type="session_turn",
        session_id="sess-1",
        turn_id=12,
        request_id="abcd1234",
        label="wrong_tool_selection",
        comment="选了写工具但实际只需要查询",
        annotator_id="admin-1",
    )
    db.add(label)
    db.commit()
    db.refresh(label)

    loaded = db.query(AgentDataFlywheelLabel).filter_by(id=label.id).one()

    assert loaded.id is not None
    assert loaded.sample_id == "turn:1:sess-1:12"
    assert loaded.label == "wrong_tool_selection"
    assert loaded.comment == "选了写工具但实际只需要查询"
    assert loaded.created_at is not None
    assert loaded.updated_at is not None
    db.close()


def test_agent_case_draft_round_trip():
    db = Session()
    case_json = {
        "case_id": "regression-sess-1-12",
        "description": "王大妈工资缺失回归",
        "user_input": "王大妈工资 100 一天",
        "reply_assertions": [{"contains": "100"}],
        "metadata": {"source_sample_id": "turn:1:sess-1:12"},
    }
    draft = AgentCaseDraft(
        farm_id=1,
        draft_id="draft-abc123",
        source_sample_id="turn:1:sess-1:12",
        target_type="evaluation_replay",
        status="draft",
        case_json=case_json,
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)

    loaded = db.query(AgentCaseDraft).filter_by(draft_id="draft-abc123").one()

    assert loaded.id is not None
    assert loaded.source_sample_id == "turn:1:sess-1:12"
    assert loaded.target_type == "evaluation_replay"
    assert loaded.status == "draft"
    assert loaded.case_json["case_id"] == "regression-sess-1-12"
    assert loaded.case_json["description"] == "王大妈工资缺失回归"
    assert loaded.case_json["user_input"] == "王大妈工资 100 一天"
    assert loaded.case_json["reply_assertions"] == [{"contains": "100"}]
    assert loaded.case_json["metadata"]["source_sample_id"] == "turn:1:sess-1:12"
    assert loaded.created_at is not None
    assert loaded.updated_at is not None
    db.close()


def test_agent_data_flywheel_prelabel_round_trip():
    db = Session()
    prelabel = AgentDataFlywheelPrelabel(
        farm_id=1,
        sample_id="turn:1:sess-1:12",
        sample_type="session_turn",
        session_id="sess-1",
        turn_id=12,
        request_id="abcd1234",
        source="llm_judge",
        status="pending",
        labels=["bad_reply", "pending_missed"],
        root_cause="写操作缺少 pending 确认",
        severity="high",
        confidence=0.86,
        reason="回复声称已安排，但证据中没有完整确认链路。",
        recommended_fix="写操作必须先创建 pending plan。",
        judge_model="gpt-4.1-mini",
        prompt_version="data-flywheel-prelabel-v1",
        raw_response={"labels": ["bad_reply", "pending_missed"]},
    )
    db.add(prelabel)
    db.commit()
    db.refresh(prelabel)

    loaded = db.query(AgentDataFlywheelPrelabel).filter_by(id=prelabel.id).one()

    assert loaded.id is not None
    assert loaded.source == "llm_judge"
    assert loaded.status == "pending"
    assert loaded.labels == ["bad_reply", "pending_missed"]
    assert loaded.root_cause == "写操作缺少 pending 确认"
    assert loaded.severity == "high"
    assert loaded.confidence == 0.86
    assert loaded.accepted_label_ids is None
    assert loaded.reviewed_by is None
    assert loaded.reviewed_at is None
    assert loaded.created_at is not None
    assert loaded.updated_at is not None
    db.close()


def test_agent_repair_pack_round_trip():
    db = Session()
    pack = AgentRepairPack(
        farm_id=1,
        pack_id="repair-pending-plan-abc123",
        fix_target="pending_plan",
        labels=["pending_missed", "needs_regression"],
        source_sample_ids=["turn:1:sess-1:12"],
        source_label_ids=[1, 2],
        status="draft",
        export_path="data/repair-packs/repair-pending-plan-abc123",
        manifest_json={"goal": "写操作必须先创建 pending plan"},
        export_error=None,
        created_by="admin-1",
    )
    db.add(pack)
    db.commit()
    db.refresh(pack)

    loaded = db.query(AgentRepairPack).filter_by(pack_id=pack.pack_id).one()

    assert loaded.id is not None
    assert loaded.fix_target == "pending_plan"
    assert loaded.labels == ["pending_missed", "needs_regression"]
    assert loaded.source_label_ids == [1, 2]
    assert loaded.source_sample_ids == ["turn:1:sess-1:12"]
    assert loaded.status == "draft"
    assert loaded.manifest_json["goal"] == "写操作必须先创建 pending plan"
    assert loaded.created_at is not None
    assert loaded.updated_at is not None
    db.close()


def test_agent_review_issue_chain_round_trip():
    db = Session()
    chain = AgentReviewIssueChain(
        farm_id=1,
        chain_id="chain:1:sess-1:12",
        session_id="sess-1",
        trigger_turn_id=12,
        context_turn_ids=[9, 10, 11],
        result_turn_ids=[13],
        status="accepted",
        severity="P0",
        dominant_signal="rule",
        final_labels=["needs_regression", "tool_parameter_mismatch"],
        source_label_ids=[1, 2],
        root_cause="批量意图被参数抽取收窄为单人",
        expected_behavior="确认批量结算时应保留所有待结算工人的作用域。",
        false_positive_reason=None,
        missing_evidence=None,
        reviewer_id="admin-1",
    )
    db.add(chain)
    db.commit()
    db.refresh(chain)

    loaded = (
        db.query(AgentReviewIssueChain)
        .filter_by(farm_id=1, chain_id="chain:1:sess-1:12")
        .one()
    )

    assert loaded.id is not None
    assert loaded.context_turn_ids == [9, 10, 11]
    assert loaded.result_turn_ids == [13]
    assert loaded.status == "accepted"
    assert loaded.final_labels == ["needs_regression", "tool_parameter_mismatch"]
    assert loaded.source_label_ids == [1, 2]
    assert loaded.root_cause == "批量意图被参数抽取收窄为单人"
    assert loaded.expected_behavior == "确认批量结算时应保留所有待结算工人的作用域。"
    assert loaded.reviewer_id == "admin-1"
    assert loaded.created_at is not None
    assert loaded.updated_at is not None
    db.close()
