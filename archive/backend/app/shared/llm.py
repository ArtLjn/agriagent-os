"""LLM Client Manager -- 多 Provider 路由、错误分类 fallback、指数退避 cooldown。"""

import json
import logging
import random
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path

import langchain
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from openai import AsyncOpenAI, OpenAI

from app.shared.config import settings

try:
    from watchfiles import watch as _watchfiles_watch

    _HAS_WATCHFILES = True
except ImportError:
    _HAS_WATCHFILES = False

for _attr in ("verbose", "debug", "llm_cache"):
    if not hasattr(langchain, _attr):
        setattr(langchain, _attr, False)

logger = logging.getLogger(__name__)

_BASE_COOLDOWN_MINUTES = 2
_MAX_COOLDOWN_MINUTES = 1440  # 24h


class ErrorLevel(Enum):
    PROVIDER = "provider"
    MODEL = "model"
    QUOTA_EXHAUSTED = "quota_exhausted"


class LlmNotConfiguredError(Exception):
    """LLM 未配置错误。"""


def get_llm(*, role: str = "generation") -> BaseChatModel:
    """获取 LLM 实例（每次返回新实例以支持负载均衡）。"""
    cb = settings.circuit_breaker_config
    extra_body: dict = {}
    if not settings.ai.enable_thinking:
        extra_body["enable_thinking"] = False

    try:
        manager = get_llm_manager()
        if not manager.fallback_mode:
            llm, info = manager.get_chat_model_with_info(
                role=role,
                temperature=0.7,
                max_retries=cb.retry_max,
                timeout=cb.retry_backoff_base * (2**cb.retry_max) * 2,
                extra_body=extra_body if extra_body else None,
            )
            logger.info(
                (
                    "LLM 请求模型选择 | provider=%s | model=%s | role=%s | "
                    "api_key_slot=%s/%s | circuit_key=%s | base_url=%s"
                ),
                info["provider"],
                info["model"],
                info["role"],
                int(info["api_key_index"]) + 1,
                info["api_key_count"],
                info["circuit_key"],
                info["base_url"],
            )
            return llm
    except Exception as e:
        logger.warning("LLMClientManager 失败，回退 config.yaml | error=%s", e)

    if not settings.ai_api_key:
        raise LlmNotConfiguredError(
            "AI API key 未配置。请在 providers.json 或 config.yaml 中设置。"
        )

    llm = ChatOpenAI(
        model=settings.ai_model,
        api_key=settings.ai_api_key,
        base_url=settings.ai_base_url,
        temperature=0.7,
        streaming=False,
        stream_usage=True,
        max_retries=cb.retry_max,
        timeout=cb.retry_backoff_base * (2**cb.retry_max) * 2,
        extra_body=extra_body if extra_body else None,
    )
    logger.info(
        "LLM 请求模型选择 | provider=config.yaml | model=%s | role=%s | base_url=%s",
        settings.ai_model,
        role,
        settings.ai_base_url,
    )
    return llm


class LLMCircuitState(Enum):
    """LLM Provider/Model 熔断状态。"""

    COOLING = "cooling"
    WARMING = "warming"
    DEAD = "dead"


@dataclass
class CircuitEntry:
    """熔断条目 -- 替代旧的 CooldownEntry。"""

    failures: int = 0
    until: datetime = field(default_factory=datetime.now)
    cooldown_minutes: int = 0
    state: LLMCircuitState = LLMCircuitState.COOLING


@dataclass
class ModelConfig:
    id: str
    priority: int = 1
    enabled: bool = True
    roles: list[str] = field(default_factory=lambda: ["all"])


@dataclass
class ProviderConfig:
    name: str
    base_url: str
    api_keys: list[str]
    priority: int = 99
    weight: int = 1
    enabled: bool = True
    models: list[ModelConfig] = field(default_factory=list)


@dataclass(frozen=True)
class LLMSelection:
    """一次 LLM 路由选择结果，公开日志信息时不包含 api_key。"""

    provider: ProviderConfig
    model: ModelConfig
    api_key: str
    api_key_index: int
    role: str | None

    def _legacy_tuple(self) -> tuple[ProviderConfig, ModelConfig, str]:
        return (self.provider, self.model, self.api_key)

    def __iter__(self):
        return iter(self._legacy_tuple())

    def __getitem__(self, index: int):
        return self._legacy_tuple()[index]

    def public_info(self) -> dict[str, str | int]:
        return {
            "provider": self.provider.name,
            "model": self.model.id,
            "base_url": self.provider.base_url,
            "role": self.role or "all",
            "api_key_index": self.api_key_index,
            "api_key_count": len(self.provider.api_keys),
            "circuit_key": f"{self.provider.name}/{self.model.id}",
        }


