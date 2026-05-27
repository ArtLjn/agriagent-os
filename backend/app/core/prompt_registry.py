"""Prompt 模板注册表 — 内存中的模板版本管理，支持热加载。"""

import logging
import threading
from pathlib import Path

import yaml
from jinja2 import TemplateSyntaxError

logger = logging.getLogger(__name__)


class PromptRegistry:
    """内存中的 Prompt 模板注册表，线程安全。"""

    def __init__(self):
        self._lock = threading.RLock()
        self._templates: dict[str, dict[str, str]] = {}
        self._defaults: dict[str, str] = {}

    def register(self, name: str, version: str, content: str) -> None:
        """注册一个模板版本。"""
        with self._lock:
            if name not in self._templates:
                self._templates[name] = {}
                if name not in self._defaults:
                    self._defaults[name] = version
            self._templates[name][version] = content
            logger.debug("Prompt 注册 | name=%s version=%s", name, version)

    def set_default(self, name: str, version: str) -> None:
        """设置默认版本。"""
        with self._lock:
            self._defaults[name] = version

    def get(self, name: str, version: str | None = None) -> str:
        """获取模板内容，version 为 None 时取默认版本。"""
        with self._lock:
            versions = self._templates.get(name)
            if not versions:
                raise KeyError(f"Prompt 模板未注册: {name}")
            v = version or self._defaults.get(name)
            if v not in versions:
                v = next(iter(versions))
            return versions[v]

    def switch_version(self, name: str, version: str) -> None:
        """切换默认版本。"""
        with self._lock:
            if name not in self._templates or version not in self._templates[name]:
                raise KeyError(f"无法切换: {name}/{version} 不存在")
            self._defaults[name] = version
            logger.info("Prompt 版本切换 | name=%s version=%s", name, version)

    def list_versions(self, name: str) -> list[str]:
        """列出某模板的所有版本。"""
        with self._lock:
            return list(self._templates.get(name, {}).keys())

    def reload(self, prompts_dir: Path | None = None) -> None:
        """从文件系统重新加载所有模板。"""
        with self._lock:
            self._templates.clear()
            self._defaults.clear()
        if prompts_dir:
            self._load_from_dir(prompts_dir)

    def _load_from_dir(self, prompts_dir: Path) -> None:
        """从 prompts/ 目录加载模板。"""
        config_path = prompts_dir / "config.yaml"
        if not config_path.exists():
            logger.warning("config.yaml 不存在，使用内置默认 prompt")
            return

        with open(config_path) as f:
            config = yaml.safe_load(f) or {}

        defaults = config.get("defaults", {})
        templates_config = config.get("templates", {})

        for name, meta in templates_config.items():
            file_name = meta.get("file", f"{name}.j2")
            file_path = prompts_dir / file_name
            if not file_path.exists():
                logger.warning("模板文件不存在: %s", file_path)
                continue
            try:
                with open(file_path) as f:
                    content = f.read()
                version = config.get("version", "1.0")
                self.register(name, version, content)
                if name in defaults:
                    self.set_default(name, defaults[name])
            except TemplateSyntaxError as e:
                logger.error("模板语法错误 | file=%s error=%s", file_name, e)
            except Exception as e:
                logger.error("加载模板失败 | file=%s error=%s", file_name, e)

        logger.info("Prompt 加载完成 | count=%d", len(self._templates))



# 全局单例
_registry = PromptRegistry()


def get_registry() -> PromptRegistry:
    """获取全局 PromptRegistry 实例。"""
    return _registry


__all__ = ["PromptRegistry", "get_registry"]
