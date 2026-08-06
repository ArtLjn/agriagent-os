"""Business 配置加载。

从 business/config.yaml 读取，环境变量可覆盖关键字段（DATABASE__URL、QWEATHER_API_KEY 等）。

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
class Settings:
    database: DatabaseCfg = field(default_factory=DatabaseCfg)
    mongodb: MongoCfg = field(default_factory=MongoCfg)
    secrets: SecretsCfg = field(default_factory=SecretsCfg)
    weather: WeatherCfg = field(default_factory=WeatherCfg)
    default_farm_id: int = 1


def _load_yaml() -> dict:
    if not _CONFIG_FILE.exists():
        return {}
    return yaml.safe_load(_CONFIG_FILE.read_text(encoding="utf-8")) or {}


def _build_settings() -> Settings:
    raw = _load_yaml()
    db_raw = raw.get("database", {}) or {}
    mongo_raw = raw.get("mongodb", {}) or {}
    secrets_raw = raw.get("secrets", {}) or {}
    weather_raw = raw.get("weather", {}) or {}

    settings = Settings(
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
        default_farm_id=int(raw.get("default_farm_id", 1)),
    )

    # 环境变量覆盖（双下划线分隔命名空间）。
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
    if env := os.getenv("DEFAULT_FARM_ID"):
        settings.default_farm_id = int(env)
    return settings


settings = _build_settings()
