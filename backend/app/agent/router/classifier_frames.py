"""RuleIntentClassifier 的 IntentFrame 构造函数。"""

from app.agent.router.models import IntentFrame


def build_ambiguous_write_frame() -> IntentFrame:
    return IntentFrame(
        domain="general",
        intent="ambiguous_write",
        risk="write_confirm",
        candidate_tools=[],
        confidence=0.7,
        requires_confirmation=True,
    )


def build_query_user_settings_frame() -> IntentFrame:
    return IntentFrame(
        domain="settings",
        intent="query_user_settings",
        risk="read",
        entities=["user_settings"],
        candidate_tools=["manage_user_settings"],
        capability="manage_settings",
        operation="query_settings",
        operation_hint="query_settings",
        confidence=0.86,
    )


def build_query_labor_payables_frame() -> IntentFrame:
    return IntentFrame(
        domain="labor",
        intent="query_labor_payables",
        risk="read",
        capability="manage_labor_payment",
        operation="query_payables",
        operation_hint="query_payables",
        entities=["labor_payable"],
        candidate_tools=["manage_labor_payment"],
        confidence=0.86,
    )


def build_query_cost_categories_frame() -> IntentFrame:
    return IntentFrame(
        domain="finance",
        intent="query_cost_categories",
        risk="read",
        entities=["cost_category"],
        candidate_tools=["manage_cost_categories"],
        capability="manage_cost_categories",
        operation="query_categories",
        operation_hint="query_categories",
        confidence=0.86,
    )


def build_query_crop_templates_frame() -> IntentFrame:
    return IntentFrame(
        domain="planting",
        intent="query_crop_templates",
        risk="read",
        entities=["crop_template"],
        candidate_tools=["manage_crop_templates"],
        confidence=0.86,
    )


def build_query_planting_units_frame() -> IntentFrame:
    return IntentFrame(
        domain="planting",
        intent="query_planting_units",
        risk="read",
        entities=["planting_unit"],
        candidate_tools=["manage_planting_units"],
        capability="manage_planting_units",
        operation="query_units",
        operation_hint="query_units",
        confidence=0.86,
    )


def build_query_crop_cycles_frame() -> IntentFrame:
    return IntentFrame(
        domain="planting",
        intent="query_crop_cycles",
        risk="read",
        entities=["crop_cycle"],
        candidate_tools=["manage_crop_cycle"],
        capability="manage_crop_cycle",
        operation="query_cycles",
        operation_hint="query_cycles",
        confidence=0.88,
    )


def build_query_crop_cycle_frame() -> IntentFrame:
    return IntentFrame(
        domain="planting",
        intent="query_crop_cycle",
        risk="read",
        entities=["crop_cycle"],
        candidate_tools=["manage_crop_cycle"],
        capability="manage_crop_cycle",
        operation="query_cycle_info",
        operation_hint="query_cycle_info",
        confidence=0.86,
    )


def build_query_daily_operation_advice_frame() -> IntentFrame:
    return IntentFrame(
        domain="operation",
        intent="query_daily_operation_advice",
        risk="read",
        entities=["weather", "farm", "crop_cycle"],
        candidate_tools=["weather", "get_farm_status"],
        confidence=0.84,
    )


def build_query_active_crops_frame() -> IntentFrame:
    return IntentFrame(
        domain="planting",
        intent="query_active_crops",
        risk="read",
        entities=["farm", "crop_cycle"],
        candidate_tools=["manage_crop_cycle", "get_farm_status"],
        capability="manage_crop_cycle",
        operation="query_cycles",
        operation_hint="query_cycles",
        confidence=0.85,
    )


def build_query_planting_advice_frame() -> IntentFrame:
    return IntentFrame(
        domain="planting",
        intent="query_planting_advice",
        risk="read",
        entities=["farm", "crop_cycle"],
        candidate_tools=["get_farm_status"],
        confidence=0.72,
    )


def build_unknown_farm_read_frame() -> IntentFrame:
    return IntentFrame(
        domain="farm",
        intent="unknown_farm_read",
        risk="read",
        entities=["farm"],
        candidate_tools=[],
        confidence=0.6,
    )


