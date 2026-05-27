"""全局限流器实例。"""

from slowapi import Limiter  # harness-exempt: external library, not internal api layer
from slowapi.util import get_remote_address  # harness-exempt: external library

limiter = Limiter(key_func=get_remote_address, headers_enabled=True)

__all__ = ["limiter"]
