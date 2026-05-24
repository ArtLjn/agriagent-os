from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000


class DatabaseConfig(BaseModel):
    url: str = "sqlite:///./farm_manager.db"


class AIConfig(BaseModel):
    model: str = "qwen3.5-plus-2026-04-20"
    api_key: str = ""
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"


class WeatherConfig(BaseModel):
    latitude: float = 34.26
    longitude: float = 117.18


class _YamlSettingsSource(PydanticBaseSettingsSource):
    """自定义 YAML 配置源，优先级低于环境变量。"""

    def __init__(self, settings_cls: type, yaml_data: dict):
        super().__init__(settings_cls)
        self._yaml_data = yaml_data

    def get_field_value(self, field, field_name: str):
        return self._yaml_data.get(field_name), field_name, False

    def __call__(self) -> dict:
        result = {}
        for field_name in self.settings_cls.model_fields:
            val, _, _ = self.get_field_value(None, field_name)
            if val is not None:
                result[field_name] = val
        return result


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_nested_delimiter="__")

    server: ServerConfig = ServerConfig()
    database: DatabaseConfig = DatabaseConfig()
    ai: AIConfig = AIConfig()
    weather: WeatherConfig = WeatherConfig()
    project_name: str = "Farm Manager API"

    def __init__(self, _config_path: Optional[str] = None, **kwargs):
        # 从 YAML 加载配置并存到类属性，供 settings_customise_sources 使用
        yaml_data: dict = {}
        if _config_path and Path(_config_path).exists():
            yaml_data = self._load_yaml(_config_path)
        else:
            default_config = Path(__file__).parent.parent.parent / "config.yaml"
            if default_config.exists():
                yaml_data = self._load_yaml(str(default_config))

        self.__class__._yaml_data_store = yaml_data
        super().__init__(**kwargs)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type,
        init_settings: PydanticBaseSettingsSource | None = None,
        env_settings: PydanticBaseSettingsSource | None = None,
        **_kwargs,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # 优先级从高到低：init_settings > env_settings > yaml_source
        yaml_data = getattr(cls, "_yaml_data_store", {})
        yaml_source = _YamlSettingsSource(settings_cls, yaml_data)
        sources = [s for s in (init_settings, env_settings, yaml_source) if s is not None]
        return tuple(sources)

    @staticmethod
    def _load_yaml(path: str) -> dict:
        with open(path) as f:
            return yaml.safe_load(f) or {}

    @property
    def database_url(self) -> str:
        return self.database.url

    @property
    def ai_model(self) -> str:
        return self.ai.model

    @property
    def ai_api_key(self) -> str:
        return self.ai.api_key

    @property
    def ai_base_url(self) -> str:
        return self.ai.base_url

    @property
    def weather_latitude(self) -> float:
        return self.weather.latitude

    @property
    def weather_longitude(self) -> float:
        return self.weather.longitude


settings = Settings()

__all__ = ["Settings", "settings"]
