"""VecminDB SDK Retry Strategy.

Implements exponential-backoff retry with optional jitter for transient
failures.  Only idempotent or explicitly retriable status codes trigger
a retry; non-retriable errors propagate immediately.

The retry logic is deliberately framework-agnostic so it can be used by
both the synchronous and asynchronous clients.
"""

from __future__ import annotations

import asyncio
import random
import time
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Optional, Set, TypeVar

from .exceptions import RateLimitError, ServerError, ConnectionError, TimeoutError

logger = logging.getLogger("vecmindb.retry")

T = TypeVar("T")

# Status codes that are generally safe to retry on.
_DEFAULT_RETRIABLE_STATUS = {429, 500, 502, 503, 504}

# Exception types that are retriable by default.
_DEFAULT_RETRIABLE_EXCEPTIONS = (
    ServerError,
    RateLimitError,
    ConnectionError,
    TimeoutError,
)


@dataclass
class RetryConfig:
    """Configuration for the retry policy.

    Attributes:
        max_retries: Maximum number of retry attempts (0 = no retries).
        backoff_factor: Base multiplier for the exponential back-off.
        max_backoff: Upper bound on back-off duration in seconds.
        jitter: If ``True``, a small random jitter is added to each back-off
            to avoid thundering-herd effects.
        retriable_statuses: Set of HTTP status codes that trigger a retry.
        retriable_exceptions: Tuple of exception types eligible for retry.
    """

    max_retries: int = 3
    backoff_factor: float = 0.5
    max_backoff: float = 30.0
    jitter: bool = True
    retriable_statuses: set = field(default_factory=lambda: set(_DEFAULT_RETRIABLE_STATUS))
    retriable_exceptions: tuple = _DEFAULT_RETRIABLE_EXCEPTIONS

    def compute_backoff(self, attempt: int) -> float:
        """Calculate the back-off duration for *attempt* (0-indexed).

        Uses exponential back-off: ``backoff_factor * 2 ** attempt``.

        Args:
            attempt: Zero-indexed retry attempt number.

        Returns:
            Number of seconds to wait before the next attempt.
        """
        delay = min(self.backoff_factor * (2 ** attempt), self.max_backoff)
        if self.jitter:
            delay *= random.uniform(0.5, 1.5)  # noqa: S311
        return delay


def should_retry(
    exc: Exception,
    config: RetryConfig,
) -> bool:
    """Determine whether *exc* qualifies for a retry.

    Args:
        exc: The exception raised by the request.
        config: Active retry configuration.

    Returns:
        ``True`` if the exception is retriable.
    """
    # Check by exception type
    if isinstance(exc, config.retriable_exceptions):
        return True
    # Check by status code embedded in our custom exceptions
    code = getattr(exc, "code", None)
    if code is not None and code in config.retriable_statuses:
        return True
    return False


# ---------------------------------------------------------------------------
# Synchronous retry
# ---------------------------------------------------------------------------


def retry_sync(
    fn: Callable[[], T],
    config: RetryConfig,
) -> T:
    """Execute *fn* with synchronous retry logic.

    Args:
        fn: Zero-argument callable that performs the HTTP request.
        config: Retry configuration.

    Returns:
        The return value of *fn* on success.

    Raises:
        The last exception if all retries are exhausted.
    """
    last_exc: Optional[Exception] = None
    for attempt in range(config.max_retries + 1):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if attempt == config.max_retries or not should_retry(exc, config):
                raise
            delay = config.compute_backoff(attempt)
            logger.warning(
                "Retry %d/%d after %.2fs due to %s",
                attempt + 1,
                config.max_retries,
                delay,
                exc,
            )
            time.sleep(delay)
    # Should not be reached, but satisfy type-checkers.
    raise last_exc  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Asynchronous retry
# ---------------------------------------------------------------------------


async def retry_async(
    fn: Callable[[], Coroutine[Any, Any, T]],
    config: RetryConfig,
) -> T:
    """Execute *fn* with asynchronous retry logic.

    Args:
        fn: Zero-argument async callable that performs the HTTP request.
        config: Retry configuration.

    Returns:
        The return value of *fn* on success.

    Raises:
        The last exception if all retries are exhausted.
    """
    last_exc: Optional[Exception] = None
    for attempt in range(config.max_retries + 1):
        try:
            return await fn()
        except Exception as exc:
            last_exc = exc
            if attempt == config.max_retries or not should_retry(exc, config):
                raise
            delay = config.compute_backoff(attempt)
            logger.warning(
                "Retry %d/%d after %.2fs due to %s",
                attempt + 1,
                config.max_retries,
                delay,
                exc,
            )
            await asyncio.sleep(delay)
    raise last_exc  # type: ignore[misc]