def classify_error(exc: Exception) -> ErrorLevel:
    """根据异常类型判断错误级别。"""
    from openai import APIConnectionError, AuthenticationError, RateLimitError

    if isinstance(exc, (APIConnectionError, ConnectionError)):
        return ErrorLevel.PROVIDER

    status_code = getattr(getattr(exc, "response", None), "status_code", None)
    if status_code == 403:
        err_msg = str(getattr(exc, "message", "")) or str(exc)
        if "AllocationQuota.FreeTierOnly" in err_msg:
            return ErrorLevel.QUOTA_EXHAUSTED
        return ErrorLevel.PROVIDER
    if status_code == 401:
        return ErrorLevel.PROVIDER
    if status_code in (429, 404, 400):
        return ErrorLevel.MODEL
    if isinstance(exc, AuthenticationError):
        return ErrorLevel.PROVIDER
    if isinstance(exc, RateLimitError):
        return ErrorLevel.MODEL

    return ErrorLevel.PROVIDER


class LLMClientManager:
    """统一 LLM 客户端管理器。"""

    def __init__(self, config_path: str | None = None):
        self._chain: list[tuple[ProviderConfig, ModelConfig]] = []
        self._cooldowns: dict[str, CircuitEntry] = {}
        self._key_counters: dict[str, int] = {}
        self.fallback_mode: bool = False

        path = config_path or str(
            Path(__file__).parent.parent.parent / "providers.json"
        )
        self._load_config(path)

    def _load_config(self, path: str) -> None:
        try:
            with open(path) as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(
                "providers.json 加载失败，使用 config.yaml 兜底 | error=%s", e
            )
            self.fallback_mode = True
            return

        providers_raw = data.get("providers", [])
        if not providers_raw:
            logger.warning("providers.json 中无 provider，使用 config.yaml 兜底")
            self.fallback_mode = True
            return

        default_name = data.get("default_provider", "")

        for p_raw in providers_raw:
            if not p_raw.get("enabled", True):
                continue
            provider = ProviderConfig(
                name=p_raw["name"],
                base_url=p_raw["base_url"],
                api_keys=p_raw.get("api_keys", []),
                priority=p_raw.get("priority", 99),
                weight=p_raw.get("weight", 1),
                enabled=p_raw.get("enabled", True),
                models=[
                    ModelConfig(
                        id=m["id"],
                        priority=m.get("priority", 1),
                        enabled=m.get("enabled", True),
                        roles=m.get("roles", ["all"]),
                    )
                    for m in p_raw.get("models", [])
                    if m.get("enabled", True)
                ],
            )
            for model in sorted(provider.models, key=lambda m: m.priority):
                self._chain.append((provider, model))

        self._chain.sort(key=lambda item: (item[0].priority, item[1].priority))

        if default_name:
            default_chain = [
                pair for pair in self._chain if pair[0].name == default_name
            ]
            rest_chain = [pair for pair in self._chain if pair[0].name != default_name]
            self._chain = default_chain + rest_chain
        logger.info(
            "LLMClientManager 初始化 | providers=%d | models=%d",
            len({p.name for p, _ in self._chain}),
            len(self._chain),
        )

    @property
    def chain(self) -> list[tuple[ProviderConfig, ModelConfig]]:
        return self._chain

    def _get_api_key(self, provider: ProviderConfig) -> str:
        key, _key_index = self._get_api_key_with_index(provider)
        return key

    def _get_api_key_with_index(self, provider: ProviderConfig) -> tuple[str, int]:
        idx = self._key_counters.get(provider.name, 0)
        key_index = idx % len(provider.api_keys)
        key = provider.api_keys[key_index]
        self._key_counters[provider.name] = idx + 1
        return key, key_index

    def _is_provider_healthy(self, provider_name: str) -> bool:
        """检查 provider 是否健康（<50% 模型处于 WARMING/DEAD）。"""
        provider_models = [m for p, m in self._chain if p.name == provider_name]
        if not provider_models:
            return True
        bad_count = 0
        for m in provider_models:
            key = f"{provider_name}/{m.id}"
            entry = self._cooldowns.get(key)
            if entry and entry.state in (
                LLMCircuitState.WARMING,
                LLMCircuitState.DEAD,
            ):
                bad_count += 1
        return bad_count < len(provider_models) / 2

    def _weighted_random_choice(
        self, candidates: list[tuple[LLMSelection, int]]
    ) -> LLMSelection | None:
        """按权重随机选择一个候选。"""
        if not candidates:
            return None
        total = sum(weight for _, weight in candidates)
        r = random.random() * total
        cumulative = 0
        for selection, weight in candidates:
            cumulative += weight
            if r <= cumulative:
                return selection
        return candidates[-1][0]

    def _get_next_available(
        self,
        role: str | None = None,
    ) -> LLMSelection | None:
        """获取下一个可用的 provider+model+key（加权随机，可选角色筛选）。"""
        seen_providers: set[str] = set()
        exact_candidates: list[tuple[LLMSelection, int]] = []
        fallback_candidates: list[tuple[LLMSelection, int]] = []

        for provider, model in self._chain:
            if not provider.enabled or not model.enabled:
                continue
            if not provider.api_keys:
                continue
            if role is not None:
                is_exact_role = role in model.roles
                is_all_fallback = "all" in model.roles
                if not is_exact_role and not is_all_fallback:
                    continue
            else:
                is_exact_role = True
            model_key = f"{provider.name}/{model.id}"
            if self.is_cooled_down(model_key):
                continue
            if not self._is_provider_healthy(provider.name):
                continue
            if provider.name in seen_providers:
                continue
            seen_providers.add(provider.name)
            api_key, api_key_index = self._get_api_key_with_index(provider)
            if not api_key:
                continue
            candidate = (
                LLMSelection(
                    provider=provider,
                    model=model,
                    api_key=api_key,
                    api_key_index=api_key_index,
                    role=role,
                ),
                provider.weight,
            )
            if is_exact_role:
                exact_candidates.append(candidate)
            else:
                fallback_candidates.append(candidate)

        return self._weighted_random_choice(exact_candidates or fallback_candidates)

    def _get_first_available(
        self,
    ) -> LLMSelection | None:
        """获取第一个未 cooldown 的 provider+model+key 组合。"""
        for provider, model in self._chain:
            if not provider.api_keys:
                continue
            model_key = f"{provider.name}/{model.id}"
            if self.is_cooled_down(model_key):
                continue
            api_key, api_key_index = self._get_api_key_with_index(provider)
            if not api_key:
                continue
            return LLMSelection(
                provider=provider,
                model=model,
                api_key=api_key,
                api_key_index=api_key_index,
                role=None,
            )
        return None

    def get_chat_model(
        self, *, role: str | None = "generation", **kwargs
    ) -> ChatOpenAI:
        """获取 ChatOpenAI 实例（给 llm.py / graph.py 使用）。"""
        llm, _info = self.get_chat_model_with_info(role=role, **kwargs)
        return llm

    def get_chat_model_with_info(
        self, *, role: str | None = "generation", **kwargs
    ) -> tuple[ChatOpenAI, dict[str, str | int]]:
        """获取 ChatOpenAI 实例和同一次路由选择的公开信息。"""
        result = self._get_next_available(role=role)
        if not result:
            raise RuntimeError("所有 LLM Provider 均不可用或处于 cooldown 中")

        extra_body = kwargs.pop("extra_body", None)
        if not settings.ai.enable_thinking:
            extra_body = {**(extra_body or {}), "enable_thinking": False}

        llm = ChatOpenAI(
            model=result.model.id,
            api_key=result.api_key,
            base_url=result.provider.base_url,
            temperature=kwargs.pop("temperature", 0.7),
            streaming=kwargs.pop("streaming", False),
            stream_usage=True,
            extra_body=extra_body if extra_body else None,
            **kwargs,
        )
        return llm, result.public_info()

    def get_sync_client(self, *, role: str | None = "generation") -> OpenAI:
        """获取同步 OpenAI 客户端（给 tool_selector 使用）。"""
        client, _info = self.get_sync_client_with_info(role=role)
        return client

    def get_sync_client_with_info(
        self, *, role: str | None = "generation"
    ) -> tuple[OpenAI, dict[str, str | int]]:
        """获取同步 OpenAI 客户端和同一次路由选择的公开信息。"""
        result = self._get_next_available(role=role)
        if not result:
            raise RuntimeError("所有 LLM Provider 均不可用或处于 cooldown 中")
        return (
            OpenAI(api_key=result.api_key, base_url=result.provider.base_url),
            result.public_info(),
        )

    def get_async_client(self, *, role: str | None = None) -> AsyncOpenAI:
        """获取异步 OpenAI 客户端（给 skills 使用）。"""
        client, _info = self.get_async_client_with_info(role=role)
        return client

    def get_async_client_with_info(
        self, *, role: str | None = None
    ) -> tuple[AsyncOpenAI, dict[str, str | int]]:
        """获取异步 OpenAI 客户端和同一次路由选择的公开信息。"""
        result = self._get_next_available(role=role)
        if not result:
            raise RuntimeError("所有 LLM Provider 均不可用或处于 cooldown 中")
        return (
            AsyncOpenAI(api_key=result.api_key, base_url=result.provider.base_url),
            result.public_info(),
        )

    def get_model_info(self, *, role: str | None = "generation") -> dict:
        """返回当前使用的 provider/model 信息。"""
        result = self._get_next_available(role=role)
        if not result:
            return {"provider": "", "model": "", "base_url": ""}
        return {
            "provider": result.provider.name,
            "model": result.model.id,
            "base_url": result.provider.base_url,
        }

    def record_failure(self, key: str, error_level: ErrorLevel | None = None) -> None:
        """记录失败并分级升级熔断状态。"""
        entry = self._cooldowns.get(key, CircuitEntry())
        entry.failures += 1

        if error_level == ErrorLevel.QUOTA_EXHAUSTED:
            entry.state = LLMCircuitState.DEAD
            entry.cooldown_minutes = 0
        elif entry.failures >= 10:
            entry.state = LLMCircuitState.DEAD
            entry.cooldown_minutes = 0
        elif entry.failures >= 4:
            entry.state = LLMCircuitState.WARMING
            entry.cooldown_minutes = 1440
        else:
            entry.state = LLMCircuitState.COOLING
            entry.cooldown_minutes = min(
                _BASE_COOLDOWN_MINUTES * (2 ** (entry.failures - 1)),
                _MAX_COOLDOWN_MINUTES,
            )

        if entry.state != LLMCircuitState.DEAD:
            entry.until = datetime.now() + timedelta(minutes=entry.cooldown_minutes)

        self._cooldowns[key] = entry
        logger.info(
            "circuit | key=%s | failures=%d | state=%s | cooldown=%dmin",
            key,
            entry.failures,
            entry.state.value,
            entry.cooldown_minutes,
        )

    def record_success(self, key: str) -> None:
        """记录成功，清除 cooldown。"""
        self._cooldowns.pop(key, None)

    def is_cooled_down(self, key: str) -> bool:
        """检查是否仍在 cooldown 期内（DEAD 永久返回 True）。"""
        entry = self._cooldowns.get(key)
        if not entry:
            return False
        if entry.state == LLMCircuitState.DEAD:
            return True
        return datetime.now() < entry.until

    def reload(self) -> None:
        """热更新：重新加载 providers.json，重置 cooldown 状态。"""
        path = str(Path(__file__).parent.parent.parent / "providers.json")
        self._chain.clear()
        self._key_counters.clear()
        self._cooldowns.clear()
        self.fallback_mode = False
        self._load_config(path)
        logger.info(
            "LLMClientManager 热更新完成 | providers=%d | models=%d",
            len({p.name for p, _ in self._chain}),
            len(self._chain),
        )

    def start_file_watcher(self) -> None:
        """启动后台线程监听 providers.json 变化，自动 reload。"""
        start_llm_config_watcher(self)