def build_query_work_orders_frame() -> IntentFrame:
    return IntentFrame(
        domain="operation",
        intent="query_work_orders",
        risk="read",
        entities=["operation_work_order"],
        candidate_tools=["get_operation_work_orders", "manage_work_orders"],
        confidence=0.82,
    )


def build_query_finance_overview_frame() -> IntentFrame:
    return IntentFrame(
        domain="finance",
        intent="query_finance_overview",
        risk="read",
        entities=["cost", "income", "debt"],
        candidate_tools=["get_cost_summary", "get_debt_summary"],
        confidence=0.78,
    )


def build_query_cost_summary_frame() -> IntentFrame:
    return IntentFrame(
        domain="finance",
        intent="query_cost_summary",
        risk="read",
        entities=["cost", "income", "balance"],
        candidate_tools=["get_cost_summary"],
        confidence=0.84,
    )


def build_analyze_cost_frame() -> IntentFrame:
    return IntentFrame(
        domain="finance",
        intent="analyze_cost",
        risk="read",
        entities=["cost", "income", "trend"],
        candidate_tools=["get_cost_analytics"],
        confidence=0.84,
    )


def build_query_debt_summary_frame() -> IntentFrame:
    return IntentFrame(
        domain="finance",
        intent="query_debt_summary",
        risk="read",
        entities=["debt"],
        candidate_tools=["get_debt_summary"],
        confidence=0.84,
    )


def build_query_workers_frame() -> IntentFrame:
    return IntentFrame(
        domain="labor",
        intent="query_workers",
        risk="read",
        capability="manage_workers",
        operation="query_workers",
        operation_hint="query_workers",
        entities=["worker"],
        candidate_tools=["manage_workers"],
        confidence=0.84,
    )


def build_query_web_search_frame() -> IntentFrame:
    return IntentFrame(
        domain="external_search",
        intent="query_web_search",
        risk="read",
        entities=["web"],
        candidate_tools=["web_search"],
        confidence=0.8,
    )


def build_query_weather_crop_impact_frame() -> IntentFrame:
    return IntentFrame(
        domain="operation",
        intent="query_weather_crop_impact",
        risk="read",
        entities=["weather", "farm", "crop_cycle"],
        candidate_tools=["weather", "get_farm_status"],
        confidence=0.84,
    )


def build_query_weather_frame() -> IntentFrame:
    return IntentFrame(
        domain="weather",
        intent="query_weather",
        risk="read",
        entities=["weather"],
        candidate_tools=["weather"],
        confidence=0.82,
    )


def build_create_worker_frame(params_hint: dict | None) -> IntentFrame:
    return IntentFrame(
        domain="labor",
        intent="create_worker",
        risk="write_confirm",
        entities=["worker"],
        candidate_tools=["manage_workers"],
        confidence=0.78,
        params_hint=params_hint,
        requires_confirmation=True,
    )


def build_manage_worker_frame(params_hint: dict | None) -> IntentFrame:
    return IntentFrame(
        domain="labor",
        intent="manage_worker",
        risk="write_confirm",
        entities=["worker"],
        candidate_tools=["manage_workers"],
        confidence=0.78,
        params_hint=params_hint,
        requires_confirmation=True,
    )


def build_create_crop_template_frame() -> IntentFrame:
    return IntentFrame(
        domain="planting",
        intent="create_crop_template",
        risk="write_confirm",
        entities=["crop_template"],
        candidate_tools=["manage_crop_templates"],
        confidence=0.78,
        requires_confirmation=True,
    )


def build_create_crop_cycle_frame() -> IntentFrame:
    return IntentFrame(
        domain="planting",
        intent="create_crop_cycle",
        risk="write_confirm",
        entities=["crop_cycle"],
        candidate_tools=["manage_crop_cycle"],
        capability="manage_crop_cycle",
        operation="create_cycle",
        operation_hint="create_cycle",
        confidence=0.76,
        requires_confirmation=True,
    )


def build_delete_crop_cycle_frame() -> IntentFrame:
    return IntentFrame(
        domain="crop",
        intent="delete_cycle",
        risk="write_high",
        entities=["crop_cycle"],
        candidate_tools=["manage_crop_cycle"],
        capability="manage_crop_cycle",
        operation="delete_cycle",
        operation_hint="delete_cycle",
        confidence=0.78,
        requires_confirmation=True,
    )


