"""农事作业单 Skill schema 与 metadata。"""

from app.agent.skills.metadata import SkillPermissionLevel, SkillRiskLevel


def work_order_parameters_schema() -> dict:
    """返回 manage_work_orders 参数 schema。"""
    return {
        "type": "object",
        "properties": _operation_properties()
        | _create_properties()
        | _labor_properties()
        | _query_update_properties(),
        "required": ["operation"],
    }


def _operation_properties() -> dict:
    return {
        "operation": {
            "type": "string",
            "enum": [
                "create_work_order",
                "query_work_orders",
                "update_work_order",
            ],
            "description": "操作：create_work_order/query_work_orders/update_work_order",
        },
    }


def _create_properties() -> dict:
    return {
        "operation_type": {
            "type": "string",
            "description": "作业类型，如人工授粉、压蔓、装车",
        },
        "operation_date": {
            "type": "string",
            "description": "作业日期 YYYY-MM-DD，默认今天",
        },
        "work_date": {"type": "string", "description": "作业日期别名，YYYY-MM-DD"},
        "cycle_id": {
            "type": "integer",
            "description": "种植批次 ID，不传则自动选择第一个活跃批次",
        },
        "crop_cycle_name": {
            "type": "string",
            "description": "茬口名称别名，如水稻、夏季水稻",
        },
        "unit_names": {
            "type": "string",
            "description": "作用棚/地块名称，多个用逗号分隔",
        },
        "planting_unit_name": {
            "type": "string",
            "description": "棚/地块名称别名，如1号棚",
        },
        "note": {"type": "string", "description": "备注"},
    }


def _labor_properties() -> dict:
    return {
        "workers": {
            "type": "string",
            "description": "工人姓名，多个用逗号分隔；不存在时自动创建轻量档案",
        },
        "worker_name": {"type": "string", "description": "工人姓名别名，如李丽"},
        "unit_price": {"type": "number", "description": "每名工人单价，如 200"},
        "quantity": {
            "type": "number",
            "description": "每名工人的计薪数量，如干了 15 天则传 15",
        },
        "payment_method": {
            "type": "string",
            "description": "计薪方式别名，如 daily、hourly、piece",
        },
        "paid_worker": {"type": "string", "description": "已付款工人姓名"},
        "paid_amount": {"type": "number", "description": "已付金额"},
        "no_wage": {
            "type": "boolean",
            "description": "明确表示本次作业不计工资时传 true",
        },
        "wage_policy": {
            "type": "string",
            "description": "工资策略；不计工资时可传 none、no_wage 或 free",
        },
    }


def _query_update_properties() -> dict:
    return {
        "work_order_id": {"type": "integer", "description": "作业单 ID"},
        "scope_type": {"type": "string", "description": "范围类型 cycle/unit/farm"},
        "cycle_name": {"type": "string", "description": "茬口名称"},
        "unit_id": {"type": "integer", "description": "种植单元 ID"},
        "unit_name": {"type": "string", "description": "棚/地块名称"},
        "worker": {"type": "string", "description": "工人姓名"},
        "start_date": {"type": "string", "description": "开始日期 YYYY-MM-DD"},
        "end_date": {"type": "string", "description": "结束日期 YYYY-MM-DD"},
        "payment_status": {
            "type": "string",
            "description": "付款状态：unpaid、partial、settled、has_unpaid",
        },
        "limit": {"type": "integer", "description": "最多返回条数"},
        "payable_amount": {"type": "number", "description": "每人应付金额"},
    }


def work_order_metadata() -> dict:
    """返回 manage_work_orders 默认 runtime metadata。"""
    return {
        "permission_level": SkillPermissionLevel.WRITE_CONFIRM,
        "risk_level": SkillRiskLevel.MEDIUM,
        "context_dependencies": [
            "operation_work_orders",
            "crop_cycles",
            "planting_units",
            "workers",
        ],
        "cache_invalidation": [
            "farm_logs",
            "cost_analytics",
            "cost_summary",
            "get_farm_status",
        ],
        "confirmation_schema": {
            "target_fields": ["operation", "work_order_id", "operation_type"],
            "changed_fields": [
                "operation_date",
                "operation_type",
                "scope_type",
                "unit_names",
                "note",
                "workers",
                "payable_amount",
                "paid_amount",
            ],
            "inferred_fields": ["operation", "work_order_id"],
            "editable_fields": [
                "operation",
                "work_order_id",
                "operation_date",
                "operation_type",
                "scope_type",
                "unit_names",
                "note",
                "workers",
                "unit_price",
                "payable_amount",
                "paid_amount",
            ],
            "risk_notes": ["确认后会创建或修改作业单和关联人工成本。"],
        },
        "evaluation_tags": ["write", "operation_work_order", "labor"],
    }
