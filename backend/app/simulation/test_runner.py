"""仿真测试执行引擎。"""

import asyncio
import json
import logging
import time
from pathlib import Path

from sqlalchemy import text
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
    "manage_farm_logs": "log_activity",
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

        session_id = f"sim-{case.case_id}-{int(time.time())}"
        agent_response = await self._agent.send_message(
            case.user_input, session_id=session_id
        )
        reply = agent_response.get("reply", "")
        pending = agent_response.get("pending_action")
        combined_reply = reply

        if pending:
            action_id = pending.get("action_id", "")
            has_expected_changes = bool(case.expected_db_changes)
            if has_expected_changes:
                logger.info("用例 [%s] pending_action，发送确认", case.case_id)
                confirm_response = await self._agent.send_confirm(session_id, action_id)
                confirm_reply = confirm_response.get("reply", "")
                reply = confirm_reply
                combined_reply = f"{combined_reply} {confirm_reply}"
            else:
                logger.info("用例 [%s] pending_action，发送取消", case.case_id)
                cancel_response = await self._agent.send_cancel(session_id, action_id)
                cancel_reply = cancel_response.get("reply", "")
                reply = cancel_reply
                combined_reply = f"{combined_reply} {cancel_reply}"

        await asyncio.sleep(0.2)
        # 刷新 Session 缓存，确保能看到其他 Session 提交的数据
        if self._db:
            self._db.expire_all()
        after = await self._snapshot.take(case.verify_tables)
        db_diff = self._snapshot.compute_diff(before, after)

        # 强制 flush trace 到数据库
        skill_traces: list[dict] = []
        if self._db:
            from app.infra.trace_collector import get_trace_dao

            dao = get_trace_dao()
            if dao:
                await dao.flush_now()

            # 查询该 session 的 skill_call trace
            from app.models.trace import TraceRecord

            records = (
                self._db.query(TraceRecord)
                .filter(
                    TraceRecord.session_id == session_id,
                    TraceRecord.node_type == "skill_call",
                )
                .all()
            )
            skill_traces = [
                {
                    "node_name": r.node_name,
                    "status": r.status,
                    "error_message": r.error_message,
                    "input_data": r.input_data,
                    "output_data": r.output_data,
                }
                for r in records
            ]

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

        errors = check_consistency(
            combined_reply, claims, db_diff, case, pending, skill_traces
        )
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
            user_input=case.user_input,
            pending_action=pending,
            expected_db_changes=case.expected_db_changes,
            skill_traces=skill_traces,
        )

    async def run_batch(
        self, cases: list[SimulationTestCase], run_id: str = ""
    ) -> list[SimulationResult]:
        """批量执行测试用例。

        每两个用例之间延迟 12 秒，避免触发 /agent/chat 的 10/min 限流。
        每个用例最多 2 次请求（初始 + confirm/cancel），12 秒延迟确保
        平均速率低于 10/分钟。
        """
        results: list[SimulationResult] = []
        for i, case in enumerate(cases):
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
            # 限流保护：避免连续请求触发 429
            # 每个用例最多 2 次请求，12 秒间隔确保 < 10/min
            if i < len(cases) - 1:
                await asyncio.sleep(12)
        return results

    def _setup_precondition(self, precondition: dict) -> None:
        """
        设置前置条件。
        目前支持：
        - clean_tables: ["table1", "table2"] — 删除指定表中当前 farm_id 的数据
        - ensure_template_exists: "作物名" — 确保作物模板已存在（预留接口）
        """
        logger.info("设置前置条件: %s", precondition)

        clean_tables = precondition.get("clean_tables", [])
        if clean_tables:
            self._clean_tables(clean_tables)

    def _clean_tables(self, tables: list[str]) -> None:
        """删除指定表中与当前 farm_id 关联的数据。

        按外键依赖顺序删除：先删子表（被引用的），再删父表（引用的），
        避免 FOREIGN KEY constraint failed。
        """
        # 外键依赖深度：子表（被引用方）先删，父表（引用方）后删
        _DELETE_ORDER = {
            "growth_stages": 0,  # 子表：引用 crop_templates
            "cycle_stages": 0,  # 子表：引用 crop_cycles
            "cost_records": 1,
            "crop_templates": 1,  # 父表：被 growth_stages 引用
            "crop_cycles": 1,  # 父表：被 cycle_stages 引用
            "farm_logs": 1,
        }
        sorted_tables = sorted(tables, key=lambda t: _DELETE_ORDER.get(t, 0))

        for table in sorted_tables:
            delete_sql = self._build_delete_sql(table)
            if delete_sql:
                try:
                    self._db.execute(text(delete_sql), {"farm_id": self._farm_id})
                    logger.info(
                        "已清理表 %s 中 farm_id=%s 的数据", table, self._farm_id
                    )
                except Exception:
                    logger.exception("清理表 %s 失败", table)
            else:
                logger.warning("未找到表 %s 的清理策略，跳过", table)
        self._db.commit()

    def _build_delete_sql(self, table: str) -> str | None:
        """根据表名构建 DELETE SQL。"""
        direct_farm_id_tables = {
            "cost_records": "farm_id",
            "crop_templates": "farm_id",
            "crop_cycles": "farm_id",
            "farm_logs": "farm_id",
        }

        if table in direct_farm_id_tables:
            farm_col = direct_farm_id_tables[table]
            return f"DELETE FROM {table} WHERE {farm_col} = :farm_id"

        if table == "growth_stages":
            return (
                "DELETE FROM growth_stages WHERE crop_template_id IN ("
                "SELECT id FROM crop_templates WHERE farm_id = :farm_id"
                ")"
            )

        if table == "cycle_stages":
            return (
                "DELETE FROM cycle_stages WHERE cycle_id IN ("
                "SELECT id FROM crop_cycles WHERE farm_id = :farm_id"
                ")"
            )

        return None
