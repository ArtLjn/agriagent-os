from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


class TraceConfig(BaseModel):
    batch_size: int = 20
    flush_interval: float = 5.0
    max_queue: int = 1000
    trace_ttl_days: int = 7
    token_stats_ttl_days: int = 90


class TokenQuotaConfig(BaseModel):
    daily_limit: int = 100000
    over_quota_action: str = "warn"  # warn / reject / downgrade


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000


_PROJECT_ROOT = Path(__file__).parent.parent.parent

class DatabaseConfig(BaseModel):
    url: str = f"sqlite:///{_PROJECT_ROOT / 'farm_manager.db'}"


class SecretsConfig(BaseModel):
    """统一密钥管理，所有第三方 API key 集中于此。"""
    dashscope_api_key: str = ""
    qweather_api_key: str = ""
    qweather_appid: str = ""
    qweather_appsecret: str = ""
    langsmith_api_key: str = ""


class AIConfig(BaseModel):
    model: str = "qwen3.6-flash-2026-04-16"
    api_key: str = ""
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    enable_thinking: bool = False


class WeatherConfig(BaseModel):
    latitude: float = 34.26
    longitude: float = 117.18


class CircuitBreakerConfig(BaseModel):
    failure_threshold: int = 3
    recovery_timeout: int = 30
    retry_max: int = 3
    retry_backoff_base: float = 2.0


class RateLimitConfig(BaseModel):
    global_requests_per_minute: int = 30
    agent_requests_per_minute: int = 10


class LangSmithConfig(BaseModel):
    api_key: str = ""
    project_name: str = "farm-manager"
    enabled: bool = False


class AuthConfig(BaseModel):
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 10080  # 7 天
    admin_phone: str = ""  # 初始管理员手机号，启动时自动创建
    admin_password: str = ""  # 初始管理员密码，启动时自动创建


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
    circuit_breaker: CircuitBreakerConfig = CircuitBreakerConfig()
    rate_limiting: RateLimitConfig = RateLimitConfig()
    langsmith: LangSmithConfig = LangSmithConfig()
    auth: AuthConfig = AuthConfig()
    trace: TraceConfig = TraceConfig()
    token_quota: TokenQuotaConfig = TokenQuotaConfig()
    secrets: SecretsConfig = SecretsConfig()
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
        sources = [
            s for s in (init_settings, env_settings, yaml_source) if s is not None
        ]
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

    @property
    def circuit_breaker_config(self) -> CircuitBreakerConfig:
        return self.circuit_breaker

    @property
    def rate_limiting_config(self) -> RateLimitConfig:
        return self.rate_limiting

    @property
    def langsmith_config(self) -> LangSmithConfig:
        return self.langsmith

    @property
    def prompts_dir(self) -> Path:
        return Path(__file__).parent.parent.parent / "prompts"


settings = Settings()

__all__ = ["Settings", "settings"]
