"""测试 YAML 配置加载。"""

import os
from unittest.mock import patch

import yaml


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

        from app.core.config import Settings

        settings = Settings(_config_path=str(config_file))
        assert settings.server.host == "127.0.0.1"
        assert settings.server.port == 9000
        assert settings.ai.api_key == "test-key"
        assert settings.weather.latitude == 39.9

    def test_default_values_when_no_yaml(self):
        from app.core.config import Settings

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
            from app.core.config import Settings

            settings = Settings(_config_path=str(config_file))
            assert settings.ai.api_key == "env-key"
        finally:
            del os.environ["AI__API_KEY"]

    def test_backward_compatible_attributes(self):
        from app.core.config import Settings

        settings = Settings(_config_path="/nonexistent/config.yaml")
        assert settings.database_url.startswith("mysql+pymysql://")
        assert settings.project_name == "Farm Manager API"
        assert settings.weather_latitude == 34.26


class TestAIConfig:
    def test_ai_config_default_model(self):
        from app.core.config import AIConfig

        assert AIConfig().model == "qwen3.6-35b-a3b"

    def test_ai_config_default_enable_thinking_false(self):
        from app.core.config import AIConfig

        ai_config = AIConfig()
        assert ai_config.enable_thinking is False

    def test_ai_config_enable_thinking_can_be_set(self):
        from app.core.config import AIConfig

        ai_config = AIConfig(enable_thinking=True)
        assert ai_config.enable_thinking is True
