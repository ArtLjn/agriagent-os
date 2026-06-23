"""数据飞轮问题候选规则检测测试。"""

from app.services.data_flywheel_issue_detector import detect_issue_candidates


def _candidate_types(candidates: list[dict[str, str]]) -> list[str]:
    return [item["type"] for item in candidates]


def test_detects_disabled_worker_used_from_tool_result() -> None:
    candidates = detect_issue_candidates(
        user_input="今天李一凡去5号棚收水稻，工资100一天",
        assistant_reply="已安排李一凡去5号棚收水稻。",
        selected_tools=["create_operation_work_order"],
        events=[
            {
                "event_type": "tool.call.finished",
                "payload": {
                    "tool_name": "create_operation_work_order",
                    "params": {
                        "workers": "李一凡",
                        "unit_price": 100,
                    },
                    "result": {
                        "labor_entries": [
                            {
                                "worker_name": "李一凡",
                                "worker_status": "inactive",
                            }
                        ]
                    },
                },
            }
        ],
        pending_lifecycle=[
            {
                "event_type": "pending.plan.created",
                "payload": {
                    "steps": [{"skill_name": "create_operation_work_order"}],
                },
            }
        ],
    )

    assert candidates == [
        {
            "type": "disabled_worker_used",
            "severity": "high",
            "reason": "已停用工人「李一凡」仍被安排到作业或工资记录中",
            "evidence": "李一凡",
            "suggested_label": "disabled_worker_used",
        }
    ]


def test_detects_missing_wage_when_work_order_has_workers_without_wage_policy() -> None:
    candidates = detect_issue_candidates(
        user_input="今天王大妈去5号棚收水稻",
        assistant_reply="已安排王大妈去5号棚收水稻。",
        selected_tools=["create_operation_work_order"],
        events=[
            {
                "event_type": "tool.call.finished",
                "payload": {
                    "tool_name": "create_operation_work_order",
                    "params": {
                        "workers": "王大妈",
                        "operation_type": "收水稻",
                    },
                    "result": {"id": 9},
                },
            }
        ],
        pending_lifecycle=[
            {
                "event_type": "pending.plan.created",
                "payload": {
                    "steps": [{"skill_name": "create_operation_work_order"}],
                },
            }
        ],
    )

    assert candidates == [
        {
            "type": "missing_wage",
            "severity": "high",
            "reason": "作业包含工人「王大妈」，但没有工资单价、已付金额、不计工资或欠款策略",
            "evidence": "王大妈",
            "suggested_label": "missing_wage",
        }
    ]


def test_detects_missing_wage_when_work_order_only_has_quantity() -> None:
    candidates = detect_issue_candidates(
        user_input="今天王大妈去5号棚收水稻1亩",
        assistant_reply="已安排王大妈去5号棚收水稻。",
        selected_tools=["create_operation_work_order"],
        events=[
            {
                "event_type": "tool.call.finished",
                "payload": {
                    "tool_name": "create_operation_work_order",
                    "params": {
                        "workers": "王大妈",
                        "operation_type": "收水稻",
                        "quantity": 1,
                    },
                    "result": {"id": 9},
                },
            }
        ],
        pending_lifecycle=[
            {
                "event_type": "pending.plan.created",
                "payload": {
                    "steps": [{"skill_name": "create_operation_work_order"}],
                },
            }
        ],
    )

    assert {
        "type": "missing_wage",
        "severity": "high",
        "reason": "作业包含工人「王大妈」，但没有工资单价、已付金额、不计工资或欠款策略",
        "evidence": "王大妈",
        "suggested_label": "missing_wage",
    } in candidates


