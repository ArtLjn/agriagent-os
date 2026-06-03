from pydantic import BaseModel

DEFAULT_DATABASE_URL = (
    "mysql+pymysql://farm_manager:password@localhost:3306/"
    "farm_manager?charset=utf8mb4"
)


class TraceConfig(BaseModel):
    batch_size: int = 20
    flush_interval: float = 5.0
    max_queue: int = 1000
    trace_ttl_days: int = 7
    token_stats_ttl_days: int = 90


class TokenQuotaConfig(BaseModel):
    daily_limit: int = 100000
    over_quota_action: str = "warn"


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000


class DatabaseConfig(BaseModel):
    url: str = DEFAULT_DATABASE_URL


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
