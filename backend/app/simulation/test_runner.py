"""仿真测试执行引擎。"""

import asyncio
import json
import logging
import time
from pathlib import Path

from sqlalchemy.orm import Session

from app.simulation.models import (
    Claim,
    SimulationResult,
    SimulationTestCase,
)
from app.simulation.state_snapshot import DbStateSnapshot
from app.simulation.agent_client import AgentClient
from app.simulation.semantic_extractor import extract_claims, get_table_for_op
from app.simulation.consistency_checker import check_consistency

logger = logging.getLogger(__name__)

CASES_DIR = Path(__file__).parent.parent.parent / "data" / "simulation_cases"

# skill_name 到 op_type 的映射（pending_action 场景使用）
_SKILL_NAME_TO_OP_TYPE: dict[str, str] = {
    "create_cost_record": "create_cost",
    "create_crop_template": "create_template",
    "create_crop_cycle": "create_cycle",
    "update_cycle_stage": "update_stage",
    "log_farm_activity": "log_activity",
    "settle_debt": "settle_debt",
}


class SimulationRunner:
    """仿真测试执行引擎。"""

    def __init__(
        self,
        agent_client: AgentClient,
        db: Session,
        farm_id: int = 1,
    ):
        self._agent = agent_client
        self._db = db
        self._farm_id = farm_id
        self._snapshot = DbStateSnapshot(db, farm_id)

    def load_cases(self, category: str | None = None) -> list[SimulationTestCase]:
        """
        从 data/simulation_cases/*.json 加载测试用例。
        每个 JSON 文件是一个数组，包含多个用例。
        如果指定 category，只加载该分类的用例。
        """
        cases: list[SimulationTestCase] = []
        if not CASES_DIR.exists():
            logger.warning("测试用例目录不存在: %s", CASES_DIR)
            return cases

        for file_path in CASES_DIR.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    raw_cases = json.load(f)
                if not isinstance(raw_cases, list):
                    logger.warning("跳过非数组文件: %s", file_path)
                    continue
                for raw in raw_cases:
                    case = self._parse_case(raw)
                    if category is None or case.category == category:
                        cases.append(case)
            except json.JSONDecodeError:
                logger.warning("JSON 解析失败，跳过: %s", file_path)
            except Exception:
                logger.exception("加载用例文件失败: %s", file_path)

        logger.info("加载 %d 个测试用例", len(cases))
        return cases

    @staticmethod
    def _parse_case(raw: dict) -> SimulationTestCase:
        """将 JSON 原始数据解析为 SimulationTestCase。"""
        return SimulationTestCase(
            case_id=raw["case_id"],
            description=raw["description"],
            user_input=raw["user_input"],
            expected_response_matches=raw.get("expected_response_matches", []),
            expected_db_changes=raw.get("expected_db_changes", {}),
            verify_tables=raw.get("verify_tables", []),
            category=raw.get("category", "basic"),
            precondition=raw.get("precondition", {}),
        )

    async def run_single(
        self, case: SimulationTestCase, run_id: str = ""
    ) -> SimulationResult:
        """
        执行单个测试用例：
        1. 前置条件 setup（如果有 precondition）
        2. before 快照
        3. 调用 Agent /agent/chat
        4. 如果有 pending_action，发送确认
        5. after 快照（等待 200ms 确保异步操作完成）
        6. 语义提取 + 一致性检查
        7. 返回 SimulationResult
        """
        start_time = time.perf_counter()
        logger.info("执行用例 [%s]: %s", case.case_id, case.description)

        if case.precondition:
            self._setup_precondition(case.precondition)

        before = await self._snapshot.take(case.verify_tables)

        agent_response = await self._agent.send_message(case.user_input)
        reply = agent_response.get("reply", "")
        pending = agent_response.get("pending_action")
        combined_reply = reply

        if pending:
            action_id = pending.get("action_id", "")
            session_id = pending.get("session_id", "")
            logger.info("用例 [%s] 发现 pending_action，发送确认", case.case_id)
            confirm_response = await self._agent.send_confirm(session_id, action_id)
            confirm_reply = confirm_response.get("reply", "")
            reply = confirm_reply
            combined_reply = f"{combined_reply} {confirm_reply}"

        await asyncio.sleep(0.2)
        after = await self._snapshot.take(case.verify_tables)
        db_diff = self._snapshot.compute_diff(before, after)

        claims = extract_claims(combined_reply)

        if pending and not claims:
            skill_name = pending.get("skill_name", "")
            op_type = _SKILL_NAME_TO_OP_TYPE.get(skill_name, skill_name)
            table = get_table_for_op(op_type)
            if table:
                claims.append(
                    Claim(
                        op_type=op_type,
                        description=f"pending_action: {skill_name}",
                        keywords_matched=["pending_action"],
                    )
                )

        errors = check_consistency(combined_reply, claims, db_diff, case)
        passed = len(errors) == 0

        latency_ms = int((time.perf_counter() - start_time) * 1000)

        logger.info(
            "用例 [%s] 结果: %s, 延迟 %dms, 错误 %d 条",
            case.case_id,
            "通过" if passed else "失败",
            latency_ms,
            len(errors),
        )

        return SimulationResult(
            case_id=case.case_id,
            passed=passed,
            agent_reply=reply,
            errors=errors,
            db_diff=db_diff,
            extracted_claims=claims,
            latency_ms=latency_ms,
            category=case.category,
            run_id=run_id,
        )

    async def run_batch(
        self, cases: list[SimulationTestCase], run_id: str = ""
    ) -> list[SimulationResult]:
        """批量执行测试用例。"""
        results: list[SimulationResult] = []
        for case in cases:
            try:
                result = await self.run_single(case, run_id=run_id)
                results.append(result)
            except Exception:
                logger.exception("用例 [%s] 执行异常", case.case_id)
                results.append(
                    SimulationResult(
                        case_id=case.case_id,
                        passed=False,
                        errors=["runner_exception: 执行引擎异常"],
                        category=case.category,
                        run_id=run_id,
                    )
                )
        return results

    def _setup_precondition(self, precondition: dict) -> None:
        """
        设置前置条件。
        例如：precondition = {"ensure_template_exists": "西瓜"} — 确保西瓜模板已存在。
        目前先实现空方法，留扩展接口。
        """
        logger.info("设置前置条件: %s", precondition)
