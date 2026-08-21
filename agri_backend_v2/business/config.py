"""Business 配置加载。

从 business/config.yaml 读取，环境变量可覆盖关键字段（DATABASE__URL、SERVER__HOST 等）。

加载入口：
  from business.config import settings
  settings.database.url
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# business/config.yaml 的位置（与 business/ 包同级）。
_CONFIG_FILE = Path(__file__).resolve().parent / "config.yaml"


@dataclass
class ServerCfg:
    host: str = "127.0.0.1"
    port: int = 9876


@dataclass
class DatabaseCfg:
    url: str = ""
    pool_size: int = 5
    max_overflow: int = 10
    pool_recycle: int = 1800
    echo: bool = False


@dataclass
class MongoCfg:
    enabled: bool = False
    uri: str = ""
    database: str = ""
    tls: bool = False
    connect_timeout_ms: int = 2000
    server_selection_timeout_ms: int = 2000
    max_pool_size: int = 20
    collections: dict[str, str] = field(default_factory=dict)


@dataclass
class SecretsCfg:
    qweather_api_key: str = ""
    searchhub_base_url: str = ""
    searchhub_api_key: str = ""


@dataclass
class WeatherCfg:
    latitude: float = 34.26
    longitude: float = 117.18


@dataclass
class AuthCfg:
    """认证配置（JWT、bcrypt、Agent Service Token、初始管理员）。"""

    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "farm-manager-auth"
    jwt_audience: str | list[str] = field(
        default_factory=lambda: ["farm-manager-agent", "farm-manager-business"]
    )
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 天
    bcrypt_rounds: int = 12
    agent_service_token: str = ""
    delegation_secret: str = ""
    delegation_issuer: str = "farm-manager-agent"
    delegation_audience: str = "farm-manager-business-mcp"
    admin_phone: str = ""
    admin_password: str = ""


@dataclass
class TokenQuotaCfg:
    """Token 配额默认值（用户未自定义时使用）。"""

    monthly_limit: int = 1_000_000
    weekly_limit: int = 250_000
    over_quota_action: str = "block"


@dataclass
class Settings:
    server: ServerCfg = field(default_factory=ServerCfg)
    database: DatabaseCfg = field(default_factory=DatabaseCfg)
    mongodb: MongoCfg = field(default_factory=MongoCfg)
    secrets: SecretsCfg = field(default_factory=SecretsCfg)
    weather: WeatherCfg = field(default_factory=WeatherCfg)
    auth: AuthCfg = field(default_factory=AuthCfg)
    token_quota: TokenQuotaCfg = field(default_factory=TokenQuotaCfg)
    default_farm_id: int = 1


def _load_yaml() -> dict:
    if not _CONFIG_FILE.exists():
        return {}
    return yaml.safe_load(_CONFIG_FILE.read_text(encoding="utf-8")) or {}


def _build_settings() -> Settings:
    raw = _load_yaml()
    server_raw = raw.get("server", {}) or {}
    db_raw = raw.get("database", {}) or {}
    mongo_raw = raw.get("mongodb", {}) or {}
    secrets_raw = raw.get("secrets", {}) or {}
    weather_raw = raw.get("weather", {}) or {}
    auth_raw = raw.get("auth", {}) or {}
    quota_raw = raw.get("token_quota", {}) or {}

    settings = Settings(
        server=ServerCfg(
            host=str(server_raw.get("host", "127.0.0.1")),
            port=int(server_raw.get("port", 9876)),
        ),
        database=DatabaseCfg(
            url=db_raw.get("url", ""),
            pool_size=int(db_raw.get("pool_size", 5)),
            max_overflow=int(db_raw.get("max_overflow", 10)),
            pool_recycle=int(db_raw.get("pool_recycle", 1800)),
            echo=bool(db_raw.get("echo", False)),
        ),
        mongodb=MongoCfg(
            enabled=bool(mongo_raw.get("enabled", False)),
            uri=mongo_raw.get("uri", ""),
            database=mongo_raw.get("database", ""),
            tls=bool(mongo_raw.get("tls", False)),
            connect_timeout_ms=int(mongo_raw.get("connect_timeout_ms", 2000)),
            server_selection_timeout_ms=int(
                mongo_raw.get("server_selection_timeout_ms", 2000)
            ),
            max_pool_size=int(mongo_raw.get("max_pool_size", 20)),
            collections=dict(mongo_raw.get("collections", {}) or {}),
        ),
        secrets=SecretsCfg(
            qweather_api_key=secrets_raw.get("qweather_api_key", ""),
            searchhub_base_url=secrets_raw.get("searchhub_base_url", ""),
            searchhub_api_key=secrets_raw.get("searchhub_api_key", ""),
        ),
        weather=WeatherCfg(
            latitude=float(weather_raw.get("latitude", 34.26)),
            longitude=float(weather_raw.get("longitude", 117.18)),
        ),
        auth=AuthCfg(
            jwt_secret=auth_raw.get("jwt_secret", ""),
            jwt_algorithm=auth_raw.get("jwt_algorithm", "HS256"),
            jwt_issuer=auth_raw.get("jwt_issuer", "farm-manager-auth"),
            jwt_audience=auth_raw.get(
                "jwt_audience",
                ["farm-manager-agent", "farm-manager-business"],
            ),
            jwt_expire_minutes=int(auth_raw.get("jwt_expire_minutes", 60 * 24 * 7)),
            bcrypt_rounds=int(auth_raw.get("bcrypt_rounds", 12)),
            agent_service_token=auth_raw.get("agent_service_token", ""),
            delegation_secret=auth_raw.get("delegation_secret", ""),
            delegation_issuer=auth_raw.get("delegation_issuer", "farm-manager-agent"),
            delegation_audience=auth_raw.get(
                "delegation_audience", "farm-manager-business-mcp"
            ),
            admin_phone=auth_raw.get("admin_phone", ""),
            admin_password=auth_raw.get("admin_password", ""),
        ),
        token_quota=TokenQuotaCfg(
            monthly_limit=int(quota_raw.get("monthly_limit", 1_000_000)),
            weekly_limit=int(quota_raw.get("weekly_limit", 250_000)),
            over_quota_action=quota_raw.get("over_quota_action", "block"),
        ),
        default_farm_id=int(raw.get("default_farm_id", 1)),
    )

    # 环境变量覆盖（双下划线分隔命名空间）。
    if env := os.getenv("SERVER__HOST"):
        settings.server.host = env
    if env := os.getenv("SERVER__PORT"):
        settings.server.port = int(env)
    if env := os.getenv("DATABASE__URL"):
        settings.database.url = env
    if env := os.getenv("MONGODB__URI"):
        settings.mongodb.uri = env
    if env := os.getenv("QWEATHER_API_KEY"):
        settings.secrets.qweather_api_key = env
    if env := os.getenv("SEARCHHUB_BASE_URL"):
        settings.secrets.searchhub_base_url = env
    if env := os.getenv("SEARCHHUB_API_KEY"):
        settings.secrets.searchhub_api_key = env
    if env := os.getenv("JWT_SECRET"):
        settings.auth.jwt_secret = env
    if env := os.getenv("JWT_ISSUER"):
        settings.auth.jwt_issuer = env
    if env := os.getenv("JWT_AUDIENCE"):
        settings.auth.jwt_audience = env
    if env := os.getenv("AGENT_SERVICE_TOKEN"):
        settings.auth.agent_service_token = env
    if env := os.getenv("AGENT_DELEGATION_SECRET"):
        settings.auth.delegation_secret = env
    if env := os.getenv("DEFAULT_FARM_ID"):
        settings.default_farm_id = int(env)
    return settings


settings = _build_settings()