def start_llm_config_watcher(manager: object) -> None:
    """启动后台线程监听 providers.json 变化，自动 reload。"""
    if not _HAS_WATCHFILES:
        logger.debug("watchfiles 未安装，跳过自动监听")
        return
    if getattr(manager, "_watcher_started", False):
        return
    setattr(manager, "_watcher_started", True)

    logging.getLogger("watchfiles").setLevel(logging.WARNING)
    logging.getLogger("watchfiles.main").setLevel(logging.WARNING)
    config_path = Path(__file__).parent.parent.parent / "providers.json"

    def _watch() -> None:
        logger.info("providers.json 文件监听已启动 | path=%s", config_path)
        for changes in _watchfiles_watch(config_path.parent):
            for _change_type, changed_path in changes:
                if Path(changed_path).name == config_path.name:
                    logger.info("检测到 providers.json 变化，执行热更新")
                    manager.reload()

    threading.Thread(target=_watch, daemon=True, name="llm-config-watcher").start()


_manager: LLMClientManager | None = None
_manager_lock = threading.Lock()


def get_llm_manager() -> LLMClientManager:
    """获取全局 LLMClientManager 单例（线程安全），首次创建时启动文件监听。"""
    global _manager
    if _manager is None:
        with _manager_lock:
            if _manager is None:
                _manager = LLMClientManager()
                _manager.start_file_watcher()
    return _manager


def reload_llm_config() -> dict:
    """热更新 LLM 配置（Manager 单例）。"""
    global _manager
    with _manager_lock:
        if _manager is not None:
            _manager.reload()
        else:
            _manager = LLMClientManager()

    info = _manager.get_model_info()
    logger.info(
        "LLM 配置热更新 | provider=%s | model=%s", info["provider"], info["model"]
    )
    return info


__all__ = [
    "ChatOpenAI",
    "CircuitEntry",
    "ErrorLevel",
    "LLMClientManager",
    "LLMCircuitState",
    "LLMSelection",
    "LlmNotConfiguredError",
    "ModelConfig",
    "ProviderConfig",
    "classify_error",
    "get_llm",
    "get_llm_manager",
    "reload_llm_config",
    "settings",
    "start_llm_config_watcher",
]