def build_create_cost_record_frame() -> IntentFrame:
    return IntentFrame(
        domain="finance",
        intent="create_cost_record",
        risk="write_confirm",
        entities=["cost"],
        candidate_tools=["create_cost_record"],
        confidence=0.78,
        requires_confirmation=True,
    )


def build_delete_cost_record_frame() -> IntentFrame:
    return IntentFrame(
        domain="finance",
        intent="delete_record",
        risk="write_high",
        entities=["cost"],
        candidate_tools=["delete_cost_record"],
        confidence=0.78,
        requires_confirmation=True,
    )


def build_settle_debt_frame() -> IntentFrame:
    return IntentFrame(
        domain="finance",
        intent="settle_debt",
        risk="write_confirm",
        entities=["debt"],
        candidate_tools=["settle_debt"],
        confidence=0.78,
        requires_confirmation=True,
    )


def build_settle_labor_payment_frame(params_hint: dict) -> IntentFrame:
    return IntentFrame(
        domain="labor",
        intent="settle_labor_payment",
        risk="write_confirm",
        capability="manage_labor_payment",
        operation="settle_payment",
        operation_hint="settle_payment",
        entities=["labor_payable"],
        candidate_tools=["manage_labor_payment"],
        confidence=0.82,
        params_hint=params_hint,
        requires_confirmation=True,
    )


def build_manage_wage_frame(params_hint: dict) -> IntentFrame:
    return IntentFrame(
        domain="labor",
        intent="manage_wage",
        risk="write_confirm",
        capability="manage_labor_payment",
        operation="manage_wage",
        operation_hint="manage_wage",
        entities=["labor_payable", "wage"],
        candidate_tools=["manage_labor_payment"],
        confidence=0.8,
        params_hint=params_hint,
        requires_confirmation=True,
    )


def build_update_user_settings_frame() -> IntentFrame:
    return IntentFrame(
        domain="settings",
        intent="update_settings",
        risk="write_confirm",
        entities=["user_settings"],
        candidate_tools=["manage_user_settings"],
        capability="manage_settings",
        operation="update_settings",
        operation_hint="update_settings",
        confidence=0.8,
        requires_confirmation=True,
    )


def build_manage_cost_category_frame(action: str) -> IntentFrame:
    return IntentFrame(
        domain="finance",
        intent="manage_cost_category",
        risk="write_confirm",
        entities=["cost_category"],
        candidate_tools=["manage_cost_categories"],
        capability="manage_cost_categories",
        operation="manage_category",
        operation_hint="manage_category",
        confidence=0.8,
        params_hint={"action": action},
        requires_confirmation=True,
    )


def build_manage_planting_unit_frame(action: str) -> IntentFrame:
    return IntentFrame(
        domain="farm",
        intent="manage_planting_units",
        risk="write_confirm",
        entities=["planting_unit"],
        candidate_tools=["manage_planting_units"],
        capability="manage_planting_units",
        operation="manage_units",
        operation_hint="manage_units",
        confidence=0.8,
        params_hint={"action": action},
        requires_confirmation=True,
    )


def build_clarify_farm_labor_frame(evidence: dict) -> IntentFrame:
    return IntentFrame(
        domain="operation",
        intent="clarify_farm_labor_work",
        risk="write_confirm",
        entities=["worker", "operation_work_order"],
        candidate_tools=[],
        confidence=0.7,
        params_hint=None,
        planning_evidence=evidence,
        missing_fields=["operation_type"],
        requires_confirmation=True,
    )


def build_create_work_order_frame(
    *,
    params_hint: dict | None,
    planning_evidence: dict,
    missing_fields: list[str],
    depends_on: list[str],
) -> IntentFrame:
    return IntentFrame(
        domain="operation",
        intent="create_work_order",
        risk="write_confirm",
        entities=["operation_work_order"],
        candidate_tools=["create_operation_work_order", "manage_work_orders"],
        confidence=0.76,
        params_hint=params_hint,
        planning_evidence=planning_evidence,
        missing_fields=missing_fields,
        depends_on=depends_on,
        requires_confirmation=True,
    )
