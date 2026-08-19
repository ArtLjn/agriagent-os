from business.tools import user_settings


def test_query_user_settings_uses_delegated_user(monkeypatch) -> None:
    monkeypatch.setattr(user_settings, "get_user_id_from_headers", lambda: "user-1")
    monkeypatch.setattr(
        user_settings.user_service,
        "get_user_settings",
        lambda user_id: {
            "user_id": user_id,
            "default_city": "苏州",
            "assistant_role": "concise",
        },
    )

    result = user_settings.manage_user_settings("query")

    assert result["user_id"] == "user-1"
    assert result["configured"] is True
    assert result["settings"]["default_city"] == "苏州"


def test_update_user_settings_rejects_empty_patch(monkeypatch) -> None:
    monkeypatch.setattr(user_settings, "get_user_id_from_headers", lambda: "user-1")

    result = user_settings.manage_user_settings("update")

    assert result["code"] == "missing_setting_fields"
    assert result["retryable"] is False


def test_update_user_settings_passes_only_current_user_and_values(monkeypatch) -> None:
    captured = {}
    monkeypatch.setattr(user_settings, "get_user_id_from_headers", lambda: "user-1")

    def update(user_id, **kwargs):
        captured.update(user_id=user_id, **kwargs)
        return {"user_id": user_id, **kwargs}

    monkeypatch.setattr(user_settings.user_service, "update_user_settings", update)

    result = user_settings.manage_user_settings(
        "update",
        default_city="苏州",
        assistant_role="professional",
    )

    assert captured == {
        "user_id": "user-1",
        "default_city": "苏州",
        "default_lat": None,
        "default_lon": None,
        "assistant_role": "professional",
    }
    assert result["updated"] is True


def test_update_user_settings_rejects_invalid_role(monkeypatch) -> None:
    monkeypatch.setattr(user_settings, "get_user_id_from_headers", lambda: "user-1")

    result = user_settings.manage_user_settings("update", assistant_role="chatty")

    assert result["code"] == "invalid_assistant_role"


def test_user_settings_tool_rejects_unknown_operation(monkeypatch) -> None:
    monkeypatch.setattr(user_settings, "get_user_id_from_headers", lambda: "user-1")

    result = user_settings.manage_user_settings("delete")

    assert result["code"] == "invalid_operation"
