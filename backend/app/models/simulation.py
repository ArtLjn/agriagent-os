"""仿真测试运行记录模型。"""

import json

from sqlalchemy import Column, DateTime, Integer, String, Text, func

from app.core.database import Base


class SimulationRun(Base):
    """仿真测试运行记录。"""

    __tablename__ = "simulation_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(32), unique=True, nullable=False, index=True)
    farm_id = Column(Integer, nullable=False, default=1)
    status = Column(String(16), nullable=False, default="running")
    total = Column(Integer, nullable=False, default=0)
    passed = Column(Integer, nullable=False, default=0)
    failed = Column(Integer, nullable=False, default=0)
    profile = Column(String(32), nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SimulationResultRecord(Base):
    """单个用例执行结果。"""

    __tablename__ = "simulation_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(32), nullable=False, index=True)
    farm_id = Column(Integer, nullable=False, default=1)
    case_id = Column(String(64), nullable=False)
    passed = Column(Integer, nullable=False, default=0)
    agent_reply = Column(Text, nullable=True)
    errors_json = Column(Text, nullable=True)
    db_diff_json = Column(Text, nullable=True)
    extracted_claims_json = Column(Text, nullable=True)
    latency_ms = Column(Integer, nullable=False, default=0)
    category = Column(String(32), nullable=True)
    user_input = Column(Text, nullable=True)
    pending_action_json = Column(Text, nullable=True)
    expected_db_changes_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    @property
    def errors(self):
        return json.loads(self.errors_json) if self.errors_json else []

    @errors.setter
    def errors(self, value):
        self.errors_json = json.dumps(value, ensure_ascii=False) if value else None

    @property
    def db_diff(self):
        return json.loads(self.db_diff_json) if self.db_diff_json else {}

    @db_diff.setter
    def db_diff(self, value):
        self.db_diff_json = json.dumps(value, ensure_ascii=False) if value else None

    @property
    def extracted_claims(self):
        return (
            json.loads(self.extracted_claims_json) if self.extracted_claims_json else []
        )

    @extracted_claims.setter
    def extracted_claims(self, value):
        self.extracted_claims_json = (
            json.dumps(value, ensure_ascii=False) if value else None
        )

    @property
    def pending_action(self):
        return (
            json.loads(self.pending_action_json) if self.pending_action_json else None
        )

    @pending_action.setter
    def pending_action(self, value):
        self.pending_action_json = (
            json.dumps(value, ensure_ascii=False) if value else None
        )

    @property
    def expected_db_changes(self):
        return (
            json.loads(self.expected_db_changes_json)
            if self.expected_db_changes_json
            else {}
        )

    @expected_db_changes.setter
    def expected_db_changes(self, value):
        self.expected_db_changes_json = (
            json.dumps(value, ensure_ascii=False) if value else None
        )
