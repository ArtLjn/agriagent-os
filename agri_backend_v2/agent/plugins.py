"""Agent 插件清单解析与单插件发现。

插件只提供业务资源：技能声明目录和业务 system prompt。MCP 地址等运行环境
配置仍由 agent/config.yaml 管理，不进入插件清单。

该模块只依赖 pathlib / yaml，避免与 loader、prompts 形成循环依赖。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[1]
_MANIFEST_NAME = "plugin.yaml"
_SCHEMA_VERSION = 2
_NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")
_REQUIRED_FIELDS = frozenset(
    {"schema_version", "name", "display_name", "system_prompt", "skills_dir"}
)
_OPTIONAL_FIELDS = frozenset({"description", "assistant_name"})
_ALLOWED_FIELDS = _REQUIRED_FIELDS | _OPTIONAL_FIELDS


class PluginError(ValueError):
    """插件清单或目录不合法，保留稳定错误码供启动日志和测试定位。"""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class PluginManifest:
    """单个业务插件清单。"""

    schema_version: int
    name: str
    display_name: str
    assistant_name: str
    description: str
    plugin_dir: Path
    system_prompt_path: Path
    skills_dir: Path

    @property
    def skill_paths(self) -> list[Path]:
        """返回按目录名排序的技能目录，排除隐藏和私有目录。"""
        return sorted(
            (
                entry
                for entry in self.skills_dir.iterdir()
                if entry.is_dir() and not entry.name.startswith(("_", "."))
            ),
            key=lambda path: path.name,
        )

    @property
    def system_prompt_source(self) -> str:
        """管理端展示用的仓库相对路径。"""
        return display_path(self.system_prompt_path)


@dataclass(frozen=True)
class PluginScan:
    """业务目录扫描结果；manifest 为空表示该目录清单不可用。"""

    name: str
    manifest: PluginManifest | None
    error_code: str | None = None


def repo_root() -> Path:
    """返回 agri_backend_v2 根目录，不依赖进程 CWD。"""
    return _REPO_ROOT


def resolve_plugin_root(value: str | Path | None) -> Path:
    """把配置中的插件根目录解析为绝对路径。"""
    raw = Path(value or "businesses").expanduser()
    return raw if raw.is_absolute() else (_REPO_ROOT / raw)


def display_path(path: Path) -> str:
    """优先返回仓库相对路径，仓库外路径保持绝对路径。"""
    resolved = path.resolve()
    try:
        return resolved.relative_to(_REPO_ROOT).as_posix()
    except ValueError:
        return str(resolved)


def discover_plugin(root: Path | str, active: str | None = None) -> PluginManifest:
    """发现并校验唯一启用的插件。

    active 为空时扫描 root 下所有 plugin.yaml，必须恰好一个。
    """
    root_path = Path(root).expanduser().resolve()
    if not root_path.is_dir():
        raise PluginError("plugin_root_missing", f"插件根目录不存在: {root_path}")

    if active:
        if not _NAME_RE.match(active):
            raise PluginError("plugin_name_invalid", f"插件名不合法: {active}")
        plugin_dir = root_path / active
        if not plugin_dir.is_dir():
            raise PluginError("plugin_missing", f"插件目录不存在: {plugin_dir}")
        return load_manifest(plugin_dir)

    candidates = _candidate_plugin_dirs(root_path)
    if not candidates:
        raise PluginError("plugin_missing", f"{root_path} 下没有找到 plugin.yaml")
    if len(candidates) > 1:
        names = ", ".join(path.name for path in candidates)
        raise PluginError(
            "plugin_ambiguous",
            f"发现多个插件但未配置 plugins.active: {names}",
        )
    return load_manifest(candidates[0])


def list_plugins(root: Path | str) -> list[PluginScan]:
    """扫描业务根目录，单个坏清单只记录错误码，不阻断其他业务。"""
    root_path = Path(root).expanduser().resolve()
    if not root_path.is_dir():
        raise PluginError("plugin_root_missing", f"插件根目录不存在: {root_path}")

    scans: list[PluginScan] = []
    for plugin_dir in _candidate_plugin_dirs(root_path):
        try:
            manifest = load_manifest(plugin_dir)
        except PluginError as exc:
            scans.append(
                PluginScan(
                    name=plugin_dir.name,
                    manifest=None,
                    error_code=exc.code,
                )
            )
        except (OSError, UnicodeError):
            scans.append(
                PluginScan(
                    name=plugin_dir.name,
                    manifest=None,
                    error_code="plugin_manifest_unreadable",
                )
            )
        else:
            scans.append(PluginScan(name=plugin_dir.name, manifest=manifest))
    return scans


def _candidate_plugin_dirs(root_path: Path) -> list[Path]:
    """返回按目录名排序、包含 plugin.yaml 的可见业务目录。"""
    return sorted(
        (
            entry
            for entry in root_path.iterdir()
            if entry.is_dir()
            and not entry.name.startswith(("_", "."))
            and (entry / _MANIFEST_NAME).is_file()
        ),
        key=lambda path: path.name,
    )


def load_manifest(plugin_dir: Path | str) -> PluginManifest:
    """读取并严格校验单个插件目录。"""
    plugin_path = Path(plugin_dir).expanduser().resolve()
    if not plugin_path.is_dir():
        raise PluginError("plugin_missing", f"插件目录不存在: {plugin_path}")

    manifest_path = plugin_path / _MANIFEST_NAME
    if not manifest_path.is_file():
        raise PluginError("plugin_manifest_missing", f"缺少插件清单: {manifest_path}")

    raw = _load_yaml(manifest_path)
    _validate_fields(raw, manifest_path)

    name = str(raw["name"]).strip()
    if not _NAME_RE.match(name):
        raise PluginError("plugin_name_invalid", f"插件名不合法: {name}")
    if name != plugin_path.name:
        raise PluginError(
            "plugin_name_mismatch",
            f"插件名 {name} 与目录名 {plugin_path.name} 不一致",
        )

    display_name = str(raw["display_name"]).strip()
    if not display_name:
        raise PluginError("plugin_display_name_empty", "display_name 不能为空")

    description = raw.get("description", "")
    if not isinstance(description, str):
        raise PluginError("plugin_description_invalid", "description 必须是字符串")

    assistant_name = raw.get("assistant_name", display_name)
    if not isinstance(assistant_name, str) or not assistant_name.strip():
        raise PluginError(
            "plugin_assistant_name_invalid", "assistant_name 必须是非空字符串"
        )
    assistant_name = assistant_name.strip()
    if len(assistant_name) > 40:
        raise PluginError(
            "plugin_assistant_name_invalid", "assistant_name 不能超过 40 个字符"
        )

    system_prompt = _resolve_within(
        plugin_path, raw["system_prompt"], "system_prompt"
    )
    if not system_prompt.is_file():
        raise PluginError(
            "plugin_system_prompt_missing", f"system_prompt 不存在: {system_prompt}"
        )

    skills_dir = _resolve_within(plugin_path, raw["skills_dir"], "skills_dir")
    if not skills_dir.is_dir():
        raise PluginError(
            "plugin_skills_missing", f"skills_dir 不存在: {skills_dir}"
        )

    manifest = PluginManifest(
        schema_version=_SCHEMA_VERSION,
        name=name,
        display_name=display_name,
        assistant_name=assistant_name,
        description=description,
        plugin_dir=plugin_path,
        system_prompt_path=system_prompt,
        skills_dir=skills_dir,
    )
    if not manifest.skill_paths:
        raise PluginError(
            "plugin_skills_empty", f"插件技能目录为空: {manifest.skills_dir}"
        )
    return manifest


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise PluginError("plugin_manifest_invalid", f"{path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise PluginError("plugin_manifest_invalid", f"{path} 必须是 YAML 对象")
    return raw


def _validate_fields(raw: dict[str, Any], path: Path) -> None:
    unknown = sorted(set(raw) - _ALLOWED_FIELDS)
    if unknown:
        raise PluginError(
            "plugin_manifest_unknown_fields",
            f"{path} 包含未知字段: {', '.join(unknown)}",
        )
    missing = sorted(_REQUIRED_FIELDS - set(raw))
    if missing:
        raise PluginError(
            "plugin_manifest_missing_fields",
            f"{path} 缺少必填字段: {', '.join(missing)}",
        )
    if raw["schema_version"] != _SCHEMA_VERSION:
        raise PluginError(
            "plugin_schema_version_invalid",
            f"schema_version 必须为 {_SCHEMA_VERSION}",
        )


def _resolve_within(base: Path, value: Any, field_name: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise PluginError(
            "plugin_path_invalid", f"{field_name} 必须是非空相对路径"
        )
    relative = Path(value.strip())
    if relative.is_absolute():
        raise PluginError(
            "plugin_path_escape", f"{field_name} 不能是绝对路径: {value}"
        )
    resolved = (base / relative).resolve()
    try:
        resolved.relative_to(base.resolve())
    except ValueError as exc:
        raise PluginError(
            "plugin_path_escape", f"{field_name} 不能逃逸插件目录: {value}"
        ) from exc
    return resolved


__all__ = [
    "PluginError",
    "PluginManifest",
    "PluginScan",
    "discover_plugin",
    "display_path",
    "list_plugins",
    "load_manifest",
    "repo_root",
    "resolve_plugin_root",
]
