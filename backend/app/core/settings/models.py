from typing import Literal

from pydantic import BaseModel, Field

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
