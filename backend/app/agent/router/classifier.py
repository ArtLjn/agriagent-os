"""Skill Router 规则意图分类器。"""

import re

from app.agent.router.models import IntentFrame


class RuleIntentClassifier:
    """基于中文触发词生成轻量意图帧。

    迁移期只保留兼容规则、无工具保护和写风险保护；Registry
    capability/operation enrichment 由 service 与 policy 接管。
    """

    _query_hints = (
        "哪些",
        "有哪些",
        "看看",
        "查询",
        "查一下",
        "最近",
        "怎么样",
        "列表",
    )
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
    _write_entity_hints = (
        "工人",
        "作业",
        "账",
        "分类",
        "种植单元",
        "地块",
        "大棚",
        "棚区",
        "号棚",
    )
    _worker_create_hints = ("新来", "招了", "新增", "创建", "添加")
    _worker_update_hints = ("改", "修改", "更新", "设置", "设为")
    _worker_deactivate_hints = ("删除", "删掉", "删", "停用", "离职", "不用了")
    _worker_restore_hints = ("恢复", "回来", "回来了", "返岗")
    _worker_update_fields = (
        "电话",
        "手机号",
        "手机",
        "工资",
        "日薪",
        "单价",
        "备注",
        "姓名",
        "名字",
        "状态",
    )
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
    _cost_record_write_hints = (
        "买",
        "采购",
        "购入",
        "花了",
        "支出",
        "记一笔",
        "记录",
    )
    _cost_record_entities = (
        "化肥",
        "肥料",
        "种子",
        "农药",
        "农资",
        "成本",
        "费用",
        "支出",
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
    _cost_analytics_hints = ("趋势", "同比", "环比", "比上个月", "比去年", "分析")
    _delete_cost_hints = ("删除账务", "删除账单", "删除流水", "撤销账单", "撤销账务")
    _settle_debt_hints = ("还钱", "还账", "还款", "清账", "结清", "全还")
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
        "查询分类",
    )
    _cost_category_entity_hints = (
        "账务分类",
        "成本分类",
        "收入分类",
        "费用分类",
        "支出分类",
        "分类",
    )
    _cost_category_scope_hints = (
        "账务分类",
        "成本分类",
        "收入分类",
        "费用分类",
        "支出分类",
        "自定义分类",
    )
    _cost_category_delete_hints = ("删除", "删掉", "删")
    _crop_template_hints = (
        "作物模板",
        "模板列表",
        "有哪些模板",
        "生长阶段模板",
    )
    _crop_cycle_list_hints = (
        "我的茬口",
        "有哪些茬口",
        "茬口列表",
        "种植批次",
        "我的作物",
        "有哪些作物栽种",
        "种了哪些作物",
        "种植哪些作物",
        "地里都种着什么",
    )
    _planting_unit_hints = ("种植单元", "地块", "大棚", "棚区", "有哪些棚")
    _planting_unit_entity_hints = (
        "种植单元",
        "地块",
        "大棚",
        "棚区",
        "号棚",
        "区域",
    )
    _ambiguous_planting_unit_targets = (
        "这个地块",
        "这个大棚",
        "这个棚区",
        "这个种植单元",
        "该地块",
        "该大棚",
        "该棚区",
        "该种植单元",
    )
    _planting_unit_update_hints = (
        "改",
        "修改",
        "更新",
        "调整",
        "改成",
        "设为",
        "面积",
    )
    _planting_unit_delete_hints = ("删除", "删掉", "删")
    _user_settings_hints = (
        "用户设置",
        "我的设置",
        "默认天气城市",
        "默认城市",
        "天气城市",
        "默认经纬度",
        "经纬度",
        "经度",
        "纬度",
        "助手回复角色",
        "助手角色",
        "回复角色",
        "显示名",
        "昵称",
    )
    _user_settings_read_hints = (
        "什么",
        "是什么",
        "当前",
        "查看",
        "查询",
        "查一下",
        "看看",
        "多少",
        "有哪些",
    )
    _user_settings_update_patterns = (
        r"(?:把|将).{0,16}(?:改成|设为|换成|调整为|更新为)",
        r"(?:设置|修改|调整|更新).{0,16}(?:为|成)",
        r"(?:改成|设为|换成|调整为|更新为).{0,16}",
        r"(?:修改|调整|更新)(?:用户设置|默认天气城市|默认城市|天气城市|默认经纬度|经纬度|经度|纬度|助手回复角色|助手角色|回复角色|显示名|昵称)",
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

    def _classify_primary_read(self, message: str) -> list[IntentFrame]:
        if self._looks_like_user_settings_query(message):
            return [
                IntentFrame(
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
            ]
        if self._looks_like_labor_payable_query(message):
            return [
                IntentFrame(
                    domain="labor",
                    intent="query_labor_payables",
                    risk="read",
                    entities=["labor_payable"],
                    candidate_tools=["get_labor_payables"],
                    confidence=0.86,
                )
            ]
        if self._looks_like_cost_category_query(message):
            return [
                IntentFrame(
                    domain="finance",
                    intent="query_cost_categories",
                    risk="read",
                    entities=["cost_category"],
                    candidate_tools=["get_cost_categories"],
                    confidence=0.86,
                )
            ]
        if self._looks_like_crop_template_query(message):
            return [
                IntentFrame(
                    domain="planting",
                    intent="query_crop_templates",
                    risk="read",
                    entities=["crop_template"],
                    candidate_tools=["manage_crop_templates"],
                    confidence=0.86,
                )
            ]
        if self._looks_like_planting_unit_query(message):
            return [
                IntentFrame(
                    domain="planting",
                    intent="query_planting_units",
                    risk="read",
                    entities=["planting_unit"],
                    candidate_tools=["get_planting_units"],
                    confidence=0.86,
                )
            ]
        if self._looks_like_crop_cycle_list_query(message):
            return [
                IntentFrame(
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
            ]
        if self._looks_like_crop_cycle_detail_query(message):
            return [
                IntentFrame(
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
            ]
        if self._looks_like_daily_operation_advice(message):
            return [
                IntentFrame(
                    domain="operation",
                    intent="query_daily_operation_advice",
                    risk="read",
                    entities=["weather", "farm", "crop_cycle"],
                    candidate_tools=["get_weather_forecast", "get_farm_status"],
                    confidence=0.84,
                )
            ]
        if self._looks_like_active_crop_query(message):
            return [
                IntentFrame(
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
            ]
        if self._looks_like_planting_advice(message):
            return [
                IntentFrame(
                    domain="planting",
                    intent="query_planting_advice",
                    risk="read",
                    entities=["farm", "crop_cycle"],
                    candidate_tools=["get_farm_status"],
                    confidence=0.72,
                )
            ]
        if self._looks_like_farm_read(message):
            return [
                IntentFrame(
                    domain="farm",
                    intent="unknown_farm_read",
                    risk="read",
                    entities=["farm"],
                    candidate_tools=[],
                    confidence=0.6,
                )
            ]
        return []

    def _classify_additional_reads(self, message: str) -> list[IntentFrame]:
        frames: list[IntentFrame] = []
        if self._looks_like_query_work_orders(message):
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
        if self._looks_like_finance_overview_query(message):
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
        if self._looks_like_cost_summary_query(message):
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
        if self._looks_like_cost_analytics_query(message):
            frames.append(
                IntentFrame(
                    domain="finance",
                    intent="analyze_cost",
                    risk="read",
                    entities=["cost", "income", "trend"],
                    candidate_tools=["get_cost_analytics"],
                    confidence=0.84,
                )
            )
        if self._looks_like_debt_summary_query(message):
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
        if self._looks_like_worker_query(message):
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
        return frames

    def _classify_search_or_weather(self, message: str) -> list[IntentFrame]:
        if self._looks_like_user_settings_query(message) or (
            self._looks_like_update_user_settings(message)
        ):
            return []
        if self._looks_like_web_search(message):
            return [
                IntentFrame(
                    domain="external_search",
                    intent="query_web_search",
                    risk="read",
                    entities=["web"],
                    candidate_tools=["web_search"],
                    confidence=0.8,
                )
            ]
        if self._looks_like_weather_crop_impact_query(message):
            return [
                IntentFrame(
                    domain="operation",
                    intent="query_weather_crop_impact",
                    risk="read",
                    entities=["weather", "farm", "crop_cycle"],
                    candidate_tools=["get_weather_forecast", "get_farm_status"],
                    confidence=0.84,
                )
            ]
        if self._looks_like_weather_query(message):
            return [
                IntentFrame(
                    domain="weather",
                    intent="query_weather",
                    risk="read",
                    entities=["weather"],
                    candidate_tools=["get_weather_forecast"],
                    confidence=0.82,
                )
            ]
        return []

    def _classify_write_candidates(
        self,
        message: str,
        existing_frames: list[IntentFrame],
    ) -> list[IntentFrame]:
        frames: list[IntentFrame] = []
        if self._looks_like_create_worker(message):
            frames.append(self._build_create_worker_frame(message))
        elif self._looks_like_manage_worker(message):
            frames.append(self._build_manage_worker_frame(message))
        if self._looks_like_create_crop_template(message):
            frames.append(self._build_create_crop_template_frame(message))
        if self._looks_like_create_crop_cycle(message):
            frames.append(self._build_create_crop_cycle_frame(message))
        if self._looks_like_delete_crop_cycle(message):
            frames.append(self._build_delete_crop_cycle_frame())
        if self._looks_like_create_cost_record(message):
            frames.append(self._build_create_cost_record_frame())
        if self._looks_like_delete_cost_record(message):
            frames.append(self._build_delete_cost_record_frame())
        if self._looks_like_settle_debt(message):
            frames.append(self._build_settle_debt_frame())
        if self._looks_like_update_user_settings(message):
            frames.append(self._build_update_user_settings_frame())
        if self._looks_like_manage_cost_category(message):
            frames.append(self._build_manage_cost_category_frame(message))
        if self._looks_like_manage_planting_unit(message):
            frames.append(self._build_manage_planting_unit_frame(message))
        if self._looks_like_incomplete_farm_labor_work(message):
            frames.append(self._build_clarify_farm_labor_frame(message))
        if self._looks_like_create_work_order(message):
            frames.append(
                self._build_create_work_order_frame(message, existing_frames + frames)
            )
        return frames

    def _build_create_worker_frame(self, message: str) -> IntentFrame:
        worker_params = self._extract_worker_params(message)
        return IntentFrame(
            domain="labor",
            intent="create_worker",
            risk="write_confirm",
            entities=["worker"],
            candidate_tools=["manage_workers"],
            confidence=0.78,
            params_hint=worker_params or None,
            requires_confirmation=True,
        )

    def _build_manage_worker_frame(self, message: str) -> IntentFrame:
        worker_params = self._extract_worker_management_params(message)
        return IntentFrame(
            domain="labor",
            intent="manage_worker",
            risk="write_confirm",
            entities=["worker"],
            candidate_tools=["manage_workers"],
            confidence=0.78,
            params_hint=worker_params or None,
            requires_confirmation=True,
        )

    def _build_create_crop_template_frame(self, message: str) -> IntentFrame:
        return IntentFrame(
            domain="planting",
            intent="create_crop_template",
            risk="write_confirm",
            entities=["crop_template"],
            candidate_tools=["manage_crop_templates"],
            confidence=0.78,
            requires_confirmation=True,
        )

    def _build_create_crop_cycle_frame(self, message: str) -> IntentFrame:
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

    def _build_delete_crop_cycle_frame(self) -> IntentFrame:
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

    def _build_create_cost_record_frame(self) -> IntentFrame:
        return IntentFrame(
            domain="finance",
            intent="create_cost_record",
            risk="write_confirm",
            entities=["cost"],
            candidate_tools=["create_cost_record"],
            confidence=0.78,
            requires_confirmation=True,
        )

    def _build_delete_cost_record_frame(self) -> IntentFrame:
        return IntentFrame(
            domain="finance",
            intent="delete_record",
            risk="write_high",
            entities=["cost"],
            candidate_tools=["delete_cost_record"],
            confidence=0.78,
            requires_confirmation=True,
        )

    def _build_settle_debt_frame(self) -> IntentFrame:
        return IntentFrame(
            domain="finance",
            intent="settle_debt",
            risk="write_confirm",
            entities=["debt"],
            candidate_tools=["settle_debt"],
            confidence=0.78,
            requires_confirmation=True,
        )

    def _build_update_user_settings_frame(self) -> IntentFrame:
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

    def _build_manage_cost_category_frame(self, message: str) -> IntentFrame:
        return IntentFrame(
            domain="finance",
            intent="manage_cost_category",
            risk="write_confirm",
            entities=["cost_category"],
            candidate_tools=["manage_cost_categories"],
            confidence=0.8,
            params_hint={"action": self._cost_category_action(message)},
            requires_confirmation=True,
        )

    def _build_manage_planting_unit_frame(self, message: str) -> IntentFrame:
        return IntentFrame(
            domain="farm",
            intent="manage_planting_units",
            risk="write_confirm",
            entities=["planting_unit"],
            candidate_tools=["manage_planting_units"],
            confidence=0.8,
            params_hint={"action": self._planting_unit_action(message)},
            requires_confirmation=True,
        )

    def _build_clarify_farm_labor_frame(self, message: str) -> IntentFrame:
        name = self._extract_worker_name(message)
        quantity = self._extract_labor_quantity(message)
        evidence = self._build_farm_labor_evidence(
            worker=name,
            operation_type=None,
            quantity=quantity,
            unit_price=None,
        )
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

    def _build_create_work_order_frame(
        self,
        message: str,
        frames: list[IntentFrame],
    ) -> IntentFrame:
        work_order_params = self._extract_work_order_params(message)
        work_order_evidence = self._extract_work_order_evidence(message)
        work_order_missing = self._missing_work_order_fields(work_order_params)
        depends_on = (
            ["create_worker"]
            if any(frame.intent == "create_worker" for frame in frames)
            else []
        )
        return IntentFrame(
            domain="operation",
            intent="create_work_order",
            risk="write_confirm",
            entities=["operation_work_order"],
            candidate_tools=["create_operation_work_order"],
            confidence=0.76,
            params_hint=work_order_params or None,
            planning_evidence=work_order_evidence,
            missing_fields=work_order_missing,
            depends_on=depends_on,
            requires_confirmation=True,
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
