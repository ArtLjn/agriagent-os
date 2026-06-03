"""Prompt 模板注册表。"""

import logging
import threading
from pathlib import Path
from types import MappingProxyType
from typing import Any

import yaml
from jinja2 import TemplateSyntaxError

from app.prompt.models import PromptVersion

logger = logging.getLogger(__name__)


class PromptRegistry:
    """内存中的 Prompt 模板注册表，支持版本注册和活跃版本选择。"""

    def __init__(self):
        self._lock = threading.RLock()
        self._templates: dict[str, dict[str, PromptVersion]] = {}
        self._active_versions: dict[str, str] = {}

    def register(
        self,
        name: str,
        version: str,
        content: str,
        *,
        metadata: dict[str, Any] | None = None,
        active: bool = False,
    ) -> None:
        """注册一个模板版本。"""
        with self._lock:
            versions = self._templates.setdefault(name, {})
            versions[version] = PromptVersion(
                name=name,
                version=version,
                content=content,
                metadata=MappingProxyType(metadata or {}),
            )
            if active or name not in self._active_versions:
                self._active_versions[name] = version
            logger.debug("Prompt 注册 | name=%s version=%s", name, version)

    def set_active_version(self, name: str, version: str) -> None:
        """设置活跃版本。"""
        with self._lock:
            if name not in self._templates or version not in self._templates[name]:
                raise KeyError(f"无法切换: {name}/{version} 不存在")
            self._active_versions[name] = version
            logger.info("Prompt 版本切换 | name=%s version=%s", name, version)

    def set_default(self, name: str, version: str) -> None:
        """兼容旧 API：设置默认版本。"""
        self.set_active_version(name, version)

    def switch_version(self, name: str, version: str) -> None:
        """兼容旧 API：切换默认版本。"""
        self.set_active_version(name, version)

    def active_version(self, name: str) -> str:
        """返回指定模板的活跃版本。"""
        with self._lock:
            if name not in self._templates:
                raise KeyError(f"Prompt 模板未注册: {name}")
            return self._active_versions[name]

    def get_version(self, name: str, version: str | None = None) -> PromptVersion:
        """获取模板版本对象。"""
        with self._lock:
            versions = self._templates.get(name)
            if not versions:
                raise KeyError(f"Prompt 模板未注册: {name}")
            selected = version or self._active_versions.get(name)
            if selected not in versions:
                raise KeyError(f"Prompt 模板版本未注册: {name}/{selected}")
            return versions[selected]

    def get(self, name: str, version: str | None = None) -> str:
        """获取模板内容，version 为空时取活跃版本。"""
        return self.get_version(name, version).content

    def list_names(self) -> list[str]:
        """列出所有已注册模板名称。"""
        with self._lock:
            return list(self._templates.keys())

    def list_versions(self, name: str) -> list[str]:
        """列出某模板的所有版本。"""
        with self._lock:
            return list(self._templates.get(name, {}).keys())

    def reload(self, prompts_dir: Path | None = None) -> None:
        """从文件系统重新加载所有模板。"""
        with self._lock:
            self._templates.clear()
            self._active_versions.clear()
        if prompts_dir:
            self._load_from_dir(prompts_dir)

    def _load_from_dir(self, prompts_dir: Path) -> None:
        """从 prompts/ 目录加载模板。"""
        config_path = prompts_dir / "config.yaml"
        if not config_path.exists():
            logger.warning("config.yaml 不存在，使用内置默认 prompt")
            return

        config = yaml.safe_load(config_path.read_text()) or {}
        default_version = str(config.get("version", "1.0"))
        active_versions = config.get("active_versions", {}) or {}
        defaults = config.get("defaults", {}) or {}
        templates_config = config.get("templates", {}) or {}

        for name, meta in templates_config.items():
            file_name = meta.get("file", f"{name}.j2")
            file_path = prompts_dir / file_name
            if not file_path.exists():
                logger.warning("模板文件不存在: %s", file_path)
                continue
            try:
                content = file_path.read_text()
                version = str(meta.get("version", default_version))
                self.register(
                    name,
                    version,
                    content,
                    metadata=meta,
                    active=active_versions.get(name) == version,
                )
            except TemplateSyntaxError as exc:
                logger.error("模板语法错误 | file=%s error=%s", file_name, exc)
            except Exception as exc:  # pragma: no cover
                logger.error("加载模板失败 | file=%s error=%s", file_name, exc)

        for name, version in active_versions.items():
            if name in self._templates and version in self._templates[name]:
                self.set_active_version(name, str(version))

        for alias, target in defaults.items():
            self._register_alias(alias, target)

        logger.info("Prompt 加载完成 | count=%d", len(self._templates))

    def _register_alias(self, alias: str, target: str) -> None:
        with self._lock:
            if alias in self._templates or target not in self._templates:
                return
            self._templates[alias] = dict(self._templates[target])
            if target in self._active_versions:
                self._active_versions[alias] = self._active_versions[target]


_registry = PromptRegistry()


def get_registry() -> PromptRegistry:
    """获取全局 PromptRegistry 实例。"""
    return _registry
