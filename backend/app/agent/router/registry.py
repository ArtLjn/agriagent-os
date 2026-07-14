"""Skill Router 迁移期 fallback 注册表。

长期事实源是 ``app.agent.skills.registry`` 下的 YAML Registry。这里的静态
配置仅用于未写入 Registry 的旧工具兜底，新增业务能力不要继续扩展本文件。
"""

from app.infra.pending_actions import WRITE_SKILLS

CATALOG_REGISTRY: dict[str, dict] = {
    "get_farm_status": {
        "domain": "planting",
        "intents": ["query_farm_status", "query_active_crops"],
        "risk": "read",
        "entities": ["farm", "crop_cycle"],
        "trigger_examples": ["我家有哪些作物栽种", "农场现在是什么情况"],
        "anti_examples": ["创建茬口"],
        "context_dependencies": ["farm", "crop_cycles", "recent_operations"],
        "candidate_group": "planting_read",
    },
    "get_weather_forecast": {
        "domain": "weather",
        "intents": ["query_weather"],
        "risk": "read",
        "entities": ["weather"],
        "trigger_examples": ["明天苏州什么天气", "最近会不会下雨"],
        "anti_examples": ["搜索一下天气新闻"],
        "context_dependencies": ["weather", "user_settings"],
        "candidate_group": "weather_read",
    },
    "manage_crop_cycle": {
        "domain": "planting",
        "intents": ["create_crop_cycle", "query_crop_cycle", "query_crop_cycles"],
        "risk": "write_confirm",
        "entities": ["crop_cycle", "crop_template", "planting_unit"],
        "trigger_examples": [
            "帮我建个黑布林茬口30亩",
            "我的茬口",
            "看一下3号茬口",
        ],
        "anti_examples": ["黑布林怎么种", "创建作物模板", "农场整体情况"],
        "context_dependencies": ["crop_templates", "planting_units", "crop_cycles"],
        "candidate_group": "planting_write",
    },
    "get_cost_summary": {
        "domain": "finance",
        "intents": ["query_cost_summary"],
        "risk": "read",
        "entities": ["cost", "income", "balance"],
        "trigger_examples": ["我的余额", "这个月花了多少", "最近收支情况"],
        "anti_examples": ["买了化肥200块", "记一笔支出"],
        "context_dependencies": ["cost_summary"],
        "candidate_group": "finance_read",
    },
    "get_debt_summary": {
        "domain": "finance",
        "intents": ["query_debt_summary"],
        "risk": "read",
        "entities": ["debt"],
        "trigger_examples": ["我还欠多少钱", "总欠款多少", "赊账还欠多少"],
        "anti_examples": ["还了老王200"],
        "context_dependencies": ["debt_summary"],
        "candidate_group": "finance_read",
    },
    "get_operation_work_orders": {
        "domain": "operation",
        "intents": ["query_work_orders"],
        "risk": "read",
        "entities": ["operation_work_order"],
        "trigger_examples": ["最近玉米授粉作业有哪些"],
        "anti_examples": ["今天李树去6号棚收水稻"],
        "context_dependencies": ["operation_work_orders", "workers"],
        "candidate_group": "operation_read",
    },
    "create_operation_work_order": {
        "domain": "operation",
        "intents": ["create_work_order"],
        "risk": "write_confirm",
        "entities": ["worker", "planting_unit", "crop_cycle", "labor"],
        "trigger_examples": ["今天李树去6号棚收水稻"],
        "anti_examples": ["我的作业单有哪些"],
        "context_dependencies": ["workers", "planting_units", "active_cycles"],
        "candidate_group": "operation_write",
    },
    "manage_work_orders": {
        "domain": "operation",
        "intents": [
            "create_work_order",
            "query_work_orders",
            "update_work_order",
        ],
        "risk": "write_confirm",
        "entities": ["operation_work_order", "worker", "planting_unit", "labor"],
        "trigger_examples": [
            "今天李树去6号棚收水稻",
            "最近玉米授粉作业有哪些",
            "修改昨天的作业单备注",
        ],
        "anti_examples": ["我的工人有哪些"],
        "context_dependencies": [
            "operation_work_orders",
            "workers",
            "planting_units",
            "active_cycles",
        ],
        "candidate_group": "operation_work_orders",
    },
    "manage_workers": {
        "domain": "labor",
        "intents": ["create_worker", "update_worker", "deactivate_worker"],
        "risk": "write_confirm",
        "entities": ["worker", "labor"],
        "trigger_examples": ["新来一个工人李丽工资100一天", "删除工人李四"],
        "anti_examples": ["我的工人有哪些"],
        "context_dependencies": ["workers"],
        "candidate_group": "labor_write",
    },
    "get_workers": {
        "domain": "labor",
        "intents": ["query_workers"],
        "risk": "read",
        "entities": ["worker"],
        "trigger_examples": ["我的工人", "看看离职工人"],
        "anti_examples": ["新增工人"],
        "context_dependencies": ["workers"],
        "candidate_group": "labor_read",
    },
    "web_search": {
        "domain": "external_search",
        "intents": ["query_web_search"],
        "risk": "read",
        "entities": ["web"],
        "trigger_examples": ["搜索一下天气新闻", "网上查一下行情"],
        "anti_examples": ["随便聊聊"],
        "candidate_group": "external_read",
    },
}


def default_risk_for_tool(name: str) -> str:
    return "write_confirm" if name in WRITE_SKILLS else "read"
