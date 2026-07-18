from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_DATABASE_URL = (
    "mysql+pymysql://farm_manager:password@localhost:3306/farm_manager?charset=utf8mb4"
)


class TraceConfig(BaseModel):
    batch_size: int = 20
    flush_interval: float = 5.0
    max_queue: int = 1000
    trace_ttl_days: int = 7
    token_stats_ttl_days: int = 90


class ReflectionConfig(BaseModel):
    enabled: bool = True
    pre_write_plan: bool = True
    pre_execution: bool = True
    post_tool_result: bool = True
    fallback_guard: bool = True


class TokenQuotaConfig(BaseModel):
    monthly_limit: int = 200000
    weekly_limit: int = 50000
    over_quota_action: str = "reject"


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000


class DatabaseConfig(BaseModel):
    url: str = DEFAULT_DATABASE_URL


class MongoConfig(BaseModel):
    enabled: bool = False
    uri: str = ""
    database: str = "farm_manager"
    tls: bool = False
    connect_timeout_ms: int = Field(default=2000, gt=0)
    server_selection_timeout_ms: int = Field(default=2000, gt=0)
    max_pool_size: int = Field(default=20, gt=0)


StorageBackend = Literal["mysql", "dual", "mongo-read", "mongo"]
DataFlywheelStorageBackend = Literal["mysql", "mongo"]


class StorageConfig(BaseModel):
    trace: StorageBackend = "mysql"
    case_drafts: DataFlywheelStorageBackend = "mysql"
    repair_packs: DataFlywheelStorageBackend = "mysql"
    review_issue_chains: DataFlywheelStorageBackend = "mysql"
    prelabels: DataFlywheelStorageBackend = "mysql"
    conversation_messages: StorageBackend = "mysql"
    agent_records: StorageBackend = "mysql"
    guardrails_logs: StorageBackend = "mysql"
    mongo_write_failure_rate_threshold: float = Field(default=0.001, ge=0)
    mongo_read_error_rate_threshold: float = Field(default=0.01, ge=0)
    mongo_consistency_mismatch_rate_threshold: float = Field(default=0.0001, ge=0)


class SecretsConfig(BaseModel):
    """统一密钥管理，所有第三方 API key 及服务地址集中于此。"""

    dashscope_api_key: str = ""
    qweather_api_key: str = ""
    qweather_appid: str = ""
    qweather_appsecret: str = ""
    langsearch_api_key: str = ""
    langsmith_api_key: str = ""
    searxng_url: str = ""


class AIConfig(BaseModel):
    model: str = "qwen3.6-35b-a3b"
    api_key: str = ""
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    enable_thinking: bool = False
    parallel_tool_calls: bool = True
    failover_max_retries: int = 3
    enable_session_summary: bool = True
    session_summary_message_threshold: int = Field(default=12, gt=0)
    session_summary_debounce_minutes: int = Field(default=30, gt=0)
    session_summary_max_tokens: int = Field(default=500, gt=0)


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
    jwt_expire_minutes: int = 10080
    admin_phone: str = ""
    admin_password: str = ""


class AppConfig(BaseModel):
    apk_download_url: str = ""


class DataFlywheelConfig(BaseModel):
    llm_prelabel_enabled: bool = False


AssistantRole = Literal["professional", "warm", "creative"]
_ROLE_CONFIG_PATH = PROJECT_ROOT / "prompts" / "assistant_roles.yaml"


class YamlSettingsSource(PydanticBaseSettingsSource):
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


def load_yaml(path: str | Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _load_role_config() -> dict:
    """从 prompts 目录读取助手角色配置。"""
    data = yaml.safe_load(_ROLE_CONFIG_PATH.read_text(encoding="utf-8")) or {}
    roles = data.get("roles") or {}
    if not isinstance(roles, dict) or "warm" not in roles:
        raise ValueError("assistant_roles.yaml 缺少 roles.warm 默认角色配置")
    return data


_ROLE_CONFIG = _load_role_config()
_ROLE_DEFINITIONS: dict[str, dict] = _ROLE_CONFIG["roles"]

DEFAULT_ASSISTANT_ROLE: AssistantRole = _ROLE_CONFIG.get("default", "warm")

ASSISTANT_ROLE_LABELS: dict[str, str] = {
    role: str(definition["label"]) for role, definition in _ROLE_DEFINITIONS.items()
}

ASSISTANT_ROLE_TEMPERATURES: dict[str, float] = {
    role: float(definition["temperature"])
    for role, definition in _ROLE_DEFINITIONS.items()
}

ASSISTANT_ROLE_PROMPTS: dict[str, str] = {
    role: str(definition["prompt"]) for role, definition in _ROLE_DEFINITIONS.items()
}


def normalize_assistant_role(value: str | None) -> AssistantRole:
    """归一化助手角色，非法或空值回退到默认角色。"""
    if value in ASSISTANT_ROLE_PROMPTS:
        return value  # type: ignore[return-value]
    return DEFAULT_ASSISTANT_ROLE


def assistant_role_label(value: str | None) -> str:
    """返回助手角色中文标签。"""
    role = normalize_assistant_role(value)
    return ASSISTANT_ROLE_LABELS[role]


def assistant_role_prompt(value: str | None) -> str:
    """返回助手角色对应的 prompt 片段。"""
    role = normalize_assistant_role(value)
    temperature = ASSISTANT_ROLE_TEMPERATURES[role]
    return f"{ASSISTANT_ROLE_PROMPTS[role]} 回复温度参考：{temperature}。"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_nested_delimiter="__")

    server: ServerConfig = ServerConfig()
    database: DatabaseConfig = DatabaseConfig()
    mongodb: MongoConfig = MongoConfig()
    storage: StorageConfig = StorageConfig()
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

__all__ = [
    "AIConfig",
    "ASSISTANT_ROLE_LABELS",
    "ASSISTANT_ROLE_PROMPTS",
    "ASSISTANT_ROLE_TEMPERATURES",
    "AppConfig",
    "AssistantRole",
    "AuthConfig",
    "CircuitBreakerConfig",
    "DEFAULT_ASSISTANT_ROLE",
    "DataFlywheelConfig",
    "DataFlywheelStorageBackend",
    "DatabaseConfig",
    "LangSmithConfig",
    "MongoConfig",
    "PROJECT_ROOT",
    "RateLimitConfig",
    "ReflectionConfig",
    "SecretsConfig",
    "ServerConfig",
    "Settings",
    "StorageBackend",
    "StorageConfig",
    "TokenQuotaConfig",
    "TraceConfig",
    "WeatherConfig",
    "YamlSettingsSource",
    "assistant_role_label",
    "assistant_role_prompt",
    "load_yaml",
    "normalize_assistant_role",
    "settings",
]
