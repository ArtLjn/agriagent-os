"""Agent 配置加载。

从 agent/config.yaml 读取 Redis、MongoDB + Business MCP 地址。
LLM 仍走 providers.json（在 agri_backend_v2 根目录，agent/llm.py 读）。
环境变量覆盖：MONGODB__URI、BUSINESS_MCP__URL 等。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# agent/config.yaml 的位置（与 agent/ 包同级）。
_CONFIG_FILE = Path(__file__).resolve().parent / "config.yaml"
_SKILL_ROUTER_MODES = frozenset({"main_agent", "llm_router"})


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
    api_url: str = "http://127.0.0.1:9876/api/v2"


@dataclass
class RedisCfg:
    """Agent 并发协调层配置。"""

    enabled: bool = False
    host: str = "127.0.0.1"
    port: int = 6379
    username: str = ""
    password: str = ""
    database: int = 0
    connect_timeout_ms: int = 2000
    socket_timeout_ms: int = 2000
    max_connections: int = 50
    key_prefix: str = "fm:agri_backend_v2:agent:dev"
    global_active_limit: int = 8
    user_active_limit: int = 2
    conversation_lock_ttl_ms: int = 30000
    conversation_lock_renew_ms: int = 10000
    conversation_queue_limit: int = 2
    global_queue_limit: int = 32
    queue_wait_timeout_seconds: int = 30
    turn_execution_timeout_seconds: int = 120
    event_stream_maxlen: int = 1000
    turn_state_ttl_seconds: int = 86400
    approval_ttl_seconds: int = 600
    idempotency_ttl_seconds: int = 86400
    cleanup_interval_seconds: int = 30
    dispatch_stream_ttl_seconds: int = 86400
    worker_count: int = 2
    dispatch_stream: str = "turn:dispatch"
    dispatch_group: str = "agent-workers"


@dataclass
class AuthCfg:
    """认证配置（与 business 共享 JWT secret，用于解析前端传入的 Bearer token）。"""

    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    agent_service_token: str = ""
    jwt_issuer: str = "farm-manager-auth"
    jwt_audience: str | list[str] = "farm-manager-agent"
    delegation_secret: str = ""
    delegation_issuer: str = "farm-manager-agent"
    delegation_audience: str = "farm-manager-business-mcp"


def _default_feature_flags() -> dict[str, bool]:
    """返回 Context 迁移开关的默认值。"""

    return {
        "candidate_tool_schema": False,
        "long_term_memory_observation": False,
    }


@dataclass
class ConversationStateCfg:
    """Conversation state 与短时会话投影配置。"""

    collection: str = "conversationStates"
    summary_ttl_seconds: int = 86400
    recent_turn_limit: int = 6
    pending_action_ttl_seconds: int = 600
    task_state_ttl_seconds: int = 3600


@dataclass
class ContextCfg:
    """Context 构建、预算和迁移开关配置。"""

    conversation_state: ConversationStateCfg = field(
        default_factory=ConversationStateCfg
    )
    summary_soft_ratio: float = 0.60
    summary_hard_ratio: float = 0.80
    response_reserve_tokens: int = 4096
    safety_margin_tokens: int = 1024
    max_tool_result_summary_chars: int = 1200
    tool_schema_mode: str = "all"
    skill_router_mode: str = "main_agent"
    skill_router_backend: str = "llm"
    skill_router_max_skills: int = 3
    skill_router_timeout_seconds: float = 12.0
    feature_flags: dict[str, bool] = field(default_factory=_default_feature_flags)

    @property
    def conversation_state_collection(self) -> str:
        """兼容直接读取 collection 配置的调用方。"""

        return self.conversation_state.collection

    @property
    def summary_ttl_seconds(self) -> int:
        """兼容旧式平铺读取方式。"""

        return self.conversation_state.summary_ttl_seconds

    @property
    def recent_turn_limit(self) -> int:
        """兼容旧式平铺读取方式。"""

        return self.conversation_state.recent_turn_limit


@dataclass
class Settings:
    redis: RedisCfg = field(default_factory=RedisCfg)
    mongodb: MongoCfg = field(default_factory=MongoCfg)
    business_mcp: BusinessMcpCfg = field(default_factory=BusinessMcpCfg)
    auth: AuthCfg = field(default_factory=AuthCfg)
    context: ContextCfg = field(default_factory=ContextCfg)
    environment: str = "development"
    default_farm_id: int = 1
    max_parallel_skills: int = 4

    @property
    def conversation_state(self) -> ConversationStateCfg:
        """提供 Conversation state 的直达兼容入口。"""

        return self.context.conversation_state


def _load_yaml() -> dict:
    if not _CONFIG_FILE.exists():
        return {}
    return yaml.safe_load(_CONFIG_FILE.read_text(encoding="utf-8")) or {}


def _env_bool(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    return value.lower() in {"1", "true", "yes", "on"}


def _first_value(*values: object, default: object) -> object:
    for value in values:
        if value is not None:
            return value
    return default


def _context_raw(raw: dict) -> tuple[dict, dict]:
    context_raw = raw.get("context", {}) or {}
    if not isinstance(context_raw, dict):
        return {}, {}
    state_raw = context_raw.get("conversation_state", {}) or {}
    if not isinstance(state_raw, dict):
        return context_raw, {}
    return context_raw, state_raw


def _build_settings() -> Settings:
    raw = _load_yaml()
    mongo_raw = raw.get("mongodb", {}) or {}
    redis_raw = raw.get("redis", {}) or {}
    mcp_raw = raw.get("business_mcp", {}) or {}
    auth_raw = raw.get("auth", {}) or {}
    context_raw, state_raw = _context_raw(raw)
    feature_flags_raw = dict(raw.get("feature_flags", {}) or {})
    feature_flags_raw.update(context_raw.get("feature_flags", {}) or {})
    feature_flags = _default_feature_flags()
    feature_flags.update(
        {
            str(name): _env_bool(value)
            for name, value in feature_flags_raw.items()
            if str(name) in feature_flags
        }
    )
    state_cfg = ConversationStateCfg(
        collection=str(
            _first_value(
                context_raw.get("conversation_state_collection"),
                state_raw.get("collection"),
                "conversationStates",
                default="conversationStates",
            )
        ),
        summary_ttl_seconds=int(
            _first_value(
                context_raw.get("summary_ttl_seconds"),
                state_raw.get("summary_ttl_seconds"),
                86400,
                default=86400,
            )
        ),
        recent_turn_limit=max(
            1,
            int(
                _first_value(
                    context_raw.get("recent_turn_limit"),
                    state_raw.get("recent_turn_limit"),
                    6,
                    default=6,
                )
            ),
        ),
        pending_action_ttl_seconds=max(
            1,
            int(
                _first_value(
                    context_raw.get("pending_action_ttl_seconds"),
                    state_raw.get("pending_action_ttl_seconds"),
                    600,
                    default=600,
                )
            ),
        ),
        task_state_ttl_seconds=max(
            1,
            int(
                _first_value(
                    context_raw.get("task_state_ttl_seconds"),
                    state_raw.get("task_state_ttl_seconds"),
                    3600,
                    default=3600,
                )
            ),
        ),
    )
    settings = Settings(
        redis=RedisCfg(
            enabled=bool(redis_raw.get("enabled", False)),
            host=str(redis_raw.get("host", "127.0.0.1")),
            port=int(redis_raw.get("port", 6379)),
            username=str(redis_raw.get("username", "")),
            password=str(redis_raw.get("password", "")),
            database=int(redis_raw.get("database", 0)),
            connect_timeout_ms=int(redis_raw.get("connect_timeout_ms", 2000)),
            socket_timeout_ms=int(redis_raw.get("socket_timeout_ms", 2000)),
            max_connections=int(redis_raw.get("max_connections", 50)),
            key_prefix=str(redis_raw.get("key_prefix", "fm:agri_backend_v2:agent:dev")),
            global_active_limit=int(redis_raw.get("global_active_limit", 8)),
            user_active_limit=int(redis_raw.get("user_active_limit", 2)),
            conversation_lock_ttl_ms=int(
                redis_raw.get("conversation_lock_ttl_ms", 30000)
            ),
            conversation_lock_renew_ms=int(
                redis_raw.get("conversation_lock_renew_ms", 10000)
            ),
            conversation_queue_limit=int(redis_raw.get("conversation_queue_limit", 2)),
            global_queue_limit=int(redis_raw.get("global_queue_limit", 32)),
            queue_wait_timeout_seconds=int(
                redis_raw.get("queue_wait_timeout_seconds", 30)
            ),
            turn_execution_timeout_seconds=int(
                redis_raw.get("turn_execution_timeout_seconds", 120)
            ),
            event_stream_maxlen=int(redis_raw.get("event_stream_maxlen", 1000)),
            turn_state_ttl_seconds=int(redis_raw.get("turn_state_ttl_seconds", 86400)),
            approval_ttl_seconds=int(redis_raw.get("approval_ttl_seconds", 600)),
            idempotency_ttl_seconds=int(
                redis_raw.get("idempotency_ttl_seconds", 86400)
            ),
            cleanup_interval_seconds=int(redis_raw.get("cleanup_interval_seconds", 30)),
            dispatch_stream_ttl_seconds=int(
                redis_raw.get("dispatch_stream_ttl_seconds", 86400)
            ),
            worker_count=int(redis_raw.get("worker_count", 2)),
            dispatch_stream=str(redis_raw.get("dispatch_stream", "turn:dispatch")),
            dispatch_group=str(redis_raw.get("dispatch_group", "agent-workers")),
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
        business_mcp=BusinessMcpCfg(
            url=mcp_raw.get("url", "http://127.0.0.1:9876/mcp"),
            api_url=mcp_raw.get("api_url", "http://127.0.0.1:9876/api/v2"),
        ),
        auth=AuthCfg(
            jwt_secret=auth_raw.get("jwt_secret", ""),
            jwt_algorithm=auth_raw.get("jwt_algorithm", "HS256"),
            agent_service_token=auth_raw.get("agent_service_token", ""),
            jwt_issuer=auth_raw.get("jwt_issuer", "farm-manager-auth"),
            jwt_audience=auth_raw.get("jwt_audience", "farm-manager-agent"),
            delegation_secret=auth_raw.get("delegation_secret", ""),
            delegation_issuer=auth_raw.get("delegation_issuer", "farm-manager-agent"),
            delegation_audience=auth_raw.get(
                "delegation_audience", "farm-manager-business-mcp"
            ),
        ),
        context=ContextCfg(
            conversation_state=state_cfg,
            summary_soft_ratio=float(context_raw.get("summary_soft_ratio", 0.60)),
            summary_hard_ratio=float(context_raw.get("summary_hard_ratio", 0.80)),
            response_reserve_tokens=int(
                context_raw.get("response_reserve_tokens", 4096)
            ),
            safety_margin_tokens=int(context_raw.get("safety_margin_tokens", 1024)),
            max_tool_result_summary_chars=int(
                context_raw.get("max_tool_result_summary_chars", 1200)
            ),
            tool_schema_mode=str(context_raw.get("tool_schema_mode", "all")),
            skill_router_mode=str(
                context_raw.get(
                    "skill_router_mode",
                    "llm_router"
                    if context_raw.get("tool_schema_mode") == "candidate"
                    or feature_flags.get("candidate_tool_schema", False)
                    else "main_agent",
                )
            ),
            skill_router_backend=str(
                context_raw.get("skill_router_backend", "llm")
            ),
            skill_router_max_skills=max(
                1, int(context_raw.get("skill_router_max_skills", 3))
            ),
            skill_router_timeout_seconds=max(
                0.1, float(context_raw.get("skill_router_timeout_seconds", 12.0))
            ),
            feature_flags=feature_flags,
        ),
        environment=str(raw.get("environment", "development")),
        default_farm_id=int(raw.get("default_farm_id", 1)),
        max_parallel_skills=max(1, int(raw.get("max_parallel_skills", 4))),
    )
    if env := os.getenv("MONGODB__URI"):
        settings.mongodb.uri = env
    if env := os.getenv("REDIS__HOST"):
        settings.redis.host = env
    if env := os.getenv("REDIS__ENABLED"):
        settings.redis.enabled = env.lower() in {"1", "true", "yes", "on"}
    if env := os.getenv("REDIS__PORT"):
        settings.redis.port = int(env)
    if env := os.getenv("REDIS__USERNAME"):
        settings.redis.username = env
    if env := os.getenv("REDIS__PASSWORD"):
        settings.redis.password = env
    if env := os.getenv("REDIS__DATABASE"):
        settings.redis.database = int(env)
    if env := os.getenv("REDIS__KEY_PREFIX"):
        settings.redis.key_prefix = env
    if env := os.getenv("REDIS__CONNECT_TIMEOUT_MS"):
        settings.redis.connect_timeout_ms = int(env)
    if env := os.getenv("REDIS__SOCKET_TIMEOUT_MS"):
        settings.redis.socket_timeout_ms = int(env)
    if env := os.getenv("REDIS__MAX_CONNECTIONS"):
        settings.redis.max_connections = int(env)
    if env := os.getenv("REDIS__GLOBAL_ACTIVE_LIMIT"):
        settings.redis.global_active_limit = int(env)
    if env := os.getenv("REDIS__USER_ACTIVE_LIMIT"):
        settings.redis.user_active_limit = int(env)
    if env := os.getenv("REDIS__CONVERSATION_LOCK_TTL_MS"):
        settings.redis.conversation_lock_ttl_ms = int(env)
    if env := os.getenv("REDIS__CONVERSATION_LOCK_RENEW_MS"):
        settings.redis.conversation_lock_renew_ms = int(env)
    if env := os.getenv("REDIS__CONVERSATION_QUEUE_LIMIT"):
        settings.redis.conversation_queue_limit = int(env)
    if env := os.getenv("REDIS__GLOBAL_QUEUE_LIMIT"):
        settings.redis.global_queue_limit = int(env)
    if env := os.getenv("REDIS__QUEUE_WAIT_TIMEOUT_SECONDS"):
        settings.redis.queue_wait_timeout_seconds = int(env)
    if env := os.getenv("REDIS__TURN_EXECUTION_TIMEOUT_SECONDS"):
        settings.redis.turn_execution_timeout_seconds = int(env)
    if env := os.getenv("REDIS__EVENT_STREAM_MAXLEN"):
        settings.redis.event_stream_maxlen = int(env)
    if env := os.getenv("REDIS__TURN_STATE_TTL_SECONDS"):
        settings.redis.turn_state_ttl_seconds = int(env)
    if env := os.getenv("REDIS__APPROVAL_TTL_SECONDS"):
        settings.redis.approval_ttl_seconds = int(env)
    if env := os.getenv("REDIS__IDEMPOTENCY_TTL_SECONDS"):
        settings.redis.idempotency_ttl_seconds = int(env)
    if env := os.getenv("REDIS__CLEANUP_INTERVAL_SECONDS"):
        settings.redis.cleanup_interval_seconds = int(env)
    if env := os.getenv("REDIS__DISPATCH_STREAM_TTL_SECONDS"):
        settings.redis.dispatch_stream_ttl_seconds = int(env)
    if env := os.getenv("REDIS__WORKER_COUNT"):
        settings.redis.worker_count = int(env)
    if env := os.getenv("AGENT_MAX_PARALLEL_SKILLS"):
        settings.max_parallel_skills = max(1, int(env))
    if env := os.getenv("BUSINESS_MCP__URL"):
        settings.business_mcp.url = env
    if env := os.getenv("BUSINESS_API__URL"):
        settings.business_mcp.api_url = env
    if env := os.getenv("AGENT_ENV"):
        settings.environment = env.lower().strip()
    if env := os.getenv("JWT_SECRET"):
        settings.auth.jwt_secret = env
    if env := os.getenv("JWT_ISSUER"):
        settings.auth.jwt_issuer = env
    if env := os.getenv("AGENT_JWT_AUDIENCE"):
        settings.auth.jwt_audience = env
    if env := os.getenv("AGENT_SERVICE_TOKEN"):
        settings.auth.agent_service_token = env
    if env := os.getenv("AGENT_DELEGATION_SECRET"):
        settings.auth.delegation_secret = env
    if env := os.getenv("DEFAULT_FARM_ID"):
        settings.default_farm_id = int(env)

    context_env = {
        "conversation_state_collection": os.getenv(
            "CONTEXT__CONVERSATION_STATE_COLLECTION"
        ),
        "summary_ttl_seconds": os.getenv("CONTEXT__SUMMARY_TTL_SECONDS"),
        "recent_turn_limit": os.getenv("CONTEXT__RECENT_TURN_LIMIT"),
        "pending_action_ttl_seconds": os.getenv(
            "CONTEXT__PENDING_ACTION_TTL_SECONDS"
        ),
        "task_state_ttl_seconds": os.getenv("CONTEXT__TASK_STATE_TTL_SECONDS"),
        "summary_soft_ratio": os.getenv("CONTEXT__SUMMARY_SOFT_RATIO"),
        "summary_hard_ratio": os.getenv("CONTEXT__SUMMARY_HARD_RATIO"),
        "response_reserve_tokens": os.getenv("CONTEXT__RESPONSE_RESERVE_TOKENS"),
        "safety_margin_tokens": os.getenv("CONTEXT__SAFETY_MARGIN_TOKENS"),
        "max_tool_result_summary_chars": os.getenv(
            "CONTEXT__MAX_TOOL_RESULT_SUMMARY_CHARS"
        ),
        "tool_schema_mode": os.getenv("CONTEXT__TOOL_SCHEMA_MODE"),
        "skill_router_mode": os.getenv("CONTEXT__SKILL_ROUTER_MODE"),
        "skill_router_backend": os.getenv("CONTEXT__SKILL_ROUTER_BACKEND"),
        "skill_router_max_skills": os.getenv("CONTEXT__SKILL_ROUTER_MAX_SKILLS"),
        "skill_router_timeout_seconds": os.getenv(
            "CONTEXT__SKILL_ROUTER_TIMEOUT_SECONDS"
        ),
    }
    if context_env["conversation_state_collection"]:
        settings.context.conversation_state.collection = context_env[
            "conversation_state_collection"
        ]
    if context_env["summary_ttl_seconds"]:
        settings.context.conversation_state.summary_ttl_seconds = int(
            context_env["summary_ttl_seconds"]
        )
    if context_env["recent_turn_limit"]:
        settings.context.conversation_state.recent_turn_limit = max(
            1, int(context_env["recent_turn_limit"])
        )
    if context_env["pending_action_ttl_seconds"]:
        settings.context.conversation_state.pending_action_ttl_seconds = max(
            1, int(context_env["pending_action_ttl_seconds"])
        )
    if context_env["task_state_ttl_seconds"]:
        settings.context.conversation_state.task_state_ttl_seconds = max(
            1, int(context_env["task_state_ttl_seconds"])
        )
    if context_env["summary_soft_ratio"]:
        settings.context.summary_soft_ratio = float(context_env["summary_soft_ratio"])
    if context_env["summary_hard_ratio"]:
        settings.context.summary_hard_ratio = float(context_env["summary_hard_ratio"])
    if context_env["response_reserve_tokens"]:
        settings.context.response_reserve_tokens = int(
            context_env["response_reserve_tokens"]
        )
    if context_env["safety_margin_tokens"]:
        settings.context.safety_margin_tokens = int(context_env["safety_margin_tokens"])
    if context_env["max_tool_result_summary_chars"]:
        settings.context.max_tool_result_summary_chars = int(
            context_env["max_tool_result_summary_chars"]
        )
    if context_env["tool_schema_mode"]:
        settings.context.tool_schema_mode = context_env["tool_schema_mode"]
    if context_env["skill_router_mode"]:
        settings.context.skill_router_mode = context_env["skill_router_mode"]
    if context_env["skill_router_backend"]:
        settings.context.skill_router_backend = context_env["skill_router_backend"]
    if context_env["skill_router_max_skills"]:
        settings.context.skill_router_max_skills = max(
            1, int(context_env["skill_router_max_skills"])
        )
    if context_env["skill_router_timeout_seconds"]:
        settings.context.skill_router_timeout_seconds = max(
            0.1, float(context_env["skill_router_timeout_seconds"])
        )

    feature_flag_prefixes = (
        "FEATURE_FLAGS__",
        "CONTEXT__FEATURE_FLAGS__",
        "AGENT_FEATURE_FLAGS__",
        "AGENT_FEATURE__",
    )
    for name in settings.context.feature_flags:
        for prefix in feature_flag_prefixes:
            if env := os.getenv(f"{prefix}{name.upper()}"):
                settings.context.feature_flags[name] = _env_bool(env)
                break
    if settings.context.skill_router_mode not in _SKILL_ROUTER_MODES:
        raise ValueError(
            "invalid_skill_router_mode: "
            f"{settings.context.skill_router_mode}; "
            "expected main_agent or llm_router"
        )
    return settings


settings = _build_settings()
