"""Skill Router 规则意图分类器。"""

from app.agent.router import classifier_extractors as extractors
from app.agent.router import classifier_frames as frame_builders
from app.agent.router import classifier_signals as signals
from app.agent.router.models import IntentFrame


class RuleIntentClassifier:
    """基于中文触发词生成轻量意图帧。

    迁移期只保留兼容规则、无工具保护和写风险保护；Registry
    capability/operation enrichment 由 service 与 policy 接管。
    """

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
        if not signals.looks_like_ambiguous_write(message):
            return None
        return [frame_builders.build_ambiguous_write_frame()]

    def _classify_primary_read(self, message: str) -> list[IntentFrame]:
        if signals.looks_like_user_settings_query(message):
            return [frame_builders.build_query_user_settings_frame()]
        if signals.looks_like_labor_payable_query(message):
            return [frame_builders.build_query_labor_payables_frame()]
        if signals.looks_like_cost_category_query(message):
            return [frame_builders.build_query_cost_categories_frame()]
        if signals.looks_like_crop_template_query(message):
            return [frame_builders.build_query_crop_templates_frame()]
        if signals.looks_like_planting_unit_query(message):
            return [frame_builders.build_query_planting_units_frame()]
        if signals.looks_like_crop_cycle_list_query(message):
            return [frame_builders.build_query_crop_cycles_frame()]
        if signals.looks_like_crop_cycle_detail_query(message):
            return [frame_builders.build_query_crop_cycle_frame()]
        if signals.looks_like_daily_operation_advice(message):
            return [frame_builders.build_query_daily_operation_advice_frame()]
        if signals.looks_like_active_crop_query(message):
            return [frame_builders.build_query_active_crops_frame()]
        if signals.looks_like_planting_advice(message):
            return [frame_builders.build_query_planting_advice_frame()]
        if signals.looks_like_farm_read(message):
            return [frame_builders.build_unknown_farm_read_frame()]
        return []

    def _classify_additional_reads(self, message: str) -> list[IntentFrame]:
        intent_frames: list[IntentFrame] = []
        if signals.looks_like_query_work_orders(message):
            intent_frames.append(frame_builders.build_query_work_orders_frame())
        if signals.looks_like_finance_overview_query(message):
            intent_frames.append(frame_builders.build_query_finance_overview_frame())
        if signals.looks_like_cost_summary_query(message):
            intent_frames.append(frame_builders.build_query_cost_summary_frame())
        if signals.looks_like_cost_analytics_query(message):
            intent_frames.append(frame_builders.build_analyze_cost_frame())
        if signals.looks_like_debt_summary_query(message):
            intent_frames.append(frame_builders.build_query_debt_summary_frame())
        if signals.looks_like_worker_query(message):
            intent_frames.append(frame_builders.build_query_workers_frame())
        return intent_frames

    def _classify_search_or_weather(self, message: str) -> list[IntentFrame]:
        if signals.looks_like_user_settings_query(message) or (
            signals.looks_like_update_user_settings(message)
        ):
            return []
        if signals.looks_like_web_search(message):
            return [frame_builders.build_query_web_search_frame()]
        if signals.looks_like_weather_crop_impact_query(message):
            return [frame_builders.build_query_weather_crop_impact_frame()]
        if signals.looks_like_weather_query(message):
            return [frame_builders.build_query_weather_frame()]
        return []

    def _classify_write_candidates(
        self,
        message: str,
        existing_frames: list[IntentFrame],
    ) -> list[IntentFrame]:
        intent_frames: list[IntentFrame] = []
        if signals.looks_like_create_worker(message):
            params = extractors.extract_worker_params(message) or None
            intent_frames.append(frame_builders.build_create_worker_frame(params))
        elif signals.looks_like_manage_worker(message):
            params = self._extract_worker_management_params(message) or None
            intent_frames.append(frame_builders.build_manage_worker_frame(params))
        if signals.looks_like_create_crop_template(message):
            intent_frames.append(frame_builders.build_create_crop_template_frame())
        if signals.looks_like_create_crop_cycle(message):
            intent_frames.append(frame_builders.build_create_crop_cycle_frame())
        if signals.looks_like_delete_crop_cycle(message):
            intent_frames.append(frame_builders.build_delete_crop_cycle_frame())
        if signals.looks_like_create_cost_record(message):
            intent_frames.append(frame_builders.build_create_cost_record_frame())
        if signals.looks_like_delete_cost_record(message):
            intent_frames.append(frame_builders.build_delete_cost_record_frame())
        if signals.looks_like_settle_debt(message):
            intent_frames.append(frame_builders.build_settle_debt_frame())
        if signals.looks_like_settle_labor_payment(message):
            params = extractors.extract_labor_payment_params(message)
            intent_frames.append(frame_builders.build_settle_labor_payment_frame(params))
        if signals.looks_like_manage_wage(message):
            params = extractors.extract_wage_params(message)
            intent_frames.append(frame_builders.build_manage_wage_frame(params))
        if signals.looks_like_update_user_settings(message):
            intent_frames.append(frame_builders.build_update_user_settings_frame())
        if signals.looks_like_manage_cost_category(message):
            action = signals.cost_category_action(message)
            intent_frames.append(frame_builders.build_manage_cost_category_frame(action))
        if signals.looks_like_manage_planting_unit(message):
            action = signals.planting_unit_action(message)
            intent_frames.append(
                frame_builders.build_manage_planting_unit_frame(action)
            )
        if signals.looks_like_incomplete_farm_labor_work(message):
            evidence = extractors.extract_incomplete_farm_labor_evidence(message)
            intent_frames.append(frame_builders.build_clarify_farm_labor_frame(evidence))
        if signals.looks_like_create_work_order(message):
            intent_frames.append(
                self._create_work_order_frame(message, existing_frames + intent_frames)
            )
        return intent_frames

    @staticmethod
    def _extract_worker_management_params(message: str) -> dict:
        action = signals.worker_management_action(message)
        return extractors.extract_worker_management_params(message, action)

    @staticmethod
    def _create_work_order_frame(
        message: str,
        current_frames: list[IntentFrame],
    ) -> IntentFrame:
        work_order_params = extractors.extract_work_order_params(message)
        depends_on = (
            ["create_worker"]
            if any(frame.intent == "create_worker" for frame in current_frames)
            else []
        )
        return frame_builders.build_create_work_order_frame(
            params_hint=work_order_params or None,
            planning_evidence=extractors.extract_work_order_evidence(message),
            missing_fields=extractors.missing_work_order_fields(work_order_params),
            depends_on=depends_on,
        )
