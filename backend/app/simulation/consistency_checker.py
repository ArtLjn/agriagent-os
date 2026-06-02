import logging

from app.simulation.models import Claim, DbDiff, SimulationTestCase
from app.simulation.semantic_extractor import get_table_for_op

logger = logging.getLogger(__name__)

_FAILURE_KEYWORDS = ["失败", "错误", "无法", "异常", "系统繁忙", "出错", "未成功"]
_SUCCESS_KEYWORDS = ["已记账", "已创建", "已更新", "已记录", "已结算", "成功"]


def check_consistency(
    agent_reply: str,
    claims: list[Claim],
    db_diff: DbDiff,
    test_case: SimulationTestCase,
    pending_action: dict | None = None,
    skill_traces: list[dict] | None = None,
) -> list[str]:
    """
    对比 LLM 声称的操作和数据库实际变化，返回错误列表。

    检测类型：
    1. hallucination: LLM 声称执行了某操作，但对应表无变化
    2. attribution_error: LLM 回复暗示失败/异常，但 DB 实际有变化
    3. partial_execution: LLM 声称全部执行但只部分成功
    4. silent_mutation: DB 有变化但 LLM 未提及
    5. state_mismatch: DB 变化与预期不符
    """
    errors: list[str] = []

    is_cancel_scenario = not test_case.expected_db_changes and pending_action is not None
    if not is_cancel_scenario:
        errors.extend(_check_hallucination(claims, db_diff, skill_traces))
    errors.extend(_check_attribution_error(agent_reply, claims, db_diff))
    errors.extend(_check_silent_mutation(agent_reply, claims, db_diff))
    errors.extend(_check_expected_changes(db_diff, test_case.expected_db_changes))
    errors.extend(_check_response_matches(agent_reply, test_case.expected_response_matches))

    return errors


# op_type 到 skill_name 的反向映射（用于 trace 查询）
_OP_TYPE_TO_SKILL_NAME: dict[str, str] = {
    "create_cost": "create_cost_record",
    "create_template": "create_crop_template",
    "create_cycle": "create_crop_cycle",
    "update_stage": "update_cycle_stage",
    "log_activity": "log_farm_activity",
    "settle_debt": "settle_debt",
}


def _check_hallucination(
    claims: list[Claim], db_diff: DbDiff, skill_traces: list[dict] | None = None
) -> list[str]:
    """LLM 声称执行但 DB 无变化 → hallucination 或 execution_failure。"""
    errors: list[str] = []
    for claim in claims:
        table = get_table_for_op(claim.op_type)
        if table and not db_diff.has_changes_for_table(table):
            # 检查是否有对应的 skill_call trace
            skill_called = False
            if skill_traces:
                expected_skill = _OP_TYPE_TO_SKILL_NAME.get(
                    claim.op_type, claim.op_type
                )
                for trace in skill_traces:
                    if trace.get("node_name") == expected_skill:
                        skill_called = True
                        break

            if skill_called:
                errors.append(
                    f"execution_failure: LLM 声称执行了 {claim.op_type}，"
                    f"skill 已被调用但数据库写入失败"
                )
            else:
                errors.append(
                    f"hallucination: LLM 声称执行了 {claim.op_type}，"
                    f"但表 {table} 无实际变化"
                )
    return errors


def _check_attribution_error(
    agent_reply: str, claims: list[Claim], db_diff: DbDiff
) -> list[str]:
    """
    LLM 回复包含失败词但 DB 有变化 → attribution_error。
    """
    errors: list[str] = []
    has_failure_words = any(kw in agent_reply for kw in _FAILURE_KEYWORDS)
    has_db_changes = bool(db_diff.added or db_diff.removed or db_diff.modified)

    if has_failure_words and has_db_changes:
        errors.append(
            "attribution_error: LLM 回复暗示操作失败，但数据库实际有变化"
        )
    return errors


def _check_silent_mutation(
    agent_reply: str, claims: list[Claim], db_diff: DbDiff
) -> list[str]:
    """DB 有变化但 LLM 未提及任何相关操作 → silent_mutation。"""
    errors: list[str] = []
    claimed_tables = {
        get_table_for_op(c.op_type) for c in claims if get_table_for_op(c.op_type)
    }

    changed_tables = set()
    for record in db_diff.added + db_diff.removed + db_diff.modified:
        table = record.get("__table__")
        if table:
            changed_tables.add(table)

    for table in changed_tables:
        if table not in claimed_tables:
            errors.append(
                f"silent_mutation: 表 {table} 有数据变化，但 LLM 未提及相关操作"
            )
    return errors


def _check_expected_changes(
    db_diff: DbDiff, expected: dict[str, dict]
) -> list[str]:
    """验证 DB 变化是否与预期一致。"""
    errors: list[str] = []
    if not expected:
        return errors

    # 统计各表新增数量
    added_counts: dict[str, int] = {}
    for record in db_diff.added:
        table = record.get("__table__", "unknown")
        added_counts[table] = added_counts.get(table, 0) + 1

    for table, expect in expected.items():
        expected_added = expect.get("added", 0)
        actual_added = added_counts.get(table, 0)

        if actual_added != expected_added:
            errors.append(
                f"state_mismatch: 表 {table} 预期新增 {expected_added} 条，"
                f"实际新增 {actual_added} 条"
            )

        # 检查 match_fields
        match_fields = expect.get("match_fields", {})
        if match_fields:
            table_added = [r for r in db_diff.added if r.get("__table__") == table]
            for field, expected_value in match_fields.items():
                found = False
                for record in table_added:
                    if _match_field_value(record.get(field), expected_value):
                        found = True
                        break
                if not found:
                    errors.append(
                        f"state_mismatch: 表 {table} 新增记录中未找到 "
                        f"字段 {field}={expected_value}"
                    )

    return errors


def _match_field_value(actual_value, expected_value) -> bool:
    """匹配字段值，支持数字等值和字符串子串匹配。"""
    if actual_value is None:
        return False

    # 数字等值匹配（int == float）
    if isinstance(actual_value, (int, float)) and isinstance(expected_value, (int, float)):
        return actual_value == expected_value

    # 字符串子串匹配
    if isinstance(expected_value, str) and isinstance(actual_value, str):
        return expected_value in actual_value

    # 布尔严格相等
    if isinstance(expected_value, bool) and isinstance(actual_value, bool):
        return actual_value == expected_value

    # 兜底：严格相等
    return actual_value == expected_value


def _check_response_matches(
    agent_reply: str, expected_matches: list[str]
) -> list[str]:
    """验证 LLM 回复是否包含预期关键词。"""
    errors: list[str] = []
    if not expected_matches:
        return errors

    for keyword in expected_matches:
        if keyword not in agent_reply:
            errors.append(
                f"response_mismatch: LLM 回复未包含预期关键词 '{keyword}'"
            )
    return errors
