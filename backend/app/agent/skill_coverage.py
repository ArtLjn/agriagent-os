"""LLM Skill 功能覆盖矩阵。"""

from __future__ import annotations

from collections import Counter

from app.agent.skills.registry import load_skill_registry
from app.core.compat import StrEnum
from pydantic import BaseModel, Field


class CoverageStatus(StrEnum):
    """系统功能的 LLM Skill 覆盖状态。"""

    COVERED_BY_SKILL = "covered_by_skill"
    NEEDS_SKILL = "needs_skill"
    ADMIN_SKILL = "admin_skill"
    FORBIDDEN_FOR_LLM = "forbidden_for_llm"
    NO_SKILL_REQUIRED = "no_skill_required"


class CoveragePriority(StrEnum):
    """覆盖优先级。"""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SkillCoverageEntry(BaseModel):
    """单个 API/Service 能力到 Skill capability 的映射。"""

    domain: str
    operation: str
    source: str
    status: CoverageStatus
    skill_name: str | None = None
    legacy_skill_names: list[str] = Field(default_factory=list)
    capability_name: str | None = None
    capability_operations: list[str] = Field(default_factory=list)
    permission_level: str | None = None
    risk_level: str | None = None
    rationale: str
    priority: CoveragePriority = CoveragePriority.MEDIUM
    test_status: str = "pending"


