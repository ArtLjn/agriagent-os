"""Context policy 单元测试。"""

from app.context.policy import ContextBuildRequest, ContextLayer, ContextPolicy


def _selector_names(result) -> set[str]:
    return {selector.__class__.__name__ for selector in result.selectors}


def test_chat_intent_uses_hot_and_working_core_selectors() -> None:
    result = ContextPolicy().resolve(ContextBuildRequest(intent="chat"))

    assert result.enabled_layers == [ContextLayer.HOT, ContextLayer.WORKING]
    assert result.max_tokens == 512
    selector_names = _selector_names(result)
    assert {
        "FarmSelector",
        "UserSettingsSelector",
        "CycleSelector",
        "MemorySelector",
        "ConversationSelector",
    }.issubset(selector_names)
    assert "LedgerSelector" not in selector_names
    assert "WeatherSelector" not in selector_names


def test_cost_summary_tool_enables_ledger_selector() -> None:
    result = ContextPolicy().resolve(
        ContextBuildRequest(
            intent="chat",
            selected_tool_names=["manage_cost"],
        )
    )

    assert result.max_tokens == 900
    assert "LedgerSelector" in _selector_names(result)


def test_debt_summary_tool_enables_ledger_selector() -> None:
    result = ContextPolicy().resolve(
        ContextBuildRequest(
            intent="chat",
            selected_tool_names=["manage_cost"],
        )
    )

    assert result.max_tokens == 900
    assert "LedgerSelector" in _selector_names(result)


def test_weather_forecast_tool_enables_weather_and_retrieval_layer() -> None:
    result = ContextPolicy().resolve(
        ContextBuildRequest(
            intent="chat",
            selected_tool_names=["weather"],
        )
    )

    assert ContextLayer.RETRIEVAL in result.enabled_layers
    assert "WeatherSelector" in _selector_names(result)


def test_policy_enables_cycle_context_for_update_crop_cycle() -> None:
    result = ContextPolicy().resolve(
        ContextBuildRequest(
            intent="agent",
            selected_tool_names=["update_crop_cycle"],
            farm_id=1,
        )
    )

    assert "CycleSelector" in _selector_names(result)
    assert result.max_tokens >= 700
    assert result.dependency_map["cycle"] == ["crop_cycle"]


def test_policy_uses_skill_metadata_context_dependencies() -> None:
    result = ContextPolicy().resolve(
        ContextBuildRequest(
            intent="agent",
            selected_tool_names=["custom_skill"],
            selected_skill_metadata={
                "custom_skill": {
                    "context_dependencies": [
                        "planting_units",
                        "workers",
                        "unpaid_labor",
                        "weather",
                        "ledger",
                    ]
                }
            },
        )
    )

    selector_names = _selector_names(result)
    assert {
        "PlantingUnitSelector",
        "WorkerSelector",
        "UnpaidLaborSummarySelector",
        "WeatherSelector",
        "LedgerSelector",
    }.issubset(selector_names)
    assert result.dependency_map["planting_units"] == ["planting_units"]
    assert result.dependency_map["workers"] == ["workers"]


def test_router_context_dependencies_drive_selectors() -> None:
    result = ContextPolicy().resolve(
        ContextBuildRequest(
            intent="query",
            selected_tool_names=[],
            context_dependencies=["workers", "planting_units"],
        )
    )

    selector_names = _selector_names(result)
    assert {"WorkerSelector", "PlantingUnitSelector"}.issubset(selector_names)
    assert result.dependency_map["workers"] == ["workers"]
    assert result.dependency_map["planting_units"] == ["planting_units"]


def test_policy_enables_labor_context_for_settle_labor_payment() -> None:
    result = ContextPolicy().resolve(
        ContextBuildRequest(
            intent="agent",
            selected_tool_names=["settle_labor_payment"],
            farm_id=1,
        )
    )

    selector_names = _selector_names(result)
    assert {"WorkerSelector", "UnpaidLaborSummarySelector", "LedgerSelector"}.issubset(
        selector_names
    )
    assert result.dependency_map["workers"] == ["workers"]
    assert result.dependency_map["unpaid_labor"] == ["unpaid_labor"]


def test_policy_enables_work_order_query_context() -> None:
    result = ContextPolicy().resolve(
        ContextBuildRequest(
            intent="agent",
            selected_tool_names=["get_operation_work_orders"],
            farm_id=1,
        )
    )

    selector_names = _selector_names(result)
    assert {
        "CycleSelector",
        "PlantingUnitSelector",
        "OperationWorkOrderSelector",
        "WorkerSelector",
    }.issubset(selector_names)
    assert result.dependency_map["operation_work_orders"] == ["operation_work_orders"]


def test_policy_request_keeps_runtime_identity_and_retrieval_flag() -> None:
    request = ContextBuildRequest(
        intent="query",
        selected_tool_names=[],
        farm_id=1,
        user_id="user-1",
        session_id="session-1",
        include_retrieval=True,
    )

    result = ContextPolicy().resolve(request)

    assert request.farm_id == 1
    assert request.user_id == "user-1"
    assert request.session_id == "session-1"
    assert ContextLayer.RETRIEVAL in result.enabled_layers
    assert "RetrievalSelector" in _selector_names(result)
