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
            selected_tool_names=["get_cost_summary"],
        )
    )

    assert result.max_tokens == 900
    assert "LedgerSelector" in _selector_names(result)


def test_weather_forecast_tool_enables_weather_and_retrieval_layer() -> None:
    result = ContextPolicy().resolve(
        ContextBuildRequest(
            intent="chat",
            selected_tool_names=["get_weather_forecast"],
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