_COVERAGE_ENTRIES: tuple[SkillCoverageEntry, ...] = (
    SkillCoverageEntry(
        domain="cost",
        operation="create_record",
        source="POST /costs -> cost_service.create_record",
        status=CoverageStatus.COVERED_BY_SKILL,
        skill_name="manage_cost",
        legacy_skill_names=["create_cost_record"],
        capability_name="manage_cost",
        capability_operations=["create_record"],
        permission_level="write_confirm",
        risk_level="medium",
        rationale="普通用户高频记账入口，已受确认保护。",
        priority=CoveragePriority.HIGH,
        test_status="covered",
    ),
    SkillCoverageEntry(
        domain="cost",
        operation="list_summary_analytics",
        source="GET /costs, /costs/summary/{year}, /costs/cycles/{cycle_id}/profit",
        status=CoverageStatus.COVERED_BY_SKILL,
        skill_name="manage_cost",
        legacy_skill_names=["get_cost_summary", "get_cost_analytics"],
        capability_name="manage_cost",
        capability_operations=["query_summary", "analyze_cost"],
        permission_level="read",
        risk_level="low",
        rationale="查询账务、利润和趋势由成本域聚合 Skill 覆盖。",
        priority=CoveragePriority.HIGH,
        test_status="covered",
    ),
    SkillCoverageEntry(
        domain="cost",
        operation="delete_record",
        source="DELETE /costs/{record_id} -> cost_service.delete_record",
        status=CoverageStatus.COVERED_BY_SKILL,
        skill_name="manage_cost",
        legacy_skill_names=["delete_cost_record"],
        capability_name="manage_cost",
        capability_operations=["delete_record"],
        permission_level="write_confirm",
        risk_level="medium",
        rationale="用户可能自然语言撤销错账，需要明确确认和可追溯删除语义。",
        priority=CoveragePriority.HIGH,
        test_status="covered",
    ),
    SkillCoverageEntry(
        domain="cost_category",
        operation="list_create_delete",
        source="GET/POST/DELETE /cost-categories",
        status=CoverageStatus.COVERED_BY_SKILL,
        skill_name="manage_cost_categories",
        legacy_skill_names=["get_cost_categories"],
        capability_name="manage_cost_categories",
        capability_operations=["query_categories", "manage_category"],
        permission_level="operation-aware",
        risk_level="low|medium",
        rationale="分类查询、创建和删除由单一分类业务能力覆盖，删除需确认。",
        priority=CoveragePriority.HIGH,
        test_status="covered",
    ),
    SkillCoverageEntry(
        domain="crop_template",
        operation="create_template",
        source="POST /crops/templates -> crop_service.create_crop_template",
        status=CoverageStatus.COVERED_BY_SKILL,
        legacy_skill_names=["create_crop_template"],
        capability_name="manage_crop_templates",
        capability_operations=["create_template"],
        skill_name="manage_crop_templates",
        permission_level="write_confirm",
        risk_level="medium",
        rationale="缺模板时由作物模板能力的创建 operation 覆盖。",
        priority=CoveragePriority.HIGH,
        test_status="covered",
    ),
    SkillCoverageEntry(
        domain="crop_template",
        operation="list_update_delete_template",
        source="GET/PUT/DELETE /crops/templates",
        status=CoverageStatus.COVERED_BY_SKILL,
        legacy_skill_names=["get_crop_templates"],
        capability_name="manage_crop_templates",
        capability_operations=["query_templates", "manage_template"],
        skill_name="manage_crop_templates",
        permission_level="operation-aware",
        risk_level="low|high",
        rationale="模板查询、纠错和删除由专用 Skill 覆盖；删除模板按高风险确认处理。",
        priority=CoveragePriority.MEDIUM,
        test_status="covered",
    ),
    SkillCoverageEntry(
        domain="crop_cycle",
        operation="create_list_update_stage",
        source="POST/GET/PUT /cycles, POST /cycles/{cycle_id}/advance-stage",
        status=CoverageStatus.COVERED_BY_SKILL,
        skill_name="manage_crop_cycle",
        permission_level="operation-aware",
        risk_level="low|medium",
        rationale="茬口创建、查询、起始日期和阶段更新由 manage_crop_cycle 聚合覆盖；update_crop_stage 仅作为 registry legacy alias 保留。",
        priority=CoveragePriority.HIGH,
        test_status="covered",
    ),
    SkillCoverageEntry(
        domain="crop_cycle",
        operation="delete_cycle",
        source="DELETE /cycles/{cycle_id} -> cycle_service.delete_crop_cycle",
        status=CoverageStatus.COVERED_BY_SKILL,
        skill_name="manage_crop_cycle",
        permission_level="operation-aware",
        risk_level="high",
        rationale="删除茬口影响历史农事和账务，已通过 manage_crop_cycle.delete_cycle 高风险确认暴露。",
        priority=CoveragePriority.MEDIUM,
        test_status="covered",
    ),
    SkillCoverageEntry(
        domain="farm_log",
        operation="create_query_update_delete",
        source="POST/GET/PUT/DELETE /logs",
        status=CoverageStatus.COVERED_BY_SKILL,
        skill_name="manage_farm_logs",
        permission_level="operation-aware",
        risk_level="low|medium",
        rationale="创建、查询、编辑和删除农事记录均由 manage_farm_logs 聚合覆盖；旧日志工具名仅作为 registry alias 保留。",
        priority=CoveragePriority.HIGH,
        test_status="covered",
    ),
    SkillCoverageEntry(
        domain="planting_unit",
        operation="crud",
        source="POST/GET/PUT/DELETE /planting/units",
        status=CoverageStatus.COVERED_BY_SKILL,
        skill_name="manage_planting_units",
        permission_level="read|write_confirm",
        risk_level="low|medium",
        rationale="棚/地块查询、创建、更新和删除由 manage_planting_units 聚合覆盖；get_planting_units 仅作为 registry alias 保留。",
        priority=CoveragePriority.HIGH,
        test_status="covered",
    ),
    SkillCoverageEntry(
        domain="worker",
        operation="query_crud",
        source="POST/GET/PUT/DELETE /planting/workers",
        status=CoverageStatus.COVERED_BY_SKILL,
        skill_name="manage_workers",
        permission_level="read|write_confirm",
        risk_level="low|medium",
        rationale="工人查询、创建、更新、停用和恢复由 manage_workers 聚合覆盖；get_workers 仅作为 registry alias 保留。",
        priority=CoveragePriority.HIGH,
        test_status="covered",
    ),
    SkillCoverageEntry(
        domain="labor",
        operation="wage_save_update",
        source="POST/PATCH /planting/labor/wages",
        status=CoverageStatus.COVERED_BY_SKILL,
        skill_name="manage_labor_payment",
        permission_level="write_confirm",
        risk_level="medium",
        rationale="单独记工资和修改工资由确认型工资 Skill 覆盖。",
        priority=CoveragePriority.HIGH,
        test_status="covered",
    ),
    SkillCoverageEntry(
        domain="operation_work_order",
        operation="create_query_update_settle",
        source="POST/GET /planting/work-orders, recent operations, labor payables",
        status=CoverageStatus.COVERED_BY_SKILL,
        skill_name=(
            "create_operation_work_order|get_operation_work_orders|"
            "update_operation_work_order|manage_labor_payment"
        ),
        permission_level="read|write_confirm",
        risk_level="low|medium",
        rationale="作业单、用工查询和人工结算已有 Skill 闭环。",
        priority=CoveragePriority.HIGH,
        test_status="covered",
    ),
    SkillCoverageEntry(
        domain="debt",
        operation="create_list_settle",
        source="POST/GET/POST /debts",
        status=CoverageStatus.COVERED_BY_SKILL,
        skill_name="manage_cost",
        legacy_skill_names=[
            "create_cost_record",
            "get_debt_summary",
            "settle_debt",
        ],
        capability_name="manage_cost",
        capability_operations=["create_record", "query_debt", "settle_debt"],
        permission_level="read|write_confirm",
        risk_level="low|medium",
        rationale="赊账创建、未结统计和结清由成本域聚合 Skill 覆盖。",
        priority=CoveragePriority.HIGH,
        test_status="covered",
    ),
    SkillCoverageEntry(
        domain="weather",
        operation="forecast",
        source="GET /weather/forecast -> weather_service.fetch_weather",
        status=CoverageStatus.COVERED_BY_SKILL,
        skill_name="weather",
        permission_level="external_network",
        risk_level="low",
        rationale="天气查询已有外部网络 Skill。",
        priority=CoveragePriority.HIGH,
        test_status="covered",
    ),
    SkillCoverageEntry(
        domain="agent",
        operation="chat_daily_reports_history",
        source="POST/GET /agent/*",
        status=CoverageStatus.NO_SKILL_REQUIRED,
        rationale="这是 Agent 自身交互面，不应再通过 LLM Skill 调自己。",
        priority=CoveragePriority.LOW,
        test_status="classified",
    ),
    SkillCoverageEntry(
        domain="user_settings",
        operation="get_update_settings",
        source="GET/PUT /user-settings",
        status=CoverageStatus.COVERED_BY_SKILL,
        skill_name="manage_user_settings",
        permission_level="read|write_confirm",
        risk_level="low|medium",
        rationale="当前用户设置查询和白名单配置项更新由统一 settings Skill 覆盖。",
        priority=CoveragePriority.MEDIUM,
        test_status="covered",
    ),
    SkillCoverageEntry(
        domain="admin",
        operation="skills_prompts_config_trace_stats_users",
        source="GET/POST/PUT/DELETE /admin/*",
        status=CoverageStatus.ADMIN_SKILL,
        permission_level="admin",
        risk_level="high",
        rationale="管理能力必须隔离到 Admin Skill 或标记禁止普通用户调用。",
        priority=CoveragePriority.MEDIUM,
        test_status="classified",
    ),
    SkillCoverageEntry(
        domain="auth",
        operation="login_register_password",
        source="/auth/*",
        status=CoverageStatus.FORBIDDEN_FOR_LLM,
        rationale="认证与凭据处理不应通过普通 LLM Skill 执行。",
        priority=CoveragePriority.HIGH,
        test_status="classified",
    ),
    SkillCoverageEntry(
        domain="feedback",
        operation="submit_and_stats",
        source="POST/GET /feedback",
        status=CoverageStatus.NO_SKILL_REQUIRED,
        rationale="反馈提交由产品入口处理；统计属于管理/运营视角。",
        priority=CoveragePriority.LOW,
        test_status="classified",
    ),
    SkillCoverageEntry(
        domain="app_version",
        operation="check_version",
        source="GET /version",
        status=CoverageStatus.NO_SKILL_REQUIRED,
        rationale="客户端升级检查不是自然语言业务能力。",
        priority=CoveragePriority.LOW,
        test_status="classified",
    ),
)


