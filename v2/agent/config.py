"""Agent 配置加载。

从 agent/config.yaml 读取 MongoDB + Business MCP 地址。
LLM 仍走 providers.json（在 v2 根目录，agent/llm.py 读）。
环境变量覆盖：MONGODB__URI、BUSINESS_MCP__URL 等。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# agent/config.yaml 的位置（与 agent/ 包同级）。
_CONFIG_FILE = Path(__file__).resolve().parent / "config.yaml"


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
class BusinessMcpCfg:
    url: str = "http://127.0.0.1:9876/mcp"


@dataclass
class Settings:
    mongodb: MongoCfg = field(default_factory=MongoCfg)
    business_mcp: BusinessMcpCfg = field(default_factory=BusinessMcpCfg)


def _load_yaml() -> dict:
    if not _CONFIG_FILE.exists():
        return {}
    return yaml.safe_load(_CONFIG_FILE.read_text(encoding="utf-8")) or {}


def _build_settings() -> Settings:
    raw = _load_yaml()
    mongo_raw = raw.get("mongodb", {}) or {}
    mcp_raw = raw.get("business_mcp", {}) or {}
    settings = Settings(
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
        business_mcp=BusinessMcpCfg(url=mcp_raw.get("url", "http://127.0.0.1:9876/mcp")),
    )
    if env := os.getenv("MONGODB__URI"):
        settings.mongodb.uri = env
    if env := os.getenv("BUSINESS_MCP__URL"):
        settings.business_mcp.url = env
    return settings


settings = _build_settings()
