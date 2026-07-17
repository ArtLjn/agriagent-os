"""Skill Router 规则意图分类器。"""

import re

from app.agent.router import classifier_frames as frame_builders
from app.agent.router import classifier_hints as hints
from app.agent.router.models import IntentFrame


class RuleIntentClassifier:
    """基于中文触发词生成轻量意图帧。

    迁移期只保留兼容规则、无工具保护和写风险保护；Registry
    capability/operation enrichment 由 service 与 policy 接管。
    """

    _query_hints = hints.QUERY_HINTS
    _farm_hints = hints.FARM_HINTS
    _crop_hints = hints.CROP_HINTS
    _daily_advice_time_hints = hints.DAILY_ADVICE_TIME_HINTS
    _daily_advice_action_hints = hints.DAILY_ADVICE_ACTION_HINTS
    _weather_sensitive_operation_hints = hints.WEATHER_SENSITIVE_OPERATION_HINTS
    _write_action_hints = hints.WRITE_ACTION_HINTS
    _write_entity_hints = hints.WRITE_ENTITY_HINTS
    _worker_create_hints = hints.WORKER_CREATE_HINTS
    _worker_update_hints = hints.WORKER_UPDATE_HINTS
    _worker_deactivate_hints = hints.WORKER_DEACTIVATE_HINTS
    _worker_restore_hints = hints.WORKER_RESTORE_HINTS
    _worker_update_fields = hints.WORKER_UPDATE_FIELDS
    _worker_pay_hints = hints.WORKER_PAY_HINTS
    _work_order_hints = hints.WORK_ORDER_HINTS
    _operation_hints = hints.OPERATION_HINTS
    _work_order_read_hints = hints.WORK_ORDER_READ_HINTS
    _read_blockers = hints.READ_BLOCKERS
    _planting_advice_hints = hints.PLANTING_ADVICE_HINTS
    _web_search_hints = hints.WEB_SEARCH_HINTS
    _weather_hints = hints.WEATHER_HINTS
    _finance_overview_hints = hints.FINANCE_OVERVIEW_HINTS
    _cost_summary_hints = hints.COST_SUMMARY_HINTS
    _cost_record_write_hints = hints.COST_RECORD_WRITE_HINTS
    _cost_record_entities = hints.COST_RECORD_ENTITIES
    _debt_summary_hints = hints.DEBT_SUMMARY_HINTS
    _cost_analytics_hints = hints.COST_ANALYTICS_HINTS
    _delete_cost_hints = hints.DELETE_COST_HINTS
    _settle_debt_hints = hints.SETTLE_DEBT_HINTS
    _labor_payable_hints = hints.LABOR_PAYABLE_HINTS
    _labor_settle_hints = hints.LABOR_SETTLE_HINTS
    _wage_record_hints = hints.WAGE_RECORD_HINTS
    _cost_category_hints = hints.COST_CATEGORY_HINTS
    _cost_category_entity_hints = hints.COST_CATEGORY_ENTITY_HINTS
    _cost_category_scope_hints = hints.COST_CATEGORY_SCOPE_HINTS
    _cost_category_delete_hints = hints.COST_CATEGORY_DELETE_HINTS
    _crop_template_hints = hints.CROP_TEMPLATE_HINTS
    _crop_cycle_list_hints = hints.CROP_CYCLE_LIST_HINTS
    _planting_unit_hints = hints.PLANTING_UNIT_HINTS
    _planting_unit_entity_hints = hints.PLANTING_UNIT_ENTITY_HINTS
    _ambiguous_planting_unit_targets = hints.AMBIGUOUS_PLANTING_UNIT_TARGETS
    _planting_unit_update_hints = hints.PLANTING_UNIT_UPDATE_HINTS
    _planting_unit_delete_hints = hints.PLANTING_UNIT_DELETE_HINTS
    _user_settings_hints = hints.USER_SETTINGS_HINTS
    _user_settings_read_hints = hints.USER_SETTINGS_READ_HINTS
    _user_settings_update_patterns = hints.USER_SETTINGS_UPDATE_PATTERNS
    _worker_query_hints = hints.WORKER_QUERY_HINTS

    def classify(self, message: str) -> list[IntentFrame]:
        """按固定规则抽取意图帧。"""
        normalized = message.strip()
        precheck_frames = self._classify_precheck(normalized)
        if precheck_frames is not None:
            return precheck_frames

        frames = self._classify_primary_read(normalized)
        frames.extend(self._classify_additional_reads(normalized))
        frames.extend(self._classify_search_or_weather(normalized))
        frames.extend(self._classify_write_candidates(normalized, frames))
        return frames

    def _classify_precheck(self, message: str) -> list[IntentFrame] | None:
        if not self._looks_like_ambiguous_write(message):
            return None
        return [frame_builders.build_ambiguous_write_frame()]

    def _classify_primary_read(self, message: str) -> list[IntentFrame]:
        if self._looks_like_user_settings_query(message):
            return [frame_builders.build_query_user_settings_frame()]
        if self._looks_like_labor_payable_query(message):
            return [frame_builders.build_query_labor_payables_frame()]
        if self._looks_like_cost_category_query(message):
            return [frame_builders.build_query_cost_categories_frame()]
        if self._looks_like_crop_template_query(message):
            return [frame_builders.build_query_crop_templates_frame()]
        if self._looks_like_planting_unit_query(message):
            return [frame_builders.build_query_planting_units_frame()]
        if self._looks_like_crop_cycle_list_query(message):
            return [frame_builders.build_query_crop_cycles_frame()]
        if self._looks_like_crop_cycle_detail_query(message):
            return [frame_builders.build_query_crop_cycle_frame()]
        if self._looks_like_daily_operation_advice(message):
            return [frame_builders.build_query_daily_operation_advice_frame()]
        if self._looks_like_active_crop_query(message):
            return [frame_builders.build_query_active_crops_frame()]
        if self._looks_like_planting_advice(message):
            return [frame_builders.build_query_planting_advice_frame()]
        if self._looks_like_farm_read(message):
            return [frame_builders.build_unknown_farm_read_frame()]
        return []

    def _classify_additional_reads(self, message: str) -> list[IntentFrame]:
        intent_frames: list[IntentFrame] = []
        if self._looks_like_query_work_orders(message):
            intent_frames.append(frame_builders.build_query_work_orders_frame())
        if self._looks_like_finance_overview_query(message):
            intent_frames.append(frame_builders.build_query_finance_overview_frame())
        if self._looks_like_cost_summary_query(message):
            intent_frames.append(frame_builders.build_query_cost_summary_frame())
        if self._looks_like_cost_analytics_query(message):
            intent_frames.append(frame_builders.build_analyze_cost_frame())
        if self._looks_like_debt_summary_query(message):
            intent_frames.append(frame_builders.build_query_debt_summary_frame())
        if self._looks_like_worker_query(message):
            intent_frames.append(frame_builders.build_query_workers_frame())
        return intent_frames

    def _classify_search_or_weather(self, message: str) -> list[IntentFrame]:
        if self._looks_like_user_settings_query(message) or (
            self._looks_like_update_user_settings(message)
        ):
            return []
        if self._looks_like_web_search(message):
            return [frame_builders.build_query_web_search_frame()]
        if self._looks_like_weather_crop_impact_query(message):
            return [frame_builders.build_query_weather_crop_impact_frame()]
        if self._looks_like_weather_query(message):
            return [frame_builders.build_query_weather_frame()]
        return []

    def _classify_write_candidates(
        self,
        message: str,
        existing_frames: list[IntentFrame],
    ) -> list[IntentFrame]:
        intent_frames: list[IntentFrame] = []
        if self._looks_like_create_worker(message):
            params = self._extract_worker_params(message) or None
            intent_frames.append(frame_builders.build_create_worker_frame(params))
        elif self._looks_like_manage_worker(message):
            params = self._extract_worker_management_params(message) or None
            intent_frames.append(frame_builders.build_manage_worker_frame(params))
        if self._looks_like_create_crop_template(message):
            intent_frames.append(frame_builders.build_create_crop_template_frame())
        if self._looks_like_create_crop_cycle(message):
            intent_frames.append(frame_builders.build_create_crop_cycle_frame())
        if self._looks_like_delete_crop_cycle(message):
            intent_frames.append(frame_builders.build_delete_crop_cycle_frame())
        if self._looks_like_create_cost_record(message):
            intent_frames.append(frame_builders.build_create_cost_record_frame())
        if self._looks_like_delete_cost_record(message):
            intent_frames.append(frame_builders.build_delete_cost_record_frame())
        if self._looks_like_settle_debt(message):
            intent_frames.append(frame_builders.build_settle_debt_frame())
        if self._looks_like_settle_labor_payment(message):
            params = self._extract_labor_payment_params(message)
            intent_frames.append(frame_builders.build_settle_labor_payment_frame(params))
        if self._looks_like_manage_wage(message):
            params = self._extract_wage_params(message)
            intent_frames.append(frame_builders.build_manage_wage_frame(params))
        if self._looks_like_update_user_settings(message):
            intent_frames.append(frame_builders.build_update_user_settings_frame())
        if self._looks_like_manage_cost_category(message):
            action = self._cost_category_action(message)
            intent_frames.append(frame_builders.build_manage_cost_category_frame(action))
        if self._looks_like_manage_planting_unit(message):
            action = self._planting_unit_action(message)
            intent_frames.append(
                frame_builders.build_manage_planting_unit_frame(action)
            )
        if self._looks_like_incomplete_farm_labor_work(message):
            evidence = self._extract_incomplete_farm_labor_evidence(message)
            intent_frames.append(frame_builders.build_clarify_farm_labor_frame(evidence))
        if self._looks_like_create_work_order(message):
            intent_frames.append(
                self._create_work_order_frame(message, existing_frames + intent_frames)
            )
        return intent_frames

    def _extract_labor_payment_params(self, message: str) -> dict:
        params = {"operation": "settle_payment"}
        worker = self._extract_worker_name(message)
        amount = self._extract_money_amount(message)
        if worker:
            params["worker"] = worker
        if amount is not None:
            params["amount"] = amount
        return params

    def _extract_wage_params(self, message: str) -> dict:
        params: dict = {"operation": "manage_wage", "action": "save"}
        worker = self._extract_worker_name(message)
        operation_type = self._extract_operation_type(message)
        quantity = self._extract_labor_quantity(message)
        unit_price = self._extract_unit_price(message)
        if worker:
            params["worker_name"] = worker
        if operation_type:
            params["operation_type"] = operation_type
        if quantity is not None:
            params["quantity"] = quantity
            params["pay_type"] = "daily"
        if unit_price is not None:
            params["unit_price"] = unit_price
        return params

    def _extract_incomplete_farm_labor_evidence(self, message: str) -> dict:
        return self._build_farm_labor_evidence(
            worker=self._extract_worker_name(message),
            operation_type=None,
            quantity=self._extract_labor_quantity(message),
            unit_price=None,
        )

    def _create_work_order_frame(
        self,
        message: str,
        current_frames: list[IntentFrame],
    ) -> IntentFrame:
        work_order_params = self._extract_work_order_params(message)
        depends_on = (
            ["create_worker"]
            if any(frame.intent == "create_worker" for frame in current_frames)
            else []
        )
        return frame_builders.build_create_work_order_frame(
            params_hint=work_order_params or None,
            planning_evidence=self._extract_work_order_evidence(message),
            missing_fields=self._missing_work_order_fields(work_order_params),
            depends_on=depends_on,
        )

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

    def _looks_like_weather_crop_impact_query(self, message: str) -> bool:
        return (
            self._looks_like_weather_query(message)
            and self._has_any(message, self._crop_hints)
            and self._has_any(message, ("影响", "适合", "建议", "要不要"))
        )

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

    def _looks_like_manage_worker(self, message: str) -> bool:
        return (
            self._looks_like_update_worker(message)
            or self._looks_like_deactivate_worker(message)
            or self._looks_like_restore_worker(message)
        )

    def _looks_like_manage_cost_category(self, message: str) -> bool:
        if self._has_any(message, self._query_hints):
            return False
        if not self._has_cost_category_target(message):
            return False
        return self._looks_like_create_action(
            message
        ) or self._looks_like_delete_cost_category(message)

    def _looks_like_manage_planting_unit(self, message: str) -> bool:
        if self._looks_like_planting_unit_query(message):
            return False
        if not self._has_planting_unit_target(message):
            return False
        return (
            self._looks_like_create_action(message)
            or self._looks_like_update_planting_unit(message)
            or self._looks_like_delete_planting_unit(message)
        )

    def _looks_like_create_crop_template(self, message: str) -> bool:
        return "模板" in message and self._looks_like_create_action(message)

    def _looks_like_create_crop_cycle(self, message: str) -> bool:
        if self._has_any(message, self._read_blockers):
            return False
        if self._looks_like_planting_advice(message):
            return False
        if "茬口" in message and self._looks_like_create_action(message):
            return True
        return False

    def _looks_like_delete_crop_cycle(self, message: str) -> bool:
        if self._has_any(message, self._read_blockers):
            return False
        return "茬口" in message and self._has_any(message, ("删除", "删掉", "删"))

    def _looks_like_create_cost_record(self, message: str) -> bool:
        if self._has_any(message, self._read_blockers):
            return False
        if re.search(r"\d+\s*(?:元|块)", message) is None:
            return False
        return self._has_any(message, self._cost_record_write_hints) and self._has_any(
            message,
            self._cost_record_entities,
        )

    def _looks_like_query_work_orders(self, message: str) -> bool:
        return self._has_any(message, self._read_blockers) and self._has_any(
            message, self._work_order_read_hints
        )

    def _looks_like_create_work_order(self, message: str) -> bool:
        if self._looks_like_manage_wage(message):
            return False
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
        if self._looks_like_manage_cost_category(message):
            return False
        return self._has_any(message, self._cost_summary_hints)

    def _looks_like_finance_overview_query(self, message: str) -> bool:
        normalized = message.strip().lower()
        return normalized in self._finance_overview_hints

    def _looks_like_debt_summary_query(self, message: str) -> bool:
        if self._looks_like_labor_payable_query(message):
            return False
        return self._has_any(message, self._debt_summary_hints)

    def _looks_like_cost_analytics_query(self, message: str) -> bool:
        return self._has_any(message, self._cost_analytics_hints)

    def _looks_like_delete_cost_record(self, message: str) -> bool:
        return self._has_any(message, self._delete_cost_hints)

    def _looks_like_settle_debt(self, message: str) -> bool:
        if self._looks_like_debt_summary_query(message):
            return False
        return self._has_any(message, self._settle_debt_hints)

    def _looks_like_labor_payable_query(self, message: str) -> bool:
        if self._looks_like_create_worker(message):
            return False
        if self._looks_like_farm_labor_work(message):
            return False
        if self._looks_like_settle_labor_payment(message):
            return False
        if self._looks_like_manage_wage(message):
            return False
        return self._has_any(message, self._labor_payable_hints)

    def _looks_like_settle_labor_payment(self, message: str) -> bool:
        has_labor = self._has_any(message, ("人工", "工钱", "工资"))
        return has_labor and self._has_any(message, self._labor_settle_hints)

    def _looks_like_manage_wage(self, message: str) -> bool:
        if not self._has_any(message, ("工资", "工钱", "人工费")):
            return False
        if self._looks_like_settle_labor_payment(message):
            return False
        has_record_action = self._has_any(message, self._wage_record_hints)
        has_wage_detail = (
            self._extract_operation_type(message) is not None
            and self._extract_worker_name(message) is not None
            and self._extract_unit_price(message) is not None
        )
        has_work_order_target = self._extract_unit_name(message) is not None or self._has_any(
            message, ("去", "到", "安排", "让", "叫", "派")
        )
        return has_record_action or (has_wage_detail and not has_work_order_target)

    def _looks_like_farm_labor_work(self, message: str) -> bool:
        has_operation = self._extract_operation_type(message) is not None
        has_worker = self._extract_worker_name(message) is not None
        has_labor_hint = bool(
            re.search(r"\d+\s*天", message)
            or self._extract_unit_price(message) is not None
            or self._has_any(message, ("干了", "去", "到", "安排"))
        )
        return has_operation and has_worker and has_labor_hint

    def _looks_like_incomplete_farm_labor_work(self, message: str) -> bool:
        if self._extract_operation_type(message) is not None:
            return False
        has_worker = self._extract_worker_name(message) is not None
        has_quantity = self._extract_labor_quantity(message) is not None
        has_labor_verb = self._has_any(message, ("干了", "做了", "上了"))
        return has_worker and has_quantity and has_labor_verb

    def _looks_like_cost_category_query(self, message: str) -> bool:
        if self._looks_like_manage_cost_category(message):
            return False
        return self._has_any(message, self._cost_category_hints) or (
            "分类" in message and self._has_any(message, self._query_hints)
        )

    def _looks_like_crop_template_query(self, message: str) -> bool:
        if self._looks_like_create_crop_template(message):
            return False
        return self._has_any(message, self._crop_template_hints)

    def _looks_like_crop_cycle_list_query(self, message: str) -> bool:
        return self._has_any(message, self._crop_cycle_list_hints)

    def _looks_like_crop_cycle_detail_query(self, message: str) -> bool:
        if self._looks_like_create_crop_cycle(message):
            return False
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
        return self._has_any(
            message,
            self._user_settings_hints,
        ) and not self._looks_like_update_user_settings(message)

    def _looks_like_update_user_settings(self, message: str) -> bool:
        if self._has_any(message, self._user_settings_read_hints):
            return False
        return self._has_any(message, self._user_settings_hints) and any(
            re.search(pattern, message)
            for pattern in self._user_settings_update_patterns
        )

    def _looks_like_worker_query(self, message: str) -> bool:
        if self._looks_like_create_worker(message):
            return False
        return self._has_any(message, self._worker_query_hints)

    def _looks_like_ambiguous_write(self, message: str) -> bool:
        if self._looks_like_manage_worker(message):
            return False
        if self._looks_like_manage_cost_category(message):
            return False
        if self._looks_like_manage_planting_unit(message):
            return False
        return self._has_any(message, self._write_action_hints) and self._has_any(
            message, self._write_entity_hints
        )

    def _looks_like_update_worker(self, message: str) -> bool:
        has_update_action = self._has_any(message, self._worker_update_hints)
        if not has_update_action:
            return False
        has_update_field = self._has_any(message, self._worker_update_fields)
        return self._has_worker_target(message) and has_update_field

    def _looks_like_deactivate_worker(self, message: str) -> bool:
        has_deactivate_action = self._has_any(message, self._worker_deactivate_hints)
        return has_deactivate_action and self._has_worker_target(message)

    def _looks_like_restore_worker(self, message: str) -> bool:
        has_restore_action = self._has_any(message, self._worker_restore_hints)
        return has_restore_action and self._has_worker_target(message)

    def _has_worker_target(self, message: str) -> bool:
        return self._extract_worker_name(message) is not None

    def _looks_like_delete_cost_category(self, message: str) -> bool:
        has_delete_action = self._has_any(message, self._cost_category_delete_hints)
        return has_delete_action and self._has_explicit_cost_category_scope(message)

    def _has_cost_category_target(self, message: str) -> bool:
        return self._has_any(message, self._cost_category_entity_hints)

    def _has_explicit_cost_category_scope(self, message: str) -> bool:
        return self._has_any(message, self._cost_category_scope_hints) or bool(
            re.search(r"(?:分类|category)\s*#?\s*\d+", message, flags=re.IGNORECASE)
        )

    def _cost_category_action(self, message: str) -> str:
        if self._looks_like_delete_cost_category(message):
            return "delete"
        return "create"

    def _looks_like_update_planting_unit(self, message: str) -> bool:
        has_update_action = self._has_any(message, self._planting_unit_update_hints)
        return has_update_action and self._has_planting_unit_target(message)

    def _looks_like_delete_planting_unit(self, message: str) -> bool:
        has_delete_action = self._has_any(message, self._planting_unit_delete_hints)
        return has_delete_action and self._has_planting_unit_target(message)

    def _has_planting_unit_target(self, message: str) -> bool:
        if self._has_any(message, self._ambiguous_planting_unit_targets):
            return False
        return bool(
            re.search(
                r"[一二三四五六七八九十\d]+\s*号棚"
                r"|[A-Za-z]\s*区"
                r"|(?:地块|大棚|棚区|种植单元)\s*[\u4e00-\u9fa5A-Za-z0-9]{1,8}",
                message,
            )
        )

    def _planting_unit_action(self, message: str) -> str:
        if self._looks_like_delete_planting_unit(message):
            return "delete"
        if self._looks_like_update_planting_unit(message):
            return "update"
        return "create"

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

    def _extract_worker_management_params(self, message: str) -> dict:
        params: dict = {"action": self._worker_management_action(message)}
        name = self._extract_worker_name(message)
        phone = self._extract_phone(message)
        price = self._extract_unit_price(message)
        if name:
            params["name"] = name
        if phone:
            params["phone"] = phone
        if price is not None:
            params["default_unit_price"] = price
            params.setdefault("default_pay_type", "daily")
        return params

    def _worker_management_action(self, message: str) -> str:
        if self._looks_like_deactivate_worker(message):
            return "deactivate"
        if self._looks_like_restore_worker(message):
            return "restore"
        return "update"

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

    def _extract_work_order_evidence(self, message: str) -> dict:
        name = self._extract_worker_name(message)
        operation_type = self._extract_operation_type(message)
        quantity = self._extract_labor_quantity(message)
        unit_price = self._extract_unit_price(message)
        return self._build_farm_labor_evidence(
            worker=name,
            operation_type=operation_type,
            quantity=quantity,
            unit_price=unit_price,
        )

    @staticmethod
    def _build_farm_labor_evidence(
        *,
        worker: str | None,
        operation_type: str | None,
        quantity: int | None,
        unit_price: int | None,
    ) -> dict:
        evidence: dict = {"write_risk": "implicit_farm_labor_work"}
        if worker:
            evidence["worker"] = worker
        if operation_type:
            evidence["operation_type"] = operation_type
        if quantity is not None:
            evidence["quantity"] = quantity
            evidence["pay_type"] = "daily"
        if unit_price is not None:
            evidence["unit_price"] = unit_price
        return evidence

    @staticmethod
    def _missing_work_order_fields(params: dict) -> list[str]:
        missing: list[str] = []
        if not params.get("operation_type"):
            missing.append("operation_type")
        if params.get("workers") and params.get("unit_price") is None:
            missing.append("unit_price_or_default_wage")
        return missing

    @staticmethod
    def _looks_like_create_action(message: str) -> bool:
        return bool(re.search(r"创建|新增|新建|建(?:个|一个)?|添加", message))

    @staticmethod
    def _extract_worker_name(message: str) -> str | None:
        name_chars = r"[\u4e00-\u9fa5A-Za-z0-9]{1,8}"
        patterns = (
            rf"(?:工人|员工|师傅)(?P<name>{name_chars})(?:工资|日薪|每天)",
            r"(?:把|将)?(?P<name>[\u4e00-\u9fa5]{2,4})的(?:电话|手机号|手机)",
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
                name = re.sub(r"^(?:让|叫|安排)", "", name)
                if name not in {"工人", "员工", "师傅"}:
                    return name
        return None

    @staticmethod
    def _extract_unit_price(message: str) -> int | None:
        match = re.search(
            r"(?:工资|日薪|每天|每人|单价)\s*"
            r"(?P<price>\d+)\s*(?:元|块)?\s*(?:一?天|/天|每天)?"
            r"|(?P<price_before>\d+)\s*(?:元|块)\s*(?:一?天|/天|每天|每人)"
            r"|(?P<slash_price>\d+)\s*/天"
            r"|每天\s*(?P<daily_price>\d+)\s*(?:元|块)?",
            message,
        )
        if not match:
            return None
        price = (
            match.group("price")
            or match.group("price_before")
            or match.group("slash_price")
            or match.group("daily_price")
        )
        return int(price)

    @staticmethod
    def _extract_money_amount(message: str) -> int | None:
        match = re.search(r"(?P<amount>\d+)\s*(?:元|块|百|千)?", message)
        if not match:
            return None
        return int(match.group("amount"))

    @staticmethod
    def _extract_phone(message: str) -> str | None:
        match = re.search(r"(?P<phone>1[3-9]\d{9})", message)
        if not match:
            return None
        return match.group("phone")

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
