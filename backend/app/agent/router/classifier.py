"""Skill Router 规则意图分类器。"""

import re

from app.agent.router.models import IntentFrame


class RuleIntentClassifier:
    """基于中文触发词生成轻量意图帧。"""

    _query_hints = ("哪些", "有哪些", "看看", "查询", "查一下", "最近", "怎么样")
    _farm_hints = ("作物", "栽种", "农场", "茬口", "种植")
    _crop_hints = ("作物", "栽种", "茬口", "种植")
    _daily_advice_time_hints = ("今天", "明天", "这几天", "最近")
    _daily_advice_action_hints = (
        "适合",
        "该做",
        "做什么",
        "做啥",
        "安排什么",
        "干什么",
        "干啥",
    )
    _weather_sensitive_operation_hints = (
        "打药",
        "施药",
        "喷药",
        "浇水",
        "施肥",
        "采收",
        "播种",
        "移栽",
    )
    _write_action_hints = (
        "处理",
        "弄一下",
        "搞一下",
        "删",
        "删除",
        "改",
        "修改",
        "停用",
        "禁用",
    )
    _write_entity_hints = ("工人", "作业", "账")
    _worker_create_hints = ("新来", "招了", "新增", "创建")
    _worker_pay_hints = ("工资", "日薪", "每天", "一天")
    _work_order_hints = ("作业", "采收", "授粉", "安排")
    _operation_hints = ("授粉", "装车", "整枝", "打杈", "压蔓", "压瓜", "留瓜", "垫瓜")
    _work_order_read_hints = ("作业单", "作业", "采收", "授粉")
    _read_blockers = ("哪些", "有哪些", "查询", "查一下", "看看", "最近", "我的")
    _planting_advice_hints = ("怎么种", "如何种", "咋种", "要注意什么")
    _web_search_hints = ("搜索", "网上查", "新闻")
    _weather_hints = (
        "天气",
        "预报",
        "降雨",
        "下雨",
        "气温",
        "风力",
        "湿度",
        "极端天气",
    )
    _finance_overview_hints = ("money", "finance", "financial")
    _cost_summary_hints = (
        "余额",
        "收支",
        "成本",
        "利润",
        "账单",
        "流水",
        "花了多少",
        "赚了多少",
        "收入多少",
        "支出多少",
    )
    _debt_summary_hints = (
        "还欠",
        "欠款",
        "欠多少钱",
        "欠别人多少钱",
        "赊账统计",
        "赊账还欠",
        "总欠款",
    )
    _labor_payable_hints = (
        "人工钱",
        "工钱",
        "工资",
        "未付人工",
        "欠人工",
        "还欠多少人工",
        "人工欠款",
    )
    _cost_category_hints = (
        "账务分类",
        "成本分类",
        "收入分类",
        "费用分类",
        "有哪些分类",
    )
    _crop_template_hints = (
        "作物模板",
        "模板列表",
        "有哪些模板",
        "生长阶段模板",
    )
    _crop_cycle_list_hints = ("我的茬口", "有哪些茬口", "茬口列表", "种植批次")
    _planting_unit_hints = ("种植单元", "地块", "大棚", "棚区", "有哪些棚")
    _user_settings_hints = (
        "用户设置",
        "我的设置",
        "默认城市",
        "天气城市",
        "显示名",
        "昵称",
    )
    _worker_query_hints = (
        "我的工人",
        "工人列表",
        "有哪些工人",
        "看看工人",
        "查询工人",
        "查一下工人",
        "工人有哪些",
    )

    def classify(self, message: str) -> list[IntentFrame]:
        """按固定规则抽取意图帧。"""
        normalized = message.strip()
        frames: list[IntentFrame] = []

        if self._looks_like_ambiguous_write(normalized):
            return [
                IntentFrame(
                    domain="general",
                    intent="ambiguous_write",
                    risk="write_confirm",
                    candidate_tools=[],
                    confidence=0.7,
                    requires_confirmation=True,
                )
            ]

        if self._looks_like_user_settings_query(normalized):
            frames.append(
                IntentFrame(
                    domain="settings",
                    intent="query_user_settings",
                    risk="read",
                    entities=["user_settings"],
                    candidate_tools=["get_user_settings"],
                    confidence=0.86,
                )
            )
        elif self._looks_like_labor_payable_query(normalized):
            frames.append(
                IntentFrame(
                    domain="labor",
                    intent="query_labor_payables",
                    risk="read",
                    entities=["labor_payable"],
                    candidate_tools=["get_labor_payables"],
                    confidence=0.86,
                )
            )
        elif self._looks_like_cost_category_query(normalized):
            frames.append(
                IntentFrame(
                    domain="finance",
                    intent="query_cost_categories",
                    risk="read",
                    entities=["cost_category"],
                    candidate_tools=["get_cost_categories"],
                    confidence=0.86,
                )
            )
        elif self._looks_like_crop_template_query(normalized):
            frames.append(
                IntentFrame(
                    domain="planting",
                    intent="query_crop_templates",
                    risk="read",
                    entities=["crop_template"],
                    candidate_tools=["get_crop_templates"],
                    confidence=0.86,
                )
            )
        elif self._looks_like_planting_unit_query(normalized):
            frames.append(
                IntentFrame(
                    domain="planting",
                    intent="query_planting_units",
                    risk="read",
                    entities=["planting_unit"],
                    candidate_tools=["get_planting_units"],
                    confidence=0.86,
                )
            )
        elif self._looks_like_crop_cycle_list_query(normalized):
            frames.append(
                IntentFrame(
                    domain="planting",
                    intent="query_crop_cycles",
                    risk="read",
                    entities=["crop_cycle"],
                    candidate_tools=["get_crop_cycles"],
                    confidence=0.86,
                )
            )
        elif self._looks_like_crop_cycle_detail_query(normalized):
            frames.append(
                IntentFrame(
                    domain="planting",
                    intent="query_crop_cycle",
                    risk="read",
                    entities=["crop_cycle"],
                    candidate_tools=["get_crop_cycle_info"],
                    confidence=0.86,
                )
            )
        elif self._looks_like_daily_operation_advice(normalized):
            frames.append(
                IntentFrame(
                    domain="operation",
                    intent="query_daily_operation_advice",
                    risk="read",
                    entities=["weather", "farm", "crop_cycle"],
                    candidate_tools=["get_weather_forecast", "get_farm_status"],
                    confidence=0.84,
                )
            )
        elif self._looks_like_active_crop_query(normalized):
            frames.append(
                IntentFrame(
                    domain="planting",
                    intent="query_active_crops",
                    risk="read",
                    entities=["farm", "crop_cycle"],
                    candidate_tools=["get_farm_status", "get_crop_cycle_info"],
                    confidence=0.85,
                )
            )
        elif self._looks_like_planting_advice(normalized):
            frames.append(
                IntentFrame(
                    domain="planting",
                    intent="query_planting_advice",
                    risk="read",
                    entities=["farm", "crop_cycle"],
                    candidate_tools=["get_farm_status"],
                    confidence=0.72,
                )
            )
        elif self._looks_like_farm_read(normalized):
            frames.append(
                IntentFrame(
                    domain="farm",
                    intent="unknown_farm_read",
                    risk="read",
                    entities=["farm"],
                    candidate_tools=[],
                    confidence=0.6,
                )
            )

        if self._looks_like_query_work_orders(normalized):
            frames.append(
                IntentFrame(
                    domain="operation",
                    intent="query_work_orders",
                    risk="read",
                    entities=["operation_work_order"],
                    candidate_tools=["get_operation_work_orders"],
                    confidence=0.82,
                )
            )

        if self._looks_like_finance_overview_query(normalized):
            frames.append(
                IntentFrame(
                    domain="finance",
                    intent="query_finance_overview",
                    risk="read",
                    entities=["cost", "income", "debt"],
                    candidate_tools=["get_cost_summary", "get_debt_summary"],
                    confidence=0.78,
                )
            )

        if self._looks_like_cost_summary_query(normalized):
            frames.append(
                IntentFrame(
                    domain="finance",
                    intent="query_cost_summary",
                    risk="read",
                    entities=["cost", "income", "balance"],
                    candidate_tools=["get_cost_summary"],
                    confidence=0.84,
                )
            )

        if self._looks_like_debt_summary_query(normalized):
            frames.append(
                IntentFrame(
                    domain="finance",
                    intent="query_debt_summary",
                    risk="read",
                    entities=["debt"],
                    candidate_tools=["get_debt_summary"],
                    confidence=0.84,
                )
            )

        if self._looks_like_worker_query(normalized):
            frames.append(
                IntentFrame(
                    domain="labor",
                    intent="query_workers",
                    risk="read",
                    entities=["worker"],
                    candidate_tools=["get_workers"],
                    confidence=0.84,
                )
            )

        if self._looks_like_web_search(normalized):
            frames.append(
                IntentFrame(
                    domain="external_search",
                    intent="query_web_search",
                    risk="read",
                    entities=["web"],
                    candidate_tools=["web_search"],
                    confidence=0.8,
                )
            )
        elif self._looks_like_weather_query(normalized):
            frames.append(
                IntentFrame(
                    domain="weather",
                    intent="query_weather",
                    risk="read",
                    entities=["weather"],
                    candidate_tools=["get_weather_forecast"],
                    confidence=0.82,
                )
            )

        if self._looks_like_create_worker(normalized):
            worker_params = self._extract_worker_params(normalized)
            frames.append(
                IntentFrame(
                    domain="labor",
                    intent="create_worker",
                    risk="write_confirm",
                    entities=["worker"],
                    candidate_tools=["manage_workers"],
                    confidence=0.78,
                    params_hint=worker_params or None,
                    requires_confirmation=True,
                )
            )

        if self._looks_like_create_work_order(normalized):
            work_order_params = self._extract_work_order_params(normalized)
            depends_on = (
                ["create_worker"]
                if any(frame.intent == "create_worker" for frame in frames)
                else []
            )
            frames.append(
                IntentFrame(
                    domain="operation",
                    intent="create_work_order",
                    risk="write_confirm",
                    entities=["operation_work_order"],
                    candidate_tools=["create_operation_work_order"],
                    confidence=0.76,
                    params_hint=work_order_params or None,
                    depends_on=depends_on,
                    requires_confirmation=True,
                )
            )

        return frames

    def _looks_like_active_crop_query(self, message: str) -> bool:
        return self._has_any(message, self._query_hints) and self._has_any(
            message, self._crop_hints
        )

    def _looks_like_farm_read(self, message: str) -> bool:
        return self._has_any(message, self._query_hints) and self._has_any(
            message, self._farm_hints
        )

    def _looks_like_planting_advice(self, message: str) -> bool:
        return "种" in message and self._has_any(message, self._planting_advice_hints)

    def _looks_like_web_search(self, message: str) -> bool:
        return self._has_any(message, self._web_search_hints)

    def _looks_like_weather_query(self, message: str) -> bool:
        return self._has_any(message, self._weather_hints)

    def _looks_like_daily_operation_advice(self, message: str) -> bool:
        has_time = self._has_any(message, self._daily_advice_time_hints)
        has_advice_action = self._has_any(message, self._daily_advice_action_hints)
        has_weather_sensitive_operation = self._has_any(
            message,
            self._weather_sensitive_operation_hints,
        )
        if has_time and has_advice_action:
            return True
        return has_time and "适合" in message and has_weather_sensitive_operation

    def _looks_like_create_worker(self, message: str) -> bool:
        if "工人" not in message:
            return False
        has_create_action = self._has_any(message, self._worker_create_hints)
        has_pay_hint = self._has_any(message, self._worker_pay_hints)
        return has_create_action or has_pay_hint

    def _looks_like_query_work_orders(self, message: str) -> bool:
        return self._has_any(message, self._read_blockers) and self._has_any(
            message, self._work_order_read_hints
        )

    def _looks_like_create_work_order(self, message: str) -> bool:
        if self._has_any(message, self._read_blockers):
            return False
        return (
            self._looks_like_farm_labor_work(message)
            or self._has_any(message, self._work_order_hints)
            or (self._extract_operation_type(message) is not None)
        )

    def _looks_like_cost_summary_query(self, message: str) -> bool:
        if self._looks_like_cost_category_query(message):
            return False
        return self._has_any(message, self._cost_summary_hints)

    def _looks_like_finance_overview_query(self, message: str) -> bool:
        return message.lower() in self._finance_overview_hints

    def _looks_like_debt_summary_query(self, message: str) -> bool:
        if self._looks_like_labor_payable_query(message):
            return False
        return self._has_any(message, self._debt_summary_hints)

    def _looks_like_labor_payable_query(self, message: str) -> bool:
        if self._looks_like_create_worker(message):
            return False
        if self._looks_like_farm_labor_work(message):
            return False
        return self._has_any(message, self._labor_payable_hints)

    def _looks_like_farm_labor_work(self, message: str) -> bool:
        has_operation = self._extract_operation_type(message) is not None
        has_worker = self._extract_worker_name(message) is not None
        has_labor_hint = bool(
            re.search(r"\d+\s*天", message)
            or self._extract_unit_price(message) is not None
            or self._has_any(message, ("干了", "去", "到", "安排"))
        )
        return has_operation and has_worker and has_labor_hint

    def _looks_like_cost_category_query(self, message: str) -> bool:
        return self._has_any(message, self._cost_category_hints)

    def _looks_like_crop_template_query(self, message: str) -> bool:
        return self._has_any(message, self._crop_template_hints)

    def _looks_like_crop_cycle_list_query(self, message: str) -> bool:
        return self._has_any(message, self._crop_cycle_list_hints)

    def _looks_like_crop_cycle_detail_query(self, message: str) -> bool:
        return bool(
            re.search(
                r"(?:看一下|查询|查一下|看看).{0,8}(?:\d+\s*号)?茬口"
                r"|(?:茬口|周期|cycle)\s*\d+"
                r"|\d+\s*(?:号|#)?\s*(?:茬口|周期)",
                message,
            )
        )

    def _looks_like_planting_unit_query(self, message: str) -> bool:
        return self._has_any(message, self._planting_unit_hints) and self._has_any(
            message, self._query_hints
        )

    def _looks_like_user_settings_query(self, message: str) -> bool:
        return self._has_any(message, self._user_settings_hints)

    def _looks_like_worker_query(self, message: str) -> bool:
        if self._looks_like_create_worker(message):
            return False
        return self._has_any(message, self._worker_query_hints)

    def _looks_like_ambiguous_write(self, message: str) -> bool:
        return self._has_any(message, self._write_action_hints) and self._has_any(
            message, self._write_entity_hints
        )

    @staticmethod
    def _has_any(message: str, hints: tuple[str, ...]) -> bool:
        return any(hint in message for hint in hints)

    def _extract_worker_params(self, message: str) -> dict:
        params: dict = {"default_pay_type": "daily"}
        name = self._extract_worker_name(message)
        price = self._extract_unit_price(message)
        if name:
            params["name"] = name
        if price is not None:
            params["default_unit_price"] = price
        return params

    def _extract_work_order_params(self, message: str) -> dict:
        params: dict = {}
        name = self._extract_worker_name(message)
        unit_name = self._extract_unit_name(message)
        unit_price = self._extract_unit_price(message)
        operation_type = self._extract_operation_type(message)
        quantity = self._extract_labor_quantity(message)
        if name:
            params["workers"] = [name]
        if unit_name:
            params["unit_names"] = [unit_name]
        if operation_type:
            params["operation_type"] = operation_type
        if quantity is not None:
            params["quantity"] = quantity
            params["pay_type"] = "daily"
        if unit_price is not None:
            params["unit_price"] = unit_price
        return params

    @staticmethod
    def _extract_worker_name(message: str) -> str | None:
        name_chars = r"[\u4e00-\u9fa5A-Za-z0-9]{1,8}"
        patterns = (
            rf"(?:工人|员工|师傅)(?P<name>{name_chars})(?:工资|日薪|每天)",
            r"(?:今天|昨天|前天|这个月|本月)?(?P<name>[\u4e00-\u9fa5]{2,4})(?:去|到).{0,16}?(?:采收|授粉|装车|整枝|打杈|压蔓|压瓜|留瓜|垫瓜)",
            r"(?P<name>[\u4e00-\u9fa5]{2,4})(?:这个月|本月).{0,4}?干了\s*\d+\s*天",
            r"(?P<name>[\u4e00-\u9fa5]{2,4})(?:这个月|本月)?.{0,4}?干了\s*\d+\s*天",
            r"(?P<name>[\u4e00-\u9fa5]{2,4})(?:工资|日薪|每天)",
            rf"(?:工人|员工|师傅)(?P<name>{name_chars})",
        )
        for pattern in patterns:
            match = re.search(pattern, message)
            if match:
                name = match.group("name")
                if name not in {"工人", "员工", "师傅"}:
                    return name
        return None

    @staticmethod
    def _extract_unit_price(message: str) -> int | None:
        match = re.search(
            r"(?:工资|日薪|每天|一天|每人|单价)\s*"
            r"(?P<price>\d+)\s*(?:元|块)?\s*(?:一?天|/天|每天)?"
            r"|(?P<price_before>\d+)\s*(?:元|块)?\s*(?:一?天|/天|每天|每人)",
            message,
        )
        if not match:
            return None
        price = match.group("price") or match.group("price_before")
        return int(price)

    @staticmethod
    def _extract_labor_quantity(message: str) -> int | None:
        match = re.search(r"(?P<quantity>\d+)\s*天", message)
        if not match:
            return None
        return int(match.group("quantity"))

    @staticmethod
    def _extract_unit_name(message: str) -> str | None:
        field_match = re.search(
            r"(?:去|到|在)(?P<unit>[\u4e00-\u9fa5A-Za-z0-9]{1,12}?"
            r"(?:大棚|田块|地块|棚|田|地))(?=采收|授粉|作业|$)",
            message,
        )
        if field_match:
            return field_match.group("unit")
        match = re.search(r"(?P<unit>\d+\s*号棚)", message)
        if not match:
            return None
        return match.group("unit").replace(" ", "")

    @staticmethod
    def _extract_operation_type(message: str) -> str | None:
        if "采收" in message or re.search(r"收(?:水稻|麦|菜|瓜|果|玉米)", message):
            return "采收"
        for operation_type in RuleIntentClassifier._operation_hints:
            if operation_type in message:
                return operation_type
        return None
