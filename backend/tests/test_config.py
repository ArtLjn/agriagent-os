"""测试 YAML 配置加载。"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from pydantic import ValidationError


class TestYamlConfig:
    def test_load_from_yaml_file(self, tmp_path):
        config_data = {
            "server": {"host": "127.0.0.1", "port": 9000},
            "database": {
                "url": "mysql+pymysql://tester:pass@localhost:3306/test_db"
                "?charset=utf8mb4"
            },
            "ai": {
                "model": "test-model",
                "api_key": "test-key",
                "base_url": "http://localhost:11434",
            },
            "weather": {"latitude": 39.9, "longitude": 116.4},
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config_data))

        from app.shared.config import Settings

        settings = Settings(_config_path=str(config_file))
        assert settings.server.host == "127.0.0.1"
        assert settings.server.port == 9000
        assert settings.ai.api_key == "test-key"
        assert settings.weather.latitude == 39.9

    def test_default_values_when_no_yaml(self):
        from app.shared.config import Settings

        # patch Path.exists 让默认 config.yaml 也找不到
        with patch("pathlib.Path.exists", return_value=False):
            settings = Settings(_config_path="/nonexistent/config.yaml")
        assert settings.server.host == "0.0.0.0"
        assert settings.server.port == 8000
        assert settings.database.url.startswith("mysql+pymysql://")

    def test_env_var_overrides_yaml(self, tmp_path):
        config_data = {
            "ai": {"api_key": "yaml-key", "base_url": "http://yaml-url"},
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config_data))

        # pydantic-settings 嵌套模型使用双下划线分隔环境变量
        os.environ["AI__API_KEY"] = "env-key"
        try:
            from app.shared.config import Settings

            settings = Settings(_config_path=str(config_file))
            assert settings.ai.api_key == "env-key"
        finally:
            del os.environ["AI__API_KEY"]

    def test_farm_manager_env_loads_dev_config(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.dev.yaml"
        config_file.write_text(yaml.dump({"server": {"port": 8101}}))

        from app.shared import config as config_module

        monkeypatch.setattr(config_module, "PROJECT_ROOT", tmp_path)
        monkeypatch.setenv("FARM_MANAGER_ENV", "dev")

        settings = config_module.Settings()

        assert settings.server.port == 8101

    def test_farm_manager_env_loads_prod_config(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.prod.yaml"
        config_file.write_text(yaml.dump({"server": {"port": 8102}}))

        from app.shared import config as config_module

        monkeypatch.setattr(config_module, "PROJECT_ROOT", tmp_path)
        monkeypatch.setenv("FARM_MANAGER_ENV", "prod")

        settings = config_module.Settings()

        assert settings.server.port == 8102

    def test_explicit_config_path_overrides_farm_manager_env(
        self,
        tmp_path,
        monkeypatch,
    ):
        (tmp_path / "config.dev.yaml").write_text(yaml.dump({"server": {"port": 8101}}))
        explicit_config = tmp_path / "custom.yaml"
        explicit_config.write_text(yaml.dump({"server": {"port": 8103}}))

        from app.shared import config as config_module

        monkeypatch.setattr(config_module, "PROJECT_ROOT", tmp_path)
        monkeypatch.setenv("FARM_MANAGER_ENV", "dev")

        settings = config_module.Settings(_config_path=str(explicit_config))

        assert settings.server.port == 8103

    def test_env_config_must_exist_when_selected(self, tmp_path, monkeypatch):
        from app.shared import config as config_module

        monkeypatch.setattr(config_module, "PROJECT_ROOT", tmp_path)
        monkeypatch.setenv("FARM_MANAGER_ENV", "prod")

        with pytest.raises(FileNotFoundError, match="CONFIG_FILE_NOT_FOUND"):
            config_module.Settings()

    def test_backward_compatible_attributes(self):
        from app.shared.config import Settings

        settings = Settings(_config_path="/nonexistent/config.yaml")
        assert settings.database_url.startswith("mysql+pymysql://")
        assert settings.project_name == "Farm Manager API"
        assert settings.weather_latitude == 34.26

    def test_data_flywheel_llm_prelabel_defaults_to_false(self):
        from app.shared.config import Settings

        with patch("pathlib.Path.exists", return_value=False):
            settings = Settings(_config_path="/nonexistent/config.yaml")

        assert settings.data_flywheel.llm_prelabel_enabled is False

    def test_data_flywheel_llm_prelabel_can_be_enabled_from_yaml(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump({"data_flywheel": {"llm_prelabel_enabled": True}})
        )

        from app.shared.config import Settings

        settings = Settings(_config_path=str(config_file))

        assert settings.data_flywheel.llm_prelabel_enabled is True

    def test_config_example_covers_settings_schema(self):
        from app.shared.config import Settings

        config_file = Path(__file__).resolve().parents[1] / "config.yaml.example"
        data = yaml.safe_load(config_file.read_text()) or {}

        missing_sections = set(Settings.model_fields) - set(data)
        assert missing_sections == set()

        for section_name, field in Settings.model_fields.items():
            section_model = getattr(field.annotation, "model_fields", None)
            if not section_model:
                continue
            missing_keys = set(section_model) - set(data[section_name])
            assert missing_keys == set()


class TestAIConfig:
    def test_ai_config_default_model(self):
        from app.shared.config import AIConfig

        assert AIConfig().model == "qwen3.6-35b-a3b"

    def test_ai_config_default_enable_thinking_false(self):
        from app.shared.config import AIConfig

        ai_config = AIConfig()
        assert ai_config.enable_thinking is False

    def test_ai_config_enable_thinking_can_be_set(self):
        from app.shared.config import AIConfig

        ai_config = AIConfig(enable_thinking=True)
        assert ai_config.enable_thinking is True

    def test_ai_config_session_summary_defaults(self):
        from app.shared.config import AIConfig

        ai_config = AIConfig()

        assert ai_config.enable_session_summary is True
        assert ai_config.session_summary_message_threshold == 12
        assert ai_config.session_summary_debounce_minutes == 30
        assert ai_config.session_summary_max_tokens == 500

    @pytest.mark.parametrize(
        "field_name",
        [
            "session_summary_message_threshold",
            "session_summary_debounce_minutes",
            "session_summary_max_tokens",
        ],
    )
    def test_ai_config_session_summary_numeric_values_must_be_positive(
        self,
        field_name,
    ):
        from app.shared.config import AIConfig

        with pytest.raises(ValidationError):
            AIConfig(**{field_name: 0})
