"""MongoDB 配置解析测试。"""

from unittest.mock import patch

import pytest
import yaml


_STORAGE_ENV_KEYS = (
    "storage__conversation_messages",
    "storage__case_drafts",
    "storage__repair_packs",
    "storage__review_issue_chains",
    "storage__prelabels",
    "storage__trace",
    "storage__agent_records",
    "storage__guardrails_logs",
)


def _clear_storage_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in _STORAGE_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_mongo_config_defaults_disable_client_and_keep_mysql_backends():
    from app.shared.config import Settings

    with patch("pathlib.Path.exists", return_value=False):
        settings = Settings(_config_path="/nonexistent/config.yaml")

    assert settings.mongodb.enabled is False
    assert settings.mongodb.uri == ""
    assert settings.mongodb.database == "farm_manager"
    assert settings.mongodb.tls is False
    assert settings.mongodb.connect_timeout_ms == 2000
    assert settings.mongodb.server_selection_timeout_ms == 2000
    assert settings.mongodb.max_pool_size == 20

    assert settings.storage.trace == "mysql"
    assert settings.storage.case_drafts == "mysql"
    assert settings.storage.repair_packs == "mysql"
    assert settings.storage.review_issue_chains == "mysql"
    assert settings.storage.prelabels == "mysql"
    assert settings.storage.conversation_messages == "mysql"
    assert settings.storage.agent_records == "mysql"
    assert settings.storage.guardrails_logs == "mysql"
    assert settings.storage.mongo_write_failure_rate_threshold == 0.001
    assert settings.storage.mongo_read_error_rate_threshold == 0.01
    assert settings.storage.mongo_consistency_mismatch_rate_threshold == 0.0001


def test_mongo_and_storage_config_load_from_yaml(tmp_path, monkeypatch):
    _clear_storage_env(monkeypatch)

    from app.shared.config import Settings

    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        yaml.dump(
            {
                "mongodb": {
                    "enabled": True,
                    "uri": "mongodb://app:secret@mongo.example:27017/farm_manager",
                    "database": "farm_manager_docs",
                    "tls": True,
                    "connect_timeout_ms": 1500,
                    "server_selection_timeout_ms": 2500,
                    "max_pool_size": 32,
                },
                "storage": {
                    "trace": "dual",
                    "case_drafts": "mongo",
                    "repair_packs": "mongo",
                    "review_issue_chains": "mongo",
                    "prelabels": "mongo",
                    "conversation_messages": "dual",
                    "agent_records": "mongo-read",
                    "guardrails_logs": "mongo",
                    "mongo_write_failure_rate_threshold": 0.002,
                    "mongo_read_error_rate_threshold": 0.02,
                    "mongo_consistency_mismatch_rate_threshold": 0.0002,
                },
            }
        )
    )

    settings = Settings(_config_path=str(config_file))

    assert settings.mongodb.enabled is True
    assert (
        settings.mongodb.uri == "mongodb://app:secret@mongo.example:27017/farm_manager"
    )
    assert settings.mongodb.database == "farm_manager_docs"
    assert settings.mongodb.tls is True
    assert settings.mongodb.connect_timeout_ms == 1500
    assert settings.mongodb.server_selection_timeout_ms == 2500
    assert settings.mongodb.max_pool_size == 32
    assert settings.storage.trace == "dual"
    assert settings.storage.case_drafts == "mongo"
    assert settings.storage.repair_packs == "mongo"
    assert settings.storage.review_issue_chains == "mongo"
    assert settings.storage.prelabels == "mongo"
    assert settings.storage.conversation_messages == "dual"
    assert settings.storage.agent_records == "mongo-read"
    assert settings.storage.guardrails_logs == "mongo"
    assert settings.storage.mongo_write_failure_rate_threshold == 0.002
    assert settings.storage.mongo_read_error_rate_threshold == 0.02
    assert settings.storage.mongo_consistency_mismatch_rate_threshold == 0.0002


def test_data_flywheel_storage_config_rejects_removed_gray_backends(
    tmp_path,
    monkeypatch,
):
    _clear_storage_env(monkeypatch)

    from app.shared.config import Settings

    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        yaml.dump({"storage": {"prelabels": "dual"}}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        Settings(_config_path=str(config_file))
