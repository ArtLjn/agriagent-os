"""LLM providers.json 文件监听辅助。"""

import logging
import threading
from pathlib import Path
from typing import Protocol

try:
    from watchfiles import watch as _watchfiles_watch

    _HAS_WATCHFILES = True
except ImportError:
    _HAS_WATCHFILES = False

logger = logging.getLogger(__name__)


class ReloadableLLMConfig(Protocol):
    def reload(self) -> None: ...


def start_llm_config_watcher(manager: ReloadableLLMConfig) -> None:
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

    def _watch():
        logger.info("providers.json 文件监听已启动 | path=%s", config_path)
        for changes in _watchfiles_watch(config_path.parent):
            for _change_type, changed_path in changes:
                if Path(changed_path).name == config_path.name:
                    logger.info("检测到 providers.json 变化，执行热更新")
                    manager.reload()

    threading.Thread(target=_watch, daemon=True, name="llm-config-watcher").start()
