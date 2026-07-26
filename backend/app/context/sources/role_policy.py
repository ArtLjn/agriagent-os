"""Role & Policies Context sources。

当前 assistant role 仍由 UserSettingsSelector 输出；此入口保留六类目录边界。
"""

from app.context.sources.business import UserSettingsSelector

__all__ = ["UserSettingsSelector"]
