"""Data Flywheel 文档 Repository selector 兼容入口。

真实实现已迁到 ``app.platforms.shared.repository_selector``。
"""

from app.platforms.shared.repository_selector import build_data_flywheel_repository

__all__ = ["build_data_flywheel_repository"]
