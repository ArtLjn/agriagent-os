"""跨 Python 版本兼容工具。"""

from datetime import timezone
from enum import Enum

UTC = timezone.utc

try:
    from enum import StrEnum as StrEnum
except ImportError:

    class StrEnum(str, Enum):
        """Python 3.10 兼容版 StrEnum。"""
