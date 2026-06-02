from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Claim:
    """从 LLM 回复中提取的声称操作。"""

    op_type: str
    description: str
    keywords_matched: list[str]


@dataclass
class SimulationTestCase:
    """单个仿真测试用例。"""

    case_id: str
    description: str
    user_input: str
    expected_response_matches: list[str]
    expected_db_changes: dict[str, dict]
    verify_tables: list[str]
    category: str = "basic"
    precondition: dict = field(default_factory=dict)


@dataclass
class DbDiff:
    """数据库状态差异。"""

    added: list[dict] = field(default_factory=list)
    removed: list[dict] = field(default_factory=list)
    modified: list[dict] = field(default_factory=list)

    def has_changes_for_table(self, table: str) -> bool:
        """检查指定表是否有变化。"""
        for record in self.added + self.removed + self.modified:
            if record.get("__table__") == table:
                return True
        return False


@dataclass
class SimulationResult:
    """单个测试用例的执行结果。"""

    case_id: str
    passed: bool
    agent_reply: str = ""
    errors: list[str] = field(default_factory=list)
    db_diff: DbDiff = field(default_factory=lambda: DbDiff())
    extracted_claims: list[Claim] = field(default_factory=list)
    latency_ms: int = 0
    category: str = "basic"
    run_id: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    user_input: str = ""
    pending_action: dict | None = None
    expected_db_changes: dict[str, dict] = field(default_factory=dict)
    skill_traces: list[dict] = field(default_factory=list)


@dataclass
class SimulationReport:
    """批量测试的报告。"""

    run_id: str
    total: int
    passed: int
    failed: int
    accuracy: float
    avg_latency_ms: float
    failure_breakdown: dict[str, int] = field(default_factory=dict)
    results: list[SimulationResult] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
