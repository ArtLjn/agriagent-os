"""跨 Python 版本兼容工具。"""

from enum import Enum

try:
    from enum import StrEnum as StrEnum
except ImportError:

    class StrEnum(str, Enum):
        """Python 3.10 兼容版 StrEnum。"""

