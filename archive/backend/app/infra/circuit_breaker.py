"""LLM 调用熔断器 + 指数退避重试。"""

import asyncio
import logging
import time
from enum import Enum

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """三态熔断器：CLOSED -> OPEN -> HALF_OPEN -> CLOSED。"""

    def __init__(self, failure_threshold: int = 3, recovery_timeout: int = 30):
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = 0.0

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if time.time() - self._last_failure_time >= self._recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                logger.info("熔断器 HALF_OPEN - 开始探测")
        return self._state

    def record_success(self) -> None:
        if self._state != CircuitState.CLOSED:
            logger.info("熔断器 %s -> CLOSED (调用成功)", self._state.value)
        self._state = CircuitState.CLOSED
        self._failure_count = 0

    def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.time()
        if self._failure_count >= self._failure_threshold:
            if self._state != CircuitState.OPEN:
                logger.warning(
                    "熔断器 CLOSED -> OPEN (连续 %d 次失败)", self._failure_count
                )
            self._state = CircuitState.OPEN

    def allow(self) -> bool:
        return self.state != CircuitState.OPEN


class CircuitOpenError(Exception):
    """熔断器打开时的异常。"""


async def call_with_retry(
    fn,
    breaker: CircuitBreaker,
    retry_max: int = 3,
    retry_backoff_base: float = 2.0,
    timeout: float = 60.0,
):
    """带熔断 + 重试的异步调用包装。"""
    if not breaker.allow():
        raise CircuitOpenError("熔断器 OPEN，请求被拒绝")

    last_error = None
    for attempt in range(retry_max):
        try:
            result = await asyncio.wait_for(fn(), timeout=timeout)
            breaker.record_success()
            return result
        except CircuitOpenError:
            raise
        except Exception as e:
            last_error = e
            breaker.record_failure()
            if attempt < retry_max - 1 and breaker.allow():
                backoff = retry_backoff_base * (2**attempt)
                logger.warning(
                    "调用失败 (attempt %d/%d), %.1fs 后重试: %s",
                    attempt + 1,
                    retry_max,
                    backoff,
                    str(e)[:100],
                )
                await asyncio.sleep(backoff)
            else:
                break

    raise last_error or CircuitOpenError("重试耗尽")