def list_skill_coverage_entries() -> list[SkillCoverageEntry]:
    """返回完整 Skill 覆盖矩阵。"""
    return [_enrich_with_registry(entry) for entry in _COVERAGE_ENTRIES]


def summarize_skill_coverage() -> dict[str, int]:
    """按覆盖状态汇总功能数量。"""
    counts = Counter(entry.status.value for entry in _COVERAGE_ENTRIES)
    return dict(sorted(counts.items()))


def high_priority_unclassified_entries() -> list[SkillCoverageEntry]:
    """返回未分类的高优先级普通用户能力。"""
    return [
        entry
        for entry in _COVERAGE_ENTRIES
        if entry.priority == CoveragePriority.HIGH
        and entry.status
        not in {
            CoverageStatus.COVERED_BY_SKILL,
            CoverageStatus.NEEDS_SKILL,
            CoverageStatus.ADMIN_SKILL,
            CoverageStatus.FORBIDDEN_FOR_LLM,
            CoverageStatus.NO_SKILL_REQUIRED,
        }
    ]


def _enrich_with_registry(entry: SkillCoverageEntry) -> SkillCoverageEntry:
    legacy_names = _split_skill_names(entry.skill_name)
    if not legacy_names:
        return entry
    try:
        registry = load_skill_registry()
    except (OSError, ValueError):
        return entry.model_copy(update={"legacy_skill_names": legacy_names})

    capability_operations = []
    capability_names = []
    for legacy_name in legacy_names:
        alias = registry.resolve_alias(legacy_name)
        if alias is None:
            continue
        capability_operations.append(alias.target)
        if alias.capability not in capability_names:
            capability_names.append(alias.capability)

    return entry.model_copy(
        update={
            "legacy_skill_names": legacy_names,
            "capability_name": "|".join(capability_names) if capability_names else None,
            "capability_operations": capability_operations,
        }
    )


def _split_skill_names(skill_name: str | None) -> list[str]:
    if not skill_name:
        return []
    return [name for name in skill_name.split("|") if name]
