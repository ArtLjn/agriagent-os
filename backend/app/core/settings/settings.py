from pathlib import Path
from typing import Optional

from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from app.core.settings.models import (
    AIConfig,
    AppConfig,
    AuthConfig,
    CircuitBreakerConfig,
    DataFlywheelConfig,
    DatabaseConfig,
    LangSmithConfig,
    RateLimitConfig,
    ReflectionConfig,
    SecretsConfig,
    ServerConfig,
    TokenQuotaConfig,
    TraceConfig,
    WeatherConfig,
)
from app.core.settings.sources import YamlSettingsSource, load_yaml

PROJECT_ROOT = Path(__file__).resolve().parents[3]


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
    reflection: ReflectionConfig = ReflectionConfig()
    token_quota: TokenQuotaConfig = TokenQuotaConfig()
    secrets: SecretsConfig = SecretsConfig()
    app: AppConfig = AppConfig()
    data_flywheel: DataFlywheelConfig = DataFlywheelConfig()
    project_name: str = "Farm Manager API"

    def __init__(self, _config_path: Optional[str] = None, **kwargs):
        yaml_data: dict = {}
        if _config_path and Path(_config_path).exists():
            yaml_data = load_yaml(_config_path)
        else:
            default_config = PROJECT_ROOT / "config.yaml"
            if default_config.exists():
                yaml_data = load_yaml(default_config)

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
        yaml_data = getattr(cls, "_yaml_data_store", {})
        yaml_source = YamlSettingsSource(settings_cls, yaml_data)
        sources = [
            s for s in (init_settings, env_settings, yaml_source) if s is not None
        ]
        return tuple(sources)

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
        return PROJECT_ROOT / "prompts"


settings = Settings()