def test_no_missing_wage_when_no_wage_policy_is_explicit() -> None:
    candidates = detect_issue_candidates(
        user_input="今天王大妈帮忙巡棚，不计工资",
        assistant_reply="已记录王大妈巡棚，本次不计工资。",
        selected_tools=["create_operation_work_order"],
        events=[
            {
                "event_type": "tool.call.finished",
                "payload": {
                    "tool_name": "create_operation_work_order",
                    "params": {
                        "workers": "王大妈",
                        "operation_type": "巡棚",
                        "wage_policy": "no_wage",
                    },
                    "result": {"id": 10},
                },
            }
        ],
        pending_lifecycle=[
            {
                "event_type": "pending.plan.created",
                "payload": {
                    "steps": [{"skill_name": "create_operation_work_order"}],
                },
            }
        ],
    )

    assert "missing_wage" not in _candidate_types(candidates)


def test_detects_pending_missed_for_each_uncovered_write_tool() -> None:
    candidates = detect_issue_candidates(
        user_input="停用李一凡，再安排王大妈去5号棚收水稻，工资100一天",
        assistant_reply="已停用李一凡，并已安排王大妈去5号棚收水稻。",
        selected_tools=["manage_workers", "create_operation_work_order"],
        events=[
            {
                "event_type": "tool.call.finished",
                "payload": {
                    "tool_name": "manage_workers",
                    "params": {"action": "deactivate", "name": "李一凡"},
                    "result": {"id": 3},
                },
            },
            {
                "event_type": "tool.call.finished",
                "payload": {
                    "tool_name": "create_operation_work_order",
                    "params": {"workers": "王大妈", "unit_price": 100},
                    "result": {"id": 9},
                },
            },
        ],
        pending_lifecycle=[
            {
                "event_type": "pending.plan.created",
                "payload": {
                    "steps": [{"skill_name": "manage_workers"}],
                },
            }
        ],
    )

    pending_candidates = [
        item for item in candidates if item["type"] == "pending_missed"
    ]
    assert pending_candidates == [
        {
            "type": "pending_missed",
            "severity": "high",
            "reason": "router 选择了写操作工具「create_operation_work_order」，但 pending lifecycle 中没有对应的确认计划",
            "evidence": "create_operation_work_order",
            "suggested_label": "pending_missed",
        }
    ]


def test_detects_tool_error_ignored_with_specific_label() -> None:
    candidates = detect_issue_candidates(
        user_input="给王大妈记一笔工资100元",
        assistant_reply="已保存工资：王大妈 应付100元。",
        selected_tools=["manage_wages"],
        events=[
            {
                "event_type": "tool.call.failed",
                "payload": {
                    "tool_name": "manage_wages",
                    "error": "新增工资需要关联茬口 cycle_id。",
                },
            }
        ],
        pending_lifecycle=[
            {
                "event_type": "pending.plan.created",
                "payload": {"steps": [{"skill_name": "manage_wages"}]},
            }
        ],
    )

    assert {
        "type": "tool_error_ignored",
        "severity": "medium",
        "reason": "工具「manage_wages」调用失败后，回复仍呈现为已完成",
        "evidence": "manage_wages",
        "suggested_label": "tool_error_ignored",
    } in candidates


def test_detects_no_tool_success_claim_as_hallucinated_execution() -> None:
    candidates = detect_issue_candidates(
        user_input="李海这个月干了15天压瓜",
        assistant_reply="已为您记录：李海这个月干了15天压瓜。",
        selected_tools=[],
        events=[],
        pending_lifecycle=[],
    )

    assert candidates == [
        {
            "type": "hallucinated_execution",
            "severity": "high",
            "reason": "回复声称已执行写入，但选中工具「无」未成功调用",
            "evidence": "无",
            "suggested_label": "hallucinated_execution",
        }
    ]


def test_detects_missing_tool_selection_for_realtime_query() -> None:
    candidates = detect_issue_candidates(
        user_input="今天适合做什么",
        assistant_reply="需要先调用工具获取真实数据，请稍后重试。",
        selected_tools=[],
        events=[],
        pending_lifecycle=[],
    )

    assert candidates == [
        {
            "type": "wrong_tool_selection",
            "severity": "high",
            "reason": "用户输入「今天适合做什么」需要实时/外部数据，但 router 没有选择任何工具",
            "evidence": "今天适合做什么",
            "suggested_label": "wrong_tool_selection",
        }
    ]
