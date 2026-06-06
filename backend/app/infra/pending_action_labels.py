"""Pending action 展示标签配置。"""

from __future__ import annotations

_SKILL_DISPLAY: dict[str, str] = {
    "create_cost_record": "记账",
    "create_crop_cycle": "创建茬口",
    "create_crop_template": "创建作物模板",
    "log_farm_activity": "记录农事",
    "create_operation_work_order": "创建农事作业单",
    "update_operation_work_order": "更新农事作业单",
    "settle_labor_payment": "结算人工",
    "settle_debt": "还款",
    "update_crop_stage": "更新阶段",
    "manage_workers": "管理工人",
    "manage_wages": "管理工资",
    "delete_cost_record": "删除账务记录",
    "manage_cost_categories": "管理账务分类",
    "manage_planting_units": "管理种植单元",
    "manage_crop_templates": "管理作物模板",
    "manage_farm_logs": "管理农事日志",
    "delete_crop_cycle": "删除茬口",
    "manage_user_settings": "修改用户设置",
}

_SKILL_EMOJI: dict[str, str] = {
    "create_cost_record": "💰",
    "create_crop_cycle": "🌱",
    "create_crop_template": "📋",
    "log_farm_activity": "📝",
    "create_operation_work_order": "🧑‍🌾",
    "update_operation_work_order": "🧑‍🌾",
    "settle_labor_payment": "💳",
    "settle_debt": "💳",
    "update_crop_stage": "🔄",
    "manage_workers": "👷",
    "manage_wages": "💳",
    "delete_cost_record": "🗑️",
    "manage_cost_categories": "🏷️",
    "manage_planting_units": "🌾",
    "manage_crop_templates": "📋",
    "manage_farm_logs": "📝",
    "delete_crop_cycle": "🗑️",
    "manage_user_settings": "⚙️",
}

_SKILL_PARAM_FORMAT: dict[str, list[str]] = {
    "create_cost_record": ["category", "amount", "record_type"],
    "create_crop_cycle": ["crop_name", "season"],
    "create_crop_template": ["crop_name"],
    "log_farm_activity": ["operation_type"],
    "create_operation_work_order": ["operation_type", "operation_date", "cycle_id"],
    "update_operation_work_order": [
        "work_order_id",
        "operation_type",
        "operation_date",
    ],
    "settle_labor_payment": ["worker", "amount", "work_order_id"],
    "settle_debt": ["counterparty", "amount"],
    "update_crop_stage": ["stage_name"],
    "manage_workers": ["action", "name", "worker_id", "default_unit_price"],
    "manage_wages": ["action", "labor_entry_id", "worker_name", "unit_price"],
    "delete_cost_record": ["record_id"],
    "manage_cost_categories": ["action", "category_id", "name", "type"],
    "manage_planting_units": ["action", "unit_id", "cycle_id", "name", "area_mu"],
    "manage_crop_templates": ["action", "template_id", "name", "variety"],
    "manage_farm_logs": ["action", "log_id", "cycle_id", "operation_type"],
    "delete_crop_cycle": ["cycle_id"],
    "manage_user_settings": [
        "display_name",
        "default_city",
        "default_lat",
        "default_lon",
    ],
}


__all__ = ["_SKILL_DISPLAY", "_SKILL_EMOJI", "_SKILL_PARAM_FORMAT"]
